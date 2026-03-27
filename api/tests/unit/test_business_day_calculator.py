"""Tests for business day calculator."""

from datetime import date

import pytest

from app.utils.business_day_calculator import add_business_days, is_business_day


class TestIsBusinessDay:
    def test_weekday_is_business_day(self):
        assert is_business_day(date(2026, 3, 30), set()) is True  # Monday

    def test_saturday_is_not_business_day(self):
        assert is_business_day(date(2026, 3, 28), set()) is False

    def test_sunday_is_not_business_day(self):
        assert is_business_day(date(2026, 3, 29), set()) is False

    def test_national_holiday_is_not_business_day(self):
        assert is_business_day(date(2026, 1, 1), set()) is False  # 元日

    def test_company_holiday_is_not_business_day(self):
        company_holidays = {date(2026, 8, 13)}
        assert is_business_day(date(2026, 8, 13), company_holidays) is False

    def test_weekday_not_holiday_is_business_day(self):
        assert is_business_day(date(2026, 4, 1), set()) is True


class TestAddBusinessDays:
    def test_add_zero_days(self):
        # Friday + 0 = next business day = Monday
        result = add_business_days(date(2026, 3, 27), 0, set())
        assert result == date(2026, 3, 30)

    def test_add_days_within_week(self):
        # Monday + 3 = Thursday
        result = add_business_days(date(2026, 3, 30), 3, set())
        assert result == date(2026, 4, 2)

    def test_add_days_across_weekend(self):
        # Thursday + 5 = next Thu (skipping weekend)
        result = add_business_days(date(2026, 3, 26), 5, set())
        assert result == date(2026, 4, 2)

    def test_add_days_with_national_holiday(self):
        # Monday 4/27 + 3 days, skipping 4/29 (昭和の日)
        result = add_business_days(date(2026, 4, 27), 3, set())
        assert result == date(2026, 5, 1)

    def test_add_days_with_company_holiday(self):
        company_holidays = {date(2026, 3, 31)}
        # Monday 3/30 + 2 days, skipping 3/31 (company holiday)
        result = add_business_days(date(2026, 3, 30), 2, company_holidays)
        assert result == date(2026, 4, 2)

    def test_add_five_business_days_default(self):
        # Monday 3/30 + 5 = Mon 4/6
        result = add_business_days(date(2026, 3, 30), 5, set())
        assert result == date(2026, 4, 6)

    def test_start_date_is_friday(self):
        # Friday 3/27 + 5 = Fri 4/3
        result = add_business_days(date(2026, 3, 27), 5, set())
        assert result == date(2026, 4, 3)
