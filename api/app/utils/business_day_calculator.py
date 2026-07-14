"""営業日計算ユーティリティ.

土日、日本の祝日、TOSYO独自休日を除外して営業日を加算する。
"""

import datetime

import jpholiday


def is_business_day(
    target_date: datetime.date,
    company_holidays: set[datetime.date] | None = None,
) -> bool:
    """指定日が営業日かどうかを判定する.

    Args:
        target_date: 判定対象の日付
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        営業日ならTrue
    """
    # 土日チェック
    if target_date.weekday() >= 5:
        return False

    # 日本の祝日チェック
    if jpholiday.is_holiday(target_date):
        return False

    # 独自休日チェック
    if company_holidays and target_date in company_holidays:
        return False

    return True


def add_business_days(
    start_date: datetime.date,
    days: int,
    company_holidays: set[datetime.date] | None = None,
) -> datetime.date:
    """start_dateの翌日から営業日をカウントしてdays営業日後の日付を返す.

    Args:
        start_date: 起算日（この日自体はカウントしない）
        days: 加算する営業日数
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        days営業日後の日付

    Examples:
        >>> add_business_days(date(2026, 4, 9), 3)  # 木曜日起算、3営業日後
        date(2026, 4, 14)  # 火曜日（土日を飛ばす）
    """
    if days <= 0:
        return start_date

    current = start_date
    counted = 0

    while counted < days:
        current += datetime.timedelta(days=1)
        if is_business_day(current, company_holidays):
            counted += 1

    return current


def next_business_day(
    target_date: datetime.date,
    company_holidays: set[datetime.date] | None = None,
) -> datetime.date:
    """target_dateの翌営業日を返す（target_date自体は含めない）.

    Args:
        target_date: 起算日（この日自体はカウントしない）
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        target_dateより後の直近の営業日

    Examples:
        >>> next_business_day(date(2026, 7, 10))  # 金曜日
        date(2026, 7, 13)  # 月曜日（土日を飛ばす）
    """
    return add_business_days(target_date, 1, company_holidays)
