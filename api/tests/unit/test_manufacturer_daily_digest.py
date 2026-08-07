"""Unit tests for ManufacturerDailyDigestService.

送信判定（マスタスイッチ/送信時刻/日次ガード）・0件スキップ・ウォーターマーク更新・
冪等性・force フラグ・メールサービス未設定時の挙動を、リポジトリ/メールをモックして検証する。
"""

import types
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.manufacturer_daily_digest import (
    JST,
    ManufacturerDailyDigestService,
)
from app.services.manufacturer_notification import (
    DIGEST_ENABLED_KEY,
    DIGEST_LAST_RUN_DATE_KEY,
    DIGEST_SEND_TIME_KEY,
)

# 送信時刻 09:00 を過ぎた JST 時刻
NOW = datetime(2026, 7, 9, 10, 0, tzinfo=JST)
TODAY_STR = "2026-07-09"


def _setting(value: str | None) -> types.SimpleNamespace | None:
    return types.SimpleNamespace(value=value) if value is not None else None


def _make_app_setting_repo(*, enabled: str="true", send_time: str | None = "09:00", claim: bool=True) -> MagicMock:
    async def find_by_key(key: str) -> Any:
        if key == DIGEST_ENABLED_KEY:
            return _setting(enabled)
        if key == DIGEST_SEND_TIME_KEY:
            return _setting(send_time)
        return None

    repo = MagicMock()
    repo.find_by_key = AsyncMock(side_effect=find_by_key)
    repo.claim_daily_run = AsyncMock(return_value=claim)
    return repo


def _manufacturer(mid: str = "m1", name: str = "メーカーA", email: str = "mfr@example.com") -> Any:
    return types.SimpleNamespace(id=mid, name=name, email=email)


def _settings(to_emails: Any=None, cc_emails: Any=None, last_notified_at: Any=None) -> Any:
    return types.SimpleNamespace(
        to_emails=to_emails or [],
        cc_emails=cc_emails or [],
        last_notified_at=last_notified_at,
    )


def _make_notif_repo(pairs: Any) -> MagicMock:
    repo = MagicMock()
    repo.list_enabled_with_manufacturer = AsyncMock(return_value=pairs)
    repo.update_last_notified_at = AsyncMock()
    return repo


def _make_order_repo(summary_by_id: Any) -> MagicMock:
    async def get_summary(manufacturer_id: Any, since: Any=None) -> Any:
        return summary_by_id.get(
            manufacturer_id, {"ordered_item_count": 0, "total_quantity": 0}
        )

    repo = MagicMock()
    repo.get_new_ordered_summary_by_manufacturer = AsyncMock(side_effect=get_summary)
    return repo


def _make_email_service(result: Any=True) -> MagicMock:
    svc = MagicMock()
    svc.send_manufacturer_daily_digest = AsyncMock(return_value=result)
    return svc


def _make_db() -> MagicMock:
    db = MagicMock()
    db.commit = AsyncMock()
    return db


def _service(*, app_setting_repo: Any=None, notif_repo: Any=None, order_repo: Any=None, email_service: Any = "default", db: Any=None) -> Any:
    return ManufacturerDailyDigestService(
        db or _make_db(),
        order_repo or _make_order_repo({}),
        notif_repo or _make_notif_repo([]),
        app_setting_repo or _make_app_setting_repo(),
        _make_email_service() if email_service == "default" else email_service,
    )


class TestGates:
    @pytest.mark.asyncio
    async def test_skips_when_master_disabled(self) -> None:
        notif_repo = _make_notif_repo([(_settings(), _manufacturer())])
        service = _service(
            app_setting_repo=_make_app_setting_repo(enabled="false"), notif_repo=notif_repo
        )

        result = await service.run_daily_digest(now=NOW)

        assert result["ran"] is False
        assert result["reason"] == "disabled"
        notif_repo.list_enabled_with_manufacturer.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_before_send_time(self) -> None:
        service = _service(app_setting_repo=_make_app_setting_repo(send_time="23:00"))

        result = await service.run_daily_digest(now=NOW)

        assert result["ran"] is False
        assert result["reason"] == "before_send_time"

    @pytest.mark.asyncio
    async def test_skips_when_send_time_missing(self) -> None:
        service = _service(app_setting_repo=_make_app_setting_repo(send_time=None))

        result = await service.run_daily_digest(now=NOW)

        assert result["reason"] == "send_time_not_set"

    @pytest.mark.asyncio
    async def test_skips_when_already_ran_today(self) -> None:
        app_repo = _make_app_setting_repo(claim=False)
        notif_repo = _make_notif_repo([(_settings(), _manufacturer())])
        service = _service(app_setting_repo=app_repo, notif_repo=notif_repo)

        result = await service.run_daily_digest(now=NOW)

        assert result["ran"] is False
        assert result["reason"] == "already_ran_today"
        notif_repo.list_enabled_with_manufacturer.assert_not_called()

    @pytest.mark.asyncio
    async def test_claims_today_and_commits(self) -> None:
        app_repo = _make_app_setting_repo()
        db = _make_db()
        service = _service(app_setting_repo=app_repo, db=db)

        await service.run_daily_digest(now=NOW)

        app_repo.claim_daily_run.assert_called_once_with(DIGEST_LAST_RUN_DATE_KEY, TODAY_STR)
        assert db.commit.await_count >= 1


class TestSending:
    @pytest.mark.asyncio
    async def test_sends_and_updates_watermark(self) -> None:
        watermark = datetime(2026, 7, 8, 10, 0, tzinfo=JST)
        settings = _settings(
            to_emails=["to@x.com"], cc_emails=["cc@x.com"], last_notified_at=watermark
        )
        manufacturer = _manufacturer()
        notif_repo = _make_notif_repo([(settings, manufacturer)])
        order_repo = _make_order_repo({"m1": {"ordered_item_count": 3, "total_quantity": 7}})
        email = _make_email_service(True)
        service = _service(notif_repo=notif_repo, order_repo=order_repo, email_service=email)

        result = await service.run_daily_digest(now=NOW)

        assert result["ran"] is True
        assert result["sent_count"] == 1
        assert result["sent_manufacturer_ids"] == ["m1"]
        # 集計はウォーターマーク以降（新規分のみ）
        order_repo.get_new_ordered_summary_by_manufacturer.assert_awaited_once_with(
            "m1", since=watermark
        )
        # 宛先・件数・合計・送信日が渡る
        kwargs = email.send_manufacturer_daily_digest.call_args.kwargs
        assert kwargs["to_emails"] == ["to@x.com"]
        assert kwargs["cc_emails"] == ["cc@x.com"]
        assert kwargs["item_count"] == 3
        assert kwargs["total_quantity"] == 7
        assert kwargs["manufacturer_name"] == "メーカーA"
        assert kwargs["sent_date"] == NOW.date()
        # 送信成功時のみウォーターマークを実行時刻へ更新
        notif_repo.update_last_notified_at.assert_awaited_once_with(settings, NOW)

    @pytest.mark.asyncio
    async def test_skips_zero_item_manufacturer(self) -> None:
        settings = _settings(to_emails=["to@x.com"])
        notif_repo = _make_notif_repo([(settings, _manufacturer())])
        order_repo = _make_order_repo({"m1": {"ordered_item_count": 0, "total_quantity": 0}})
        email = _make_email_service()
        service = _service(notif_repo=notif_repo, order_repo=order_repo, email_service=email)

        result = await service.run_daily_digest(now=NOW)

        assert result["sent_count"] == 0
        assert result["skipped_zero_count"] == 1
        assert result["skipped_zero_manufacturer_ids"] == ["m1"]
        email.send_manufacturer_daily_digest.assert_not_called()
        notif_repo.update_last_notified_at.assert_not_called()

    @pytest.mark.asyncio
    async def test_defaults_to_manufacturer_email_when_to_empty(self) -> None:
        settings = _settings(to_emails=[])  # 未設定
        notif_repo = _make_notif_repo([(settings, _manufacturer(email="fallback@x.com"))])
        order_repo = _make_order_repo({"m1": {"ordered_item_count": 1, "total_quantity": 1}})
        email = _make_email_service(True)
        service = _service(notif_repo=notif_repo, order_repo=order_repo, email_service=email)

        await service.run_daily_digest(now=NOW)

        kwargs = email.send_manufacturer_daily_digest.call_args.kwargs
        assert kwargs["to_emails"] == ["fallback@x.com"]

    @pytest.mark.asyncio
    async def test_failed_send_keeps_watermark(self) -> None:
        settings = _settings(to_emails=["to@x.com"])
        notif_repo = _make_notif_repo([(settings, _manufacturer())])
        order_repo = _make_order_repo({"m1": {"ordered_item_count": 2, "total_quantity": 4}})
        email = _make_email_service(result=False)  # 送信失敗
        service = _service(notif_repo=notif_repo, order_repo=order_repo, email_service=email)

        result = await service.run_daily_digest(now=NOW)

        assert result["failed_count"] == 1
        assert result["sent_count"] == 0
        notif_repo.update_last_notified_at.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_email_service_marks_failed(self) -> None:
        settings = _settings(to_emails=["to@x.com"])
        notif_repo = _make_notif_repo([(settings, _manufacturer())])
        order_repo = _make_order_repo({"m1": {"ordered_item_count": 2, "total_quantity": 4}})
        service = _service(notif_repo=notif_repo, order_repo=order_repo, email_service=None)

        result = await service.run_daily_digest(now=NOW)

        assert result["failed_count"] == 1
        notif_repo.update_last_notified_at.assert_not_called()


class TestForce:
    @pytest.mark.asyncio
    async def test_force_bypasses_gates(self) -> None:
        # マスタスイッチ off でも force なら送信する
        app_repo = _make_app_setting_repo(enabled="false")
        settings = _settings(to_emails=["to@x.com"])
        notif_repo = _make_notif_repo([(settings, _manufacturer())])
        order_repo = _make_order_repo({"m1": {"ordered_item_count": 5, "total_quantity": 9}})
        email = _make_email_service(True)
        service = _service(
            app_setting_repo=app_repo,
            notif_repo=notif_repo,
            order_repo=order_repo,
            email_service=email,
        )

        result = await service.run_daily_digest(force=True, now=NOW)

        assert result["ran"] is True
        assert result["sent_count"] == 1
        # ガードは評価されない
        app_repo.find_by_key.assert_not_called()
        app_repo.claim_daily_run.assert_not_called()
