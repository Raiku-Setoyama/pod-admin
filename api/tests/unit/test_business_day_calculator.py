"""Tests for business day calculator utility."""

from datetime import date

from app.utils.business_day_calculator import add_business_days, is_business_day


class TestIsBusinessDay:
    """Tests for is_business_day function."""

    def test_weekday_is_business_day(self) -> None:
        """平日は営業日."""
        assert is_business_day(date(2026, 4, 9)) is True  # Thursday

    def test_saturday_is_not_business_day(self) -> None:
        """土曜日は非営業日."""
        assert is_business_day(date(2026, 4, 11)) is False  # Saturday

    def test_sunday_is_not_business_day(self) -> None:
        """日曜日は非営業日."""
        assert is_business_day(date(2026, 4, 12)) is False  # Sunday

    def test_japanese_holiday_is_not_business_day(self) -> None:
        """日本の祝日は非営業日（昭和の日: 4/29）."""
        assert is_business_day(date(2026, 4, 29)) is False  # 昭和の日

    def test_new_years_day_is_not_business_day(self) -> None:
        """元日は非営業日."""
        assert is_business_day(date(2026, 1, 1)) is False  # 元日

    def test_company_holiday_is_not_business_day(self) -> None:
        """独自休日は非営業日."""
        holidays = {date(2026, 8, 13), date(2026, 8, 14)}
        assert is_business_day(date(2026, 8, 13), holidays) is False

    def test_non_company_holiday_is_business_day(self) -> None:
        """独自休日以外の平日は営業日."""
        holidays = {date(2026, 8, 13)}
        assert is_business_day(date(2026, 8, 12), holidays) is True  # Wednesday


class TestAddBusinessDays:
    """Tests for add_business_days function."""

    def test_zero_days_returns_start_date(self) -> None:
        """0営業日加算はstart_dateをそのまま返す."""
        result = add_business_days(date(2026, 4, 9), 0)
        assert result == date(2026, 4, 9)

    def test_negative_days_returns_start_date(self) -> None:
        """負の営業日はstart_dateをそのまま返す."""
        result = add_business_days(date(2026, 4, 9), -1)
        assert result == date(2026, 4, 9)

    def test_simple_weekday_addition(self) -> None:
        """平日のみの加算（週末をまたがない）."""
        # 月曜日から3営業日 → 木曜日
        result = add_business_days(date(2026, 4, 6), 3)  # Monday
        assert result == date(2026, 4, 9)  # Thursday

    def test_weekend_skip(self) -> None:
        """週末をまたぐ場合のスキップ."""
        # 木曜日から3営業日 → 翌火曜日
        result = add_business_days(date(2026, 4, 9), 3)  # Thursday
        assert result == date(2026, 4, 14)  # Tuesday

    def test_friday_start_1_day(self) -> None:
        """金曜日から1営業日 → 翌月曜日."""
        result = add_business_days(date(2026, 4, 10), 1)  # Friday
        assert result == date(2026, 4, 13)  # Monday

    def test_five_business_days_across_weekend(self) -> None:
        """5営業日加算（週末をまたぐ）."""
        # 金曜日から5営業日
        result = add_business_days(date(2026, 4, 10), 5)  # Friday
        assert result == date(2026, 4, 17)  # Friday

    def test_skip_japanese_holiday(self) -> None:
        """日本の祝日をスキップ."""
        # 4/28(火)から2営業日 → 4/29(水)は昭和の日でスキップ → 4/30(木), 5/1(金)
        # Wait, 2026年の4/29は水曜日
        # 4/28(火)起算: 翌日4/29(水) = 昭和の日 → スキップ, 4/30(木) = 1日目, 5/1(金) = 2日目
        result = add_business_days(date(2026, 4, 28), 2)
        assert result == date(2026, 5, 1)

    def test_skip_company_holiday(self) -> None:
        """独自休日をスキップ."""
        holidays = {date(2026, 4, 14)}  # Tuesday
        # 木曜日から3営業日: 金(1), 月(2), 火=独自休日→スキップ, 水(3)
        result = add_business_days(date(2026, 4, 9), 3, holidays)
        assert result == date(2026, 4, 15)  # Wednesday

    def test_golden_week(self) -> None:
        """GW（連休）をまたぐケース."""
        # 2026年GW: 4/29(水)昭和の日, 5/3(日)憲法記念日, 5/4(月)みどりの日, 5/5(火)こどもの日
        # 5/6(水)振替休日
        # 4/28(火)から5営業日:
        # 4/29(水)=祝日skip, 4/30(木)=1, 5/1(金)=2, 5/2(土)skip, 5/3(日)skip,
        # 5/4(月)=みどりの日skip, 5/5(火)=こどもの日skip, 5/6(水)=振替休日skip,
        # 5/7(木)=3, 5/8(金)=4, 5/9(土)skip, 5/10(日)skip, 5/11(月)=5
        result = add_business_days(date(2026, 4, 28), 5)
        assert result == date(2026, 5, 11)

    def test_company_holidays_with_weekend(self) -> None:
        """独自休日と週末が重なるケース."""
        # 独自休日が土曜日の場合、すでに非営業日なので影響なし
        holidays = {date(2026, 4, 11)}  # Saturday
        result = add_business_days(date(2026, 4, 9), 3)  # Thursday
        result_with_holiday = add_business_days(date(2026, 4, 9), 3, holidays)
        assert result == result_with_holiday  # 結果は同じ

    def test_one_business_day(self) -> None:
        """1営業日加算."""
        # 水曜日から1営業日 → 木曜日
        result = add_business_days(date(2026, 4, 8), 1)
        assert result == date(2026, 4, 9)

    def test_consecutive_company_holidays(self) -> None:
        """連続する独自休日（夏季休暇など）."""
        # 8/11(火)〜8/14(金)が夏季休暇
        holidays = {
            date(2026, 8, 11),
            date(2026, 8, 12),
            date(2026, 8, 13),
            date(2026, 8, 14),
        }
        # 8/10(月)から1営業日: 8/11-14全てスキップ, 8/15(土)skip, 8/16(日)skip, 8/17(月)=1日目
        result = add_business_days(date(2026, 8, 10), 1, holidays)
        assert result == date(2026, 8, 17)

    def test_start_date_itself_not_counted(self) -> None:
        """起算日（start_date）自体はカウントされない."""
        # 月曜日から1営業日 → 火曜日（月曜日はカウントしない）
        result = add_business_days(date(2026, 4, 6), 1)  # Monday
        assert result == date(2026, 4, 7)  # Tuesday
