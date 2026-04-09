"""Estimated shipping date calculation service."""

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderStatus
from app.repositories.app_setting_repository import AppSettingRepository
from app.repositories.company_holiday_repository import CompanyHolidayRepository
from app.utils.business_day_calculator import add_business_days

logger = logging.getLogger(__name__)

SHIPPING_PREPARATION_DAYS_KEY = "shipping_preparation_days"
SHIPPING_PREPARATION_DAYS_DEFAULT = 5

# 再計算対象のステータス
RECALC_STATUSES = [
    OrderStatus.ORDERED.value,
    OrderStatus.MANUFACTURING.value,
    OrderStatus.DELIVERED.value,
]


def calculate_estimated_shipping_date(
    items_delivery_dates: list[dt.date | None],
    shipping_preparation_days: int,
    company_holidays: set[dt.date] | None = None,
) -> dt.date | None:
    """注文の配送予定日を計算する.

    Args:
        items_delivery_dates: 各商品の納品予定日リスト
        shipping_preparation_days: 発送準備日数
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        配送予定日。納品予定日が一つもない場合はNone
    """
    valid_dates = [d for d in items_delivery_dates if d is not None]
    if not valid_dates:
        return None

    max_delivery_date = max(valid_dates)
    return add_business_days(max_delivery_date, shipping_preparation_days, company_holidays)


async def get_shipping_preparation_days(
    setting_repo: AppSettingRepository,
) -> int:
    """発送準備日数を取得する."""
    setting = await setting_repo.find_by_key(SHIPPING_PREPARATION_DAYS_KEY)
    if setting:
        try:
            return int(setting.value)
        except ValueError:
            pass
    return SHIPPING_PREPARATION_DAYS_DEFAULT


async def recalculate_all_estimated_shipping_dates(
    db: AsyncSession,
    setting_repo: AppSettingRepository,
    holiday_repo: CompanyHolidayRepository,
) -> int:
    """未出荷注文の配送予定日を一括再計算する.

    Returns:
        更新された注文数
    """
    shipping_days = await get_shipping_preparation_days(setting_repo)
    company_holidays = await holiday_repo.find_all_dates()

    # 再計算対象の注文を取得
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.status.in_(RECALC_STATUSES))
    )
    orders = list(result.scalars().all())

    updated = 0
    for order in orders:
        delivery_dates = [item.expected_delivery_date for item in order.items]
        new_date = calculate_estimated_shipping_date(
            delivery_dates, shipping_days, company_holidays
        )
        if order.estimated_shipping_date != new_date:
            order.estimated_shipping_date = new_date
            updated += 1

    if updated > 0:
        await db.flush()

    logger.info(f"Recalculated estimated_shipping_date for {updated}/{len(orders)} orders")
    return updated
