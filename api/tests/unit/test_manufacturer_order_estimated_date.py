"""Test ManufacturerOrderService persists estimated_shipping_date on shipment creation."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderItem
from app.services.manufacturer_order_service import ManufacturerOrderService


@pytest.mark.asyncio
async def test_create_shipment_persists_estimated_shipping_date():
    """全OrderItem delivered時にShipment作成でestimated_shipping_dateが渡される."""
    order_repo = AsyncMock()
    manufacturer_repo = AsyncMock()
    shipment_repo = AsyncMock()
    settings_service = AsyncMock()

    settings_service.get_shipping_preparation_days_value = AsyncMock(return_value=5)
    settings_service.get_company_holiday_dates = AsyncMock(return_value=set())

    service = ManufacturerOrderService(
        order_repo=order_repo,
        manufacturer_repo=manufacturer_repo,
        shipment_repo=shipment_repo,
        settings_service=settings_service,
    )

    product = MagicMock()
    product.lead_time_days = 7

    order_item = MagicMock(spec=OrderItem)
    order_item.product = product

    order = MagicMock(spec=Order)
    order.id = "order-1"
    order.ordered_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order.items = [order_item]

    shipment_repo.exists_for_order = AsyncMock(return_value=False)
    shipment_repo.create = AsyncMock()

    result = await service._create_shipment_for_order(order)

    assert result is True
    shipment_repo.create.assert_called_once()
    call_kwargs = shipment_repo.create.call_args
    assert call_kwargs.kwargs.get("estimated_shipping_date") is not None
    assert isinstance(call_kwargs.kwargs["estimated_shipping_date"], date)


@pytest.mark.asyncio
async def test_create_shipment_without_settings_service():
    """settings_serviceがNoneの場合、estimated_shipping_dateはNone."""
    order_repo = AsyncMock()
    manufacturer_repo = AsyncMock()
    shipment_repo = AsyncMock()

    service = ManufacturerOrderService(
        order_repo=order_repo,
        manufacturer_repo=manufacturer_repo,
        shipment_repo=shipment_repo,
        settings_service=None,
    )

    product = MagicMock()
    product.lead_time_days = 7

    order_item = MagicMock(spec=OrderItem)
    order_item.product = product

    order = MagicMock(spec=Order)
    order.id = "order-1"
    order.ordered_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order.items = [order_item]

    shipment_repo.exists_for_order = AsyncMock(return_value=False)
    shipment_repo.create = AsyncMock()

    result = await service._create_shipment_for_order(order)

    assert result is True
    call_kwargs = shipment_repo.create.call_args
    assert call_kwargs.kwargs.get("estimated_shipping_date") is None
