"""Unit tests for manufacturer notification settings validation and CRUD service."""

import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.manufacturer_notification import ManufacturerNotificationSettingsUpdate
from app.services.manufacturer_notification import (
    DIGEST_ENABLED_KEY,
    DIGEST_SEND_TIME_KEY,
    ManufacturerNotificationService,
    normalize_emails,
    parse_send_time,
    validate_digest_setting_value,
    validate_emails,
)
from app.utils.exceptions import AppException, ManufacturerNotFoundError


class TestNormalizeEmails:
    def test_strips_and_drops_empty(self) -> None:
        assert normalize_emails([" a@example.com ", "", "  "]) == ["a@example.com"]

    def test_dedupes_preserving_order(self) -> None:
        assert normalize_emails(["a@example.com", "b@example.com", "a@example.com"]) == [
            "a@example.com",
            "b@example.com",
        ]


class TestValidateEmails:
    def test_accepts_valid(self) -> None:
        validate_emails(["a@example.com", "b@example.com"])

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValueError):
            validate_emails(["not-an-email"])

    def test_rejects_too_many(self) -> None:
        with pytest.raises(ValueError):
            validate_emails([f"user{i}@example.com" for i in range(21)])


class TestParseSendTime:
    def test_parses_hhmm(self) -> None:
        t = parse_send_time("09:30")
        assert (t.hour, t.minute) == (9, 30)

    def test_accepts_single_digit_hour(self) -> None:
        # strptime("%H:%M") は "9:30" を 09:30 として受理する（正当な時刻）
        assert parse_send_time("9:30").hour == 9

    def test_rejects_invalid(self) -> None:
        for bad in ["24:00", "12:60", "abc", "09-30", ""]:
            with pytest.raises(ValueError):
                parse_send_time(bad)


class TestValidateDigestSettingValue:
    def test_enabled_accepts_true_false(self) -> None:
        validate_digest_setting_value(DIGEST_ENABLED_KEY, "true")
        validate_digest_setting_value(DIGEST_ENABLED_KEY, "false")

    def test_enabled_rejects_other(self) -> None:
        with pytest.raises(ValueError):
            validate_digest_setting_value(DIGEST_ENABLED_KEY, "yes")

    def test_send_time_accepts_valid(self) -> None:
        validate_digest_setting_value(DIGEST_SEND_TIME_KEY, "09:00")

    def test_send_time_rejects_invalid(self) -> None:
        with pytest.raises(ValueError):
            validate_digest_setting_value(DIGEST_SEND_TIME_KEY, "9am")


def _make_manufacturer_repo(exists: bool) -> MagicMock:
    repo = MagicMock()
    manufacturer = types.SimpleNamespace(id="m1", name="メーカーA") if exists else None
    repo.find_by_id = AsyncMock(return_value=manufacturer)
    return repo


class TestManufacturerNotificationService:
    @pytest.mark.asyncio
    async def test_get_returns_defaults_when_absent(self) -> None:
        notif_repo = MagicMock()
        notif_repo.find_by_manufacturer_id = AsyncMock(return_value=None)
        service = ManufacturerNotificationService(notif_repo, _make_manufacturer_repo(True))

        result = await service.get_settings("m1")

        assert result.manufacturer_id == "m1"
        assert result.daily_digest_enabled is False
        assert result.to_emails == []
        assert result.cc_emails == []
        assert result.last_notified_at is None

    @pytest.mark.asyncio
    async def test_get_raises_when_manufacturer_missing(self) -> None:
        notif_repo = MagicMock()
        service = ManufacturerNotificationService(notif_repo, _make_manufacturer_repo(False))

        with pytest.raises(ManufacturerNotFoundError):
            await service.get_settings("missing")

    @pytest.mark.asyncio
    async def test_update_normalizes_and_persists(self) -> None:
        saved = types.SimpleNamespace(
            manufacturer_id="m1",
            daily_digest_enabled=True,
            to_emails=["a@example.com"],
            cc_emails=["c@example.com"],
            last_notified_at=None,
        )
        notif_repo = MagicMock()
        notif_repo.upsert = AsyncMock(return_value=saved)
        service = ManufacturerNotificationService(notif_repo, _make_manufacturer_repo(True))

        data = ManufacturerNotificationSettingsUpdate(
            daily_digest_enabled=True,
            to_emails=[" a@example.com ", "a@example.com"],  # 重複・空白
            cc_emails=["c@example.com"],
        )
        result = await service.update_settings("m1", data)

        assert result.daily_digest_enabled is True
        # 正規化された値で upsert される
        kwargs = notif_repo.upsert.call_args.kwargs
        assert kwargs["to_emails"] == ["a@example.com"]
        assert kwargs["cc_emails"] == ["c@example.com"]

    @pytest.mark.asyncio
    async def test_update_rejects_invalid_email(self) -> None:
        notif_repo = MagicMock()
        notif_repo.upsert = AsyncMock()
        service = ManufacturerNotificationService(notif_repo, _make_manufacturer_repo(True))

        data = ManufacturerNotificationSettingsUpdate(
            daily_digest_enabled=True,
            to_emails=["not-an-email"],
        )
        with pytest.raises(AppException) as exc:
            await service.update_settings("m1", data)

        assert exc.value.status_code == 422
        notif_repo.upsert.assert_not_called()
