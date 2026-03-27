"""Business day calculator utility.

営業日計算ユーティリティ。
土日、日本の祝日、TOSYO独自休日を除外して営業日を加算する。
"""

from datetime import date, timedelta

import jpholiday


def is_business_day(target_date: date, company_holidays: set[date]) -> bool:
    """指定日が営業日かどうかを判定する.

    Args:
        target_date: 判定対象の日付
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        営業日であればTrue
    """
    if target_date.weekday() >= 5:
        return False
    if jpholiday.is_holiday(target_date):
        return False
    if target_date in company_holidays:
        return False
    return True


def add_business_days(start_date: date, days: int, company_holidays: set[date]) -> date:
    """起算日の翌日から営業日を加算した日付を返す.

    Args:
        start_date: 起算日（この日はカウントに含まない）
        days: 加算する営業日数
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        加算後の日付
    """
    current = start_date
    remaining = days

    while True:
        current += timedelta(days=1)
        if is_business_day(current, company_holidays):
            remaining -= 1
            if remaining <= 0:
                return current
