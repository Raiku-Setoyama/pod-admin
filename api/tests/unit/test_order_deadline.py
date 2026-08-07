"""Unit tests for the order deadline (注文〆切時間) service.

- parse_deadline_time: 有効な "HH:MM" / 空文字・None / 不正形式（None 扱い）
- validate_setting_value: 有効 / 空文字許可 / 不正値は日本語 ValueError
- effective_order_date: 〆切ちょうど(==)・直前・直後・未設定、翌営業日が
  土日祝・独自休日で連続するケース
"""

from datetime import date, time
from datetime import datetime as dt
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.services.order_deadline import (
    ORDER_DEADLINE_TIME_KEY,
    effective_order_date,
    get_deadline_time,
    parse_deadline_time,
    validate_setting_value,
)

JST = ZoneInfo("Asia/Tokyo")


def _jst(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> dt:
    return dt(year, month, day, hour, minute, second, tzinfo=JST)


class TestKey:
    def test_key_constant(self) -> None:
        assert ORDER_DEADLINE_TIME_KEY == "order_deadline_time"


class TestParseDeadlineTime:
    def test_parses_valid_hhmm(self) -> None:
        assert parse_deadline_time("18:00") == time(18, 0)
        assert parse_deadline_time("00:00") == time(0, 0)
        assert parse_deadline_time("23:59") == time(23, 59)

    def test_strips_surrounding_whitespace(self) -> None:
        assert parse_deadline_time("  09:30  ") == time(9, 30)

    def test_empty_returns_none(self) -> None:
        assert parse_deadline_time("") is None
        assert parse_deadline_time("   ") is None

    def test_none_returns_none(self) -> None:
        assert parse_deadline_time(None) is None

    def test_invalid_format_returns_none(self) -> None:
        # 保存時に validate で弾かれるが、防御的に None（＝無効）とする
        assert parse_deadline_time("25:00") is None
        assert parse_deadline_time("9:5") is None  # ゼロ埋めなしは不正
        assert parse_deadline_time("abc") is None
        assert parse_deadline_time("18:60") is None


class TestValidateSettingValue:
    def test_accepts_valid_hhmm(self) -> None:
        validate_setting_value("18:00")
        validate_setting_value("00:00")
        validate_setting_value("23:59")

    def test_accepts_empty(self) -> None:
        # 空文字は無効化として許可
        validate_setting_value("")

    def test_rejects_hour_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            validate_setting_value("25:00")

    def test_rejects_minute_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            validate_setting_value("18:60")

    def test_rejects_non_zero_padded(self) -> None:
        with pytest.raises(ValueError):
            validate_setting_value("9:5")

    def test_rejects_non_time_string(self) -> None:
        with pytest.raises(ValueError):
            validate_setting_value("abc")

    def test_error_message_is_japanese(self) -> None:
        with pytest.raises(ValueError, match="注文〆切時間は HH:MM 形式"):
            validate_setting_value("99:99")


class TestGetDeadlineTime:
    @staticmethod
    def _repo(value: str | None) -> AsyncMock:
        setting = None
        if value is not None:
            setting = MagicMock()
            setting.value = value
        repo = AsyncMock()
        repo.find_by_key = AsyncMock(return_value=setting)
        return repo

    @pytest.mark.asyncio
    async def test_reads_and_parses_setting(self) -> None:
        repo = self._repo("18:00")
        assert await get_deadline_time(repo) == time(18, 0)
        repo.find_by_key.assert_awaited_once_with(ORDER_DEADLINE_TIME_KEY)

    @pytest.mark.asyncio
    async def test_missing_setting_returns_none(self) -> None:
        assert await get_deadline_time(self._repo(None)) is None

    @pytest.mark.asyncio
    async def test_empty_value_returns_none(self) -> None:
        assert await get_deadline_time(self._repo("")) is None


class TestEffectiveOrderDate:
    def test_none_deadline_returns_today(self) -> None:
        # 未設定は常に当日起算（後方互換）
        now = _jst(2026, 7, 9, 23, 59)
        assert effective_order_date(now, None) == date(2026, 7, 9)

    def test_before_deadline_returns_today(self) -> None:
        # 〆切直前 → 当日
        now = _jst(2026, 7, 9, 17, 59, 59)
        assert effective_order_date(now, time(18, 0)) == date(2026, 7, 9)

    def test_exactly_deadline_defers_to_next_business_day(self) -> None:
        # 〆切ちょうど(==)は超過扱い → 翌営業日（木→金）
        now = _jst(2026, 7, 9, 18, 0, 0)
        assert effective_order_date(now, time(18, 0)) == date(2026, 7, 10)

    def test_after_deadline_defers_to_next_business_day(self) -> None:
        # 〆切直後 → 翌営業日（木→金）
        now = _jst(2026, 7, 9, 18, 5)
        assert effective_order_date(now, time(18, 0)) == date(2026, 7, 10)

    def test_after_deadline_skips_weekend(self) -> None:
        # 金曜の〆切超過 → 翌営業日は月曜（土日スキップ）
        now = _jst(2026, 7, 10, 20, 0)
        assert effective_order_date(now, time(18, 0)) == date(2026, 7, 13)

    def test_after_deadline_skips_company_holiday(self) -> None:
        # 木曜の〆切超過だが翌日の金曜が独自休日 → 翌営業日は月曜
        now = _jst(2026, 7, 9, 18, 30)
        holidays = {date(2026, 7, 10)}  # 金曜を独自休日に
        assert effective_order_date(now, time(18, 0), holidays) == date(2026, 7, 13)

    def test_after_deadline_skips_consecutive_holidays(self) -> None:
        # 金曜の〆切超過、翌週月曜(7/13)が海の日相当の独自休日 → 火曜へ
        now = _jst(2026, 7, 10, 19, 0)
        holidays = {date(2026, 7, 13)}
        assert effective_order_date(now, time(18, 0), holidays) == date(2026, 7, 14)
