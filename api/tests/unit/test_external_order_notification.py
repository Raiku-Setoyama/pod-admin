"""Unit tests for external order notification settings and service.

- 設定値バリデーション（有効/無効値、メール形式、長さ）
- 通知のスキップ条件（無効・宛先空・メールサービス未設定）
- 有効時に BackgroundTasks へ送信が積まれること
- 設定読込で例外が起きても注文受付をブロックしないこと
"""

import types
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks

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


class TestEnqueueIfEnabled:
    @pytest.mark.asyncio
    async def test_skips_when_email_service_missing(self) -> None:
        repo = _make_repo("true", "a@example.com")
        service = ExternalOrderNotificationService(repo, None)
        bg = BackgroundTasks()

        await service.enqueue_if_enabled(bg, order=cast("OrderResponse", _make_order()))

        assert len(bg.tasks) == 0

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self) -> None:
        repo = _make_repo("false", "a@example.com")
        service = ExternalOrderNotificationService(repo, MagicMock())
        bg = BackgroundTasks()

        await service.enqueue_if_enabled(bg, order=cast("OrderResponse", _make_order()))

        assert len(bg.tasks) == 0

    @pytest.mark.asyncio
    async def test_skips_when_enabled_setting_missing(self) -> None:
        repo = _make_repo(None, "a@example.com")
        service = ExternalOrderNotificationService(repo, MagicMock())
        bg = BackgroundTasks()

        await service.enqueue_if_enabled(bg, order=cast("OrderResponse", _make_order()))

        assert len(bg.tasks) == 0

    @pytest.mark.asyncio
    async def test_skips_when_recipients_empty(self) -> None:
        repo = _make_repo("true", "")
        service = ExternalOrderNotificationService(repo, MagicMock())
        bg = BackgroundTasks()

        await service.enqueue_if_enabled(bg, order=cast("OrderResponse", _make_order()))

        assert len(bg.tasks) == 0

    @pytest.mark.asyncio
    async def test_enqueues_when_enabled_with_recipients(self) -> None:
        repo = _make_repo("true", "a@example.com, b@example.com")
        email_service = MagicMock()
        service = ExternalOrderNotificationService(repo, email_service)
        bg = BackgroundTasks()

        await service.enqueue_if_enabled(bg, order=cast("OrderResponse", _make_order()))

        assert len(bg.tasks) == 1
        task = bg.tasks[0]
        assert task.func == email_service.send_external_order_notification
        assert task.kwargs["to_emails"] == ["a@example.com", "b@example.com"]
        assert task.kwargs["order_number"] == "0000001"
        assert task.kwargs["source_code"] == "RKSYO"
        assert task.kwargs["total_price"] == 5000
        assert task.kwargs["order_items"] == [
            {"product_name": "オリジナルTシャツ", "quantity": 2}
        ]

    @pytest.mark.asyncio
    async def test_never_raises_on_repo_error(self) -> None:
        repo = MagicMock()
        repo.find_by_key = AsyncMock(side_effect=RuntimeError("db down"))
        service = ExternalOrderNotificationService(repo, MagicMock())
        bg = BackgroundTasks()

        # 例外を送出せず、タスクも積まれない（注文受付はブロックされない）
        await service.enqueue_if_enabled(bg, order=cast("OrderResponse", _make_order()))

        assert len(bg.tasks) == 0
