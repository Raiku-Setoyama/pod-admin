"""Unit tests for the Cloud Monitoring alert notification (製造データ生成のアラート).

- 宛先・有効/無効は管理画面の設定（app_settings）に従う。既定は有効
- Webhook の受け口は Basic 認証（パスワード = INTERNAL_API_SECRET）で守る
- 送れなかったときは 503 を返す
"""

import base64
import types
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.config import settings as app_settings
from app.dependencies import get_monitoring_alert_notification_service
from app.main import app
from app.schemas.monitoring_alert import MonitoringIncident
from app.services.email_service import EmailService
from app.services.monitoring_alert_notification import (
    ALERT_ENABLED_KEY,
    ALERT_RECIPIENTS_KEY,
    AlertDelivery,
    MonitoringAlertNotificationService,
    validate_setting_value,
)

_INCIDENT = MonitoringIncident(
    incident_id="i-1",
    policy_name="製造データ生成 VM が応答しない",
    condition_name="illustrator_vm_health が 15 分で 3 回 NG",
    state="open",
    summary="NG が続いています",
    url="https://console.cloud.google.com/monitoring/alerting/incidents/i-1",
    started_at=1759370000,
)


def _repo(enabled: str | None, recipients: str | None) -> MagicMock:
    async def find_by_key(key: str) -> Any:
        value = {ALERT_ENABLED_KEY: enabled, ALERT_RECIPIENTS_KEY: recipients}.get(key)
        return types.SimpleNamespace(value=value) if value is not None else None

    repo = MagicMock()
    repo.find_by_key = AsyncMock(side_effect=find_by_key)
    return repo


def _email(sent: bool = True) -> MagicMock:
    email = MagicMock()
    email.send_monitoring_alert = AsyncMock(return_value=sent)
    return email


class TestValidateSettingValue:
    def test_enabled_accepts_true_false(self) -> None:
        validate_setting_value(ALERT_ENABLED_KEY, "true")
        validate_setting_value(ALERT_ENABLED_KEY, "false")
        with pytest.raises(ValueError):
            validate_setting_value(ALERT_ENABLED_KEY, "yes")

    def test_recipients_must_be_emails(self) -> None:
        validate_setting_value(ALERT_RECIPIENTS_KEY, "a@example.com, b@example.com")
        with pytest.raises(ValueError, match="形式"):
            validate_setting_value(ALERT_RECIPIENTS_KEY, "a@example.com,not-an-email")


class TestNotify:
    @pytest.mark.asyncio
    async def test_sends_to_configured_recipients_by_default(self) -> None:
        """有効/無効が未設定なら送る（アラートは黙るほうが危ない）."""
        email = _email()
        svc = MonitoringAlertNotificationService(_repo(None, "a@example.com,b@example.com"), email)

        assert await svc.notify(_INCIDENT) is AlertDelivery.SENT
        kwargs = email.send_monitoring_alert.await_args.kwargs
        assert kwargs["to_emails"] == ["a@example.com", "b@example.com"]
        assert kwargs["recovered"] is False
        assert kwargs["policy_name"] == _INCIDENT.policy_name

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self) -> None:
        email = _email()
        svc = MonitoringAlertNotificationService(_repo("false", "a@example.com"), email)

        assert await svc.notify(_INCIDENT) is AlertDelivery.DISABLED
        email.send_monitoring_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_without_recipients(self) -> None:
        svc = MonitoringAlertNotificationService(_repo("true", ""), _email())
        assert await svc.notify(_INCIDENT) is AlertDelivery.NO_RECIPIENTS

    @pytest.mark.asyncio
    async def test_reports_send_failure(self) -> None:
        svc = MonitoringAlertNotificationService(_repo(None, "a@example.com"), _email(sent=False))
        assert await svc.notify(_INCIDENT) is AlertDelivery.SEND_FAILED

    @pytest.mark.asyncio
    async def test_reports_missing_sendgrid(self) -> None:
        svc = MonitoringAlertNotificationService(_repo(None, "a@example.com"), None)
        assert await svc.notify(_INCIDENT) is AlertDelivery.EMAIL_NOT_CONFIGURED


class TestWebhookEndpoint:
    """Cloud Monitoring の Webhook（schema 1.2）を受けて送るところまで."""

    _PAYLOAD = {
        "version": "1.2",
        "incident": {
            "incident_id": "i-1",
            "policy_name": "製造データ生成 VM が応答しない",
            "condition_name": "illustrator_vm_health が 15 分で 3 回 NG",
            "state": "open",
            "summary": "NG",
            "url": "https://example.com",
            "started_at": 1759370000,
            "documentation": {"content": "手順", "mime_type": "text/markdown"},
            "resource": {"type": "global"},  # 未知の項目は無視する
        },
    }

    @staticmethod
    def _auth(password: str) -> dict[str, str]:
        token = base64.b64encode(f"monitoring:{password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    @pytest.mark.parametrize(
        ("delivery", "status"),
        [
            pytest.param(AlertDelivery.SENT, 200, id="送れた"),
            pytest.param(AlertDelivery.NO_RECIPIENTS, 200, id="宛先なしは設定どおり"),
            pytest.param(AlertDelivery.SEND_FAILED, 503, id="送れなかった"),
            pytest.param(AlertDelivery.EMAIL_NOT_CONFIGURED, 503, id="SendGrid未設定"),
        ],
    )
    @pytest.mark.asyncio
    async def test_delivers_and_reports_status(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        delivery: AlertDelivery,
        status: int,
    ) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "s3cret")
        service = MagicMock()
        service.notify = AsyncMock(return_value=delivery)
        app.dependency_overrides[get_monitoring_alert_notification_service] = lambda: service
        try:
            res = await client.post(
                "/api/v1/internal/monitoring-alerts", json=self._PAYLOAD, headers=self._auth("s3cret")
            )
        finally:
            app.dependency_overrides.clear()

        assert res.status_code == status
        incident = service.notify.await_args.args[0]
        assert incident.policy_name == "製造データ生成 VM が応答しない"
        assert incident.documentation.content == "手順"

    @pytest.mark.asyncio
    async def test_rejects_wrong_password(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "s3cret")
        res = await client.post(
            "/api/v1/internal/monitoring-alerts", json=self._PAYLOAD, headers=self._auth("wrong")
        )
        assert res.status_code == 401


class TestEmailRendering:
    @pytest.mark.asyncio
    async def test_renders_open_and_closed_alerts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        email = EmailService(api_key="x", from_email="noreply@example.com", contact_email="c@x")
        sent: list[Any] = []

        def fake_send(message: Any) -> types.SimpleNamespace:
            sent.append(message)
            return types.SimpleNamespace(status_code=202)

        monkeypatch.setattr(email._client, "send", fake_send)

        started = datetime(2026, 10, 2, 4, 0, tzinfo=UTC)
        assert await email.send_monitoring_alert(
            ["a@example.com"], recovered=False, policy_name="VM が応答しない",
            started_at=started, runbook="手順",
        )
        assert await email.send_monitoring_alert(
            ["a@example.com"], recovered=True, policy_name="VM が応答しない",
            started_at=started, ended_at=started, runbook="手順",
        )

        assert [m.subject.get() for m in sent] == [
            "【要対応】VM が応答しない",
            "【回復】VM が応答しない",
        ]
        open_text = sent[0].contents[0].content
        closed_text = sent[1].contents[0].content
        assert "■ 発生: 2026-10-02 13:00" in open_text  # JST
        assert "手順" in open_text
        assert "手順" not in closed_text  # 回復の通知に対処手順は載せない

    @pytest.mark.asyncio
    async def test_service_maps_incident_to_email(self) -> None:
        email = _email()
        svc = MonitoringAlertNotificationService(_repo(None, "a@example.com"), email)
        closed = _INCIDENT.model_copy(update={"state": "closed", "ended_at": 1759371000})

        await svc.notify(closed)

        kwargs = email.send_monitoring_alert.await_args.kwargs
        assert kwargs["recovered"] is True
        assert kwargs["started_at"] == datetime.fromtimestamp(1759370000, UTC)
        assert kwargs["ended_at"] == datetime.fromtimestamp(1759371000, UTC)
