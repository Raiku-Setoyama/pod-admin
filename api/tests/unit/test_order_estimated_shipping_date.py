"""Test estimated_shipping_date is persisted when OrderService creates a shipment."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderItem, OrderStatus
from app.services.order_service import OrderService


def _make_order(ordered_at: datetime, lead_time_days: int = 10) -> MagicMock:
    """Create a mock Order with items."""
    order_item = MagicMock(spec=OrderItem)
    order_item.expected_delivery_date = ordered_at.date() + timedelta(days=lead_time_days)

    order = MagicMock(spec=Order)
    order.id = "order-1"
    order.status = OrderStatus.DELIVERED.value
    order.ordered_at = ordered_at
    order.items = [order_item]
    return order


@pytest.mark.asyncio
async def test_create_shipment_persists_estimated_shipping_date():
    """delivered時にShipment作成で estimated_shipping_date が渡される."""
    order_repo = AsyncMock()
    product_repo = AsyncMock()
    shipment_repo = AsyncMock()
    settings_service = AsyncMock()

    settings_service.get_shipping_preparation_days_value = AsyncMock(return_value=5)
    settings_service.get_company_holiday_dates = AsyncMock(return_value=set())

    service = OrderService(
        order_repo=order_repo,
        product_repo=product_repo,
        shipment_repo=shipment_repo,
        settings_service=settings_service,
    )

    ordered_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order = _make_order(ordered_at=ordered_at, lead_time_days=10)

    shipment_repo.exists_for_order = AsyncMock(return_value=False)
    shipment_repo.create = AsyncMock()

    await service._create_shipment_for_order(order)

    shipment_repo.create.assert_called_once()
    call_kwargs = shipment_repo.create.call_args
    assert call_kwargs.kwargs.get("estimated_shipping_date") is not None
    assert isinstance(call_kwargs.kwargs["estimated_shipping_date"], date)


@pytest.mark.asyncio
async def test_create_shipment_without_settings_service():
    """settings_serviceがNoneの場合、estimated_shipping_dateはNone."""
    order_repo = AsyncMock()
    product_repo = AsyncMock()
    shipment_repo = AsyncMock()

    service = OrderService(
        order_repo=order_repo,
        product_repo=product_repo,
        shipment_repo=shipment_repo,
        settings_service=None,
    )

    ordered_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order = _make_order(ordered_at=ordered_at, lead_time_days=10)

    shipment_repo.exists_for_order = AsyncMock(return_value=False)
    shipment_repo.create = AsyncMock()

    await service._create_shipment_for_order(order)

    shipment_repo.create.assert_called_once()
    call_kwargs = shipment_repo.create.call_args
    assert call_kwargs.kwargs.get("estimated_shipping_date") is None
