"""Unit tests for OrderService.create() honoring the order deadline time.

〆切前後で expected_delivery_date / estimated_shipping_date が期待通りに変わり、
ordered_at（実受注時刻）は繰り下がらない（実時刻のまま）ことを検証する。
"""

from datetime import date
from datetime import datetime as dt
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.models.order import Order, OrderStatus
from app.models.product import Product, ProductType
from app.schemas.order import CustomerInfo, OrderCreate, OrderItemCreate
from app.services.estimated_shipping_service import SHIPPING_PREPARATION_DAYS_KEY
from app.services.order_deadline import ORDER_DEADLINE_TIME_KEY
from app.services.order_service import OrderService

JST = ZoneInfo("Asia/Tokyo")


def _setting(value: str) -> MagicMock:
    s = MagicMock()
    s.value = value
    return s


def _make_app_setting_repo(deadline_value: str | None) -> AsyncMock:
    async def find_by_key(key: str) -> Any:
        if key == ORDER_DEADLINE_TIME_KEY:
            return _setting(deadline_value) if deadline_value is not None else None
        if key == SHIPPING_PREPARATION_DAYS_KEY:
            return _setting("5")
        return None

    repo = AsyncMock()
    repo.find_by_key = AsyncMock(side_effect=find_by_key)
    return repo


def _stamp_and_return(order: Order) -> Order:
    """DB flush 相当のデフォルト（id/status/timestamps）を付与して返す."""
    now = dt(2026, 1, 1, tzinfo=JST)
    order.id = "order-1"
    order.status = OrderStatus.ORDERED.value
    order.created_at = now
    order.updated_at = now
    for idx, item in enumerate(order.items):
        item.id = f"item-{idx}"
        if item.status is None:
            item.status = OrderStatus.ORDERED.value
        item.created_at = now
        item.updated_at = now
    return order


def _make_order_service(deadline_value: str | None) -> tuple[OrderService, AsyncMock]:
    order_repo = AsyncMock()
    order_repo.find_by_order_number = AsyncMock(return_value=None)
    order_repo.create = AsyncMock(side_effect=lambda order: _stamp_and_return(order))

    product = MagicMock(spec=Product)
    product.id = "prod-1"
    product.lead_time_days = 3
    product_repo = AsyncMock()
    product_repo.find_by_product_type = AsyncMock(return_value=product)

    shipment_repo = AsyncMock()
    shipment_repo.find_by_order_ids = AsyncMock(return_value={})

    company_holiday_repo = AsyncMock()
    company_holiday_repo.find_all_dates = AsyncMock(return_value=set())

    app_setting_repo = _make_app_setting_repo(deadline_value)

    service = OrderService(
        order_repo=order_repo,
        product_repo=product_repo,
        shipment_repo=shipment_repo,
        company_holiday_repo=company_holiday_repo,
        app_setting_repo=app_setting_repo,
    )
    return service, order_repo


def _order_create() -> OrderCreate:
    return OrderCreate(
        order_number="0000001",
        customer=CustomerInfo(
            name="山田太郎",
            postal_code="100-0001",
            address_prefecture="東京都",
            address_city="千代田区1-1",
            phone="090-1234-5678",
        ),
        items=[
            OrderItemCreate(
                uid="0000001",
                product_type=ProductType.TSHIRT,
                product_name="オリジナルTシャツ",
                price=3000,
                quantity=1,
                size="M",
                color="白",
                position="正面",
            )
        ],
    )


async def _create_at(now_jst: dt, deadline_value: str | None) -> Any:
    service, order_repo = _make_order_service(deadline_value)
    with patch("app.services.order_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = now_jst
        await service.create(_order_create())
    return order_repo.create.call_args.args[0]


@pytest.mark.asyncio
class TestOrderServiceDeadline:
    async def test_before_deadline_uses_same_day(self) -> None:
        # 2026-07-09(木) 17:30、〆切 18:00 → 起算日 7/9 → 納品予定日 7/14(火)
        now = dt(2026, 7, 9, 17, 30, tzinfo=JST)
        order = await _create_at(now, "18:00")

        assert order.items[0].expected_delivery_date == date(2026, 7, 14)
        # 配送予定日 = add_business_days(7/14, 5) = 7/22(水)（土日と 7/20 海の日をスキップ）
        assert order.estimated_shipping_date == date(2026, 7, 22)
        # ordered_at は実受注時刻のまま
        assert order.ordered_at == now

    async def test_after_deadline_defers_to_next_business_day(self) -> None:
        # 2026-07-09(木) 18:05、〆切 18:00 → 起算日 7/10(金) → 納品予定日 7/15(水)
        now = dt(2026, 7, 9, 18, 5, tzinfo=JST)
        order = await _create_at(now, "18:00")

        assert order.items[0].expected_delivery_date == date(2026, 7, 15)
        # 配送予定日 = add_business_days(7/15, 5) = 7/23(木)（土日と 7/20 海の日をスキップ）
        assert order.estimated_shipping_date == date(2026, 7, 23)
        # ordered_at は繰り下げない（実受注時刻のまま）
        assert order.ordered_at == now

    async def test_no_deadline_uses_same_day(self) -> None:
        # 〆切未設定（空文字）→ 常に当日起算（後方互換）
        now = dt(2026, 7, 9, 23, 0, tzinfo=JST)
        order = await _create_at(now, "")

        assert order.items[0].expected_delivery_date == date(2026, 7, 14)
        assert order.ordered_at == now

    async def test_deadline_setting_absent_uses_same_day(self) -> None:
        # 設定キー自体が無い（find_by_key が None）→ 当日起算
        now = dt(2026, 7, 9, 23, 0, tzinfo=JST)
        order = await _create_at(now, None)

        assert order.items[0].expected_delivery_date == date(2026, 7, 14)
