"""Unit tests for external order notification settings and service.

- 設定値バリデーション（有効/無効値、メール形式、長さ）
- 通知のスキップ条件（無効・宛先空・メールサービス未設定）
- 有効時にレスポンスを返す前へ送信されること（BackgroundTasks に積まない）
- 設定読込や送信で例外が起きても注文受付をブロックしないこと
"""

import types
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.order import OrderResponse
from app.services.external_order_notification import (
    NOTIFICATION_ENABLED_KEY,
    NOTIFICATION_RECIPIENTS_KEY,
    ExternalOrderNotificationService,
    parse_recipients,
    validate_setting_value,
)


def _setting(value: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(value=value)


def _make_repo(enabled_value: str | None, recipients_value: str | None) -> MagicMock:
    async def find_by_key(key: str) -> Any:
        if key == NOTIFICATION_ENABLED_KEY:
            return _setting(enabled_value) if enabled_value is not None else None
        if key == NOTIFICATION_RECIPIENTS_KEY:
            return _setting(recipients_value) if recipients_value is not None else None
        return None

    repo = MagicMock()
    repo.find_by_key = AsyncMock(side_effect=find_by_key)
    return repo


def _make_order() -> types.SimpleNamespace:
    item = types.SimpleNamespace(product_name="オリジナルTシャツ", quantity=2)
    return types.SimpleNamespace(
        id="order-1",
        order_number="0000001",
        source="RKSYO",
        ordered_at=datetime(2026, 6, 28, 3, 0, tzinfo=UTC),
        customer_name="山田太郎",
        items=[item],
        total_price=5000,
    )


class TestParseRecipients:
    def test_empty_returns_empty_list(self) -> None:
        assert parse_recipients("") == []
        assert parse_recipients(None) == []

    def test_splits_and_strips(self) -> None:
        assert parse_recipients("a@example.com, b@example.com") == [
            "a@example.com",
            "b@example.com",
        ]

    def test_drops_empty_segments(self) -> None:
        assert parse_recipients("a@example.com,,  ,b@example.com") == [
            "a@example.com",
            "b@example.com",
        ]


class TestValidateSettingValue:
    def test_enabled_accepts_true_false(self) -> None:
        validate_setting_value(NOTIFICATION_ENABLED_KEY, "true")
        validate_setting_value(NOTIFICATION_ENABLED_KEY, "false")

    def test_enabled_rejects_other(self) -> None:
        with pytest.raises(ValueError):
            validate_setting_value(NOTIFICATION_ENABLED_KEY, "yes")

    def test_recipients_accepts_empty(self) -> None:
        validate_setting_value(NOTIFICATION_RECIPIENTS_KEY, "")

    def test_recipients_accepts_multiple_valid(self) -> None:
        validate_setting_value(
            NOTIFICATION_RECIPIENTS_KEY, "a@example.com, b@example.com"
        )

    def test_recipients_rejects_invalid_email(self) -> None:
        with pytest.raises(ValueError):
            validate_setting_value(
                NOTIFICATION_RECIPIENTS_KEY, "a@example.com, not-an-email"
            )

    def test_recipients_rejects_too_long(self) -> None:
        long_value = ",".join(f"user{i}@example.com" for i in range(40))
        assert len(long_value) > 500
        with pytest.raises(ValueError):
            validate_setting_value(NOTIFICATION_RECIPIENTS_KEY, long_value)


def _make_email_service() -> MagicMock:
    """送信メソッドだけを待てるようにしたメールサービスの代役."""
    email_service = MagicMock()
    email_service.send_external_order_notification = AsyncMock(return_value=True)
    return email_service


class TestNotifyIfEnabled:
    """送信は BackgroundTasks に積まず、レスポンスを返す前に完了させる（ADR-0026）."""

    @pytest.mark.asyncio
    async def test_skips_before_reading_settings_when_email_service_missing(self) -> None:
        repo = _make_repo("true", "a@example.com")
        service = ExternalOrderNotificationService(repo, None)

        await service.notify_if_enabled(order=cast("OrderResponse", _make_order()))

        # メールサービスが無いなら設定の読み込みにも入らない
        repo.find_by_key.assert_not_awaited()

    @pytest.mark.parametrize(
        ("enabled", "recipients"),
        [
            pytest.param("false", "a@example.com", id="通知が無効"),
            pytest.param(None, "a@example.com", id="有効/無効の設定が無い"),
            pytest.param("true", "", id="宛先が空"),
        ],
    )
    @pytest.mark.asyncio
    async def test_skips_when_not_enabled_or_no_recipients(
        self, enabled: str | None, recipients: str
    ) -> None:
        email_service = _make_email_service()
        service = ExternalOrderNotificationService(
            _make_repo(enabled, recipients), email_service
        )

        await service.notify_if_enabled(order=cast("OrderResponse", _make_order()))

        email_service.send_external_order_notification.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sends_before_returning_when_enabled_with_recipients(self) -> None:
        email_service = _make_email_service()
        service = ExternalOrderNotificationService(
            _make_repo("true", "a@example.com, b@example.com"), email_service
        )

        await service.notify_if_enabled(order=cast("OrderResponse", _make_order()))

        # notify_if_enabled から戻った時点で送信が終わっていること
        email_service.send_external_order_notification.assert_awaited_once()
        kwargs = email_service.send_external_order_notification.await_args.kwargs
        assert kwargs["to_emails"] == ["a@example.com", "b@example.com"]
        assert kwargs["order_number"] == "0000001"
        assert kwargs["source_code"] == "RKSYO"
        assert kwargs["total_price"] == 5000
        assert kwargs["order_items"] == [
            {"product_name": "オリジナルTシャツ", "quantity": 2}
        ]

    @pytest.mark.asyncio
    async def test_never_raises_on_repo_error(self) -> None:
        repo = MagicMock()
        repo.find_by_key = AsyncMock(side_effect=RuntimeError("db down"))
        email_service = _make_email_service()
        service = ExternalOrderNotificationService(repo, email_service)

        # 例外を送出しない（注文受付はブロックされない）
        await service.notify_if_enabled(order=cast("OrderResponse", _make_order()))

        email_service.send_external_order_notification.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_never_raises_when_sending_fails(self) -> None:
        """送信が失敗しても受注は成立させる（ADR-0014: メール障害で業務処理を止めない）."""
        email_service = _make_email_service()
        email_service.send_external_order_notification = AsyncMock(
            side_effect=RuntimeError("sendgrid down")
        )
        service = ExternalOrderNotificationService(
            _make_repo("true", "a@example.com"), email_service
        )

        await service.notify_if_enabled(order=cast("OrderResponse", _make_order()))

        email_service.send_external_order_notification.assert_awaited_once()
