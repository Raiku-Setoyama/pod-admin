"""製造データ生成のアラート通知.

Cloud Monitoring のアラート（infra/modules/manufacturing-monitoring）を Webhook で受け、
管理画面で設定した宛先へメールで送る。宛先・有効/無効は外部注文の通知と同じく
app_settings（key-value）で管理する。

**Monitoring から直接メールを送らない理由。** Monitoring の通知先は Terraform の
管理下にあり、宛先を変えるたびに apply が要る。宛先は運用の都合で変わるので、
管理画面から変えられるようにした（2026-10）。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from app.schemas.monitoring_alert import MonitoringIncident
from app.services.recipient_settings import (
    parse_recipients,
    validate_enabled_value,
    validate_recipients_value,
)

if TYPE_CHECKING:
    from app.repositories.app_setting_repository import AppSettingRepository
    from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

# app_settings のキー
ALERT_ENABLED_KEY = "monitoring_alert_enabled"
ALERT_RECIPIENTS_KEY = "monitoring_alert_recipients"


def validate_setting_value(key: str, value: str) -> None:
    """アラート通知の設定値を検証する（不正なら日本語メッセージの ValueError）."""
    if key == ALERT_ENABLED_KEY:
        validate_enabled_value(value)
    elif key == ALERT_RECIPIENTS_KEY:
        validate_recipients_value(value)


class AlertDelivery(Enum):
    """アラートを受け取った結果."""

    SENT = "sent"
    DISABLED = "disabled"
    NO_RECIPIENTS = "no_recipients"
    EMAIL_NOT_CONFIGURED = "email_not_configured"
    SEND_FAILED = "send_failed"


class MonitoringAlertNotificationService:
    """Cloud Monitoring のアラートを、管理画面で設定した宛先へメールで送る."""

    def __init__(
        self,
        app_setting_repo: AppSettingRepository,
        email_service: EmailService | None,
    ) -> None:
        self._app_setting_repo = app_setting_repo
        self._email_service = email_service

    async def notify(self, incident: MonitoringIncident) -> AlertDelivery:
        """アラートを送る.

        **既定で有効にしている**（外部注文の通知は既定で無効）。アラートは止まっている
        ことを知らせるためのものなので、設定し忘れで黙るほうが危ない。明示的に
        "false" にしたときだけ止める。
        """
        if self._email_service is None:
            logger.error(
                "monitoring alert %s skipped: SendGrid is not configured", incident.policy_name
            )
            return AlertDelivery.EMAIL_NOT_CONFIGURED

        enabled = await self._app_setting_repo.find_by_key(ALERT_ENABLED_KEY)
        if enabled is not None and enabled.value == "false":
            logger.info("monitoring alert %s skipped: disabled", incident.policy_name)
            return AlertDelivery.DISABLED

        recipients_setting = await self._app_setting_repo.find_by_key(ALERT_RECIPIENTS_KEY)
        recipients = parse_recipients(recipients_setting.value if recipients_setting else None)
        if not recipients:
            logger.warning("monitoring alert %s skipped: no recipients", incident.policy_name)
            return AlertDelivery.NO_RECIPIENTS

        # メールの層には Monitoring の形式を持ち込まない（ここで素の値へ落とす）。
        sent = await self._email_service.send_monitoring_alert(
            to_emails=recipients,
            recovered=incident.state == "closed",
            policy_name=incident.policy_name,
            condition_name=incident.condition_name,
            summary=incident.summary,
            started_at=_from_unix(incident.started_at),
            ended_at=_from_unix(incident.ended_at),
            url=incident.url,
            runbook=incident.documentation.content if incident.documentation else "",
        )
        return AlertDelivery.SENT if sent else AlertDelivery.SEND_FAILED


def _from_unix(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, UTC) if ts is not None else None
