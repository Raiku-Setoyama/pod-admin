"""Test that ShipmentService uses DB value for estimated_shipping_date."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.schemas.shipment import PendingOrderStatus
from app.services.shipment_service import ShipmentService


def _make_shipment(estimated_date: date | None = None) -> MagicMock:
    """Create a mock Shipment with estimated_shipping_date."""
    order = MagicMock()
    order.id = "order-1"
    order.order_number = "ORD-001"
    order.customer_name = "テスト太郎"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "東京都"
    order.customer_address_city = "千代田区"
    order.customer_address_building = None
    order.customer_phone = "03-1234-5678"

    order_item = MagicMock()
    order_item.id = "oi-1"
    order_item.product_name = "テスト商品"
    order_item.quantity = 1
    order_item.thumbnail_image_url = None
    order.items = [order_item]

    item = MagicMock(spec=ShipmentItem)
    item.id = "item-1"
    item.order_id = "order-1"
    item.order = order

    shipment = MagicMock(spec=Shipment)
    shipment.id = "ship-1"
    shipment.status = ShipmentStatus.PENDING.value
    shipment.tracking_number = None
    shipment.carrier = None
    shipment.packing_photo_path = None
    shipment.shipped_at = None
    shipment.delivered_at = None
    shipment.note = None
    shipment.created_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    shipment.updated_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    shipment.estimated_shipping_date = estimated_date
    shipment.items = [item]
    shipment.first_order = order
    return shipment


@pytest.mark.asyncio
async def test_list_shipment_uses_db_estimated_date():
    """Shipmentの納品予定日はDBの値をそのまま返す."""
    shipment_repo = AsyncMock()
    order_repo = AsyncMock()
    file_storage = MagicMock()
    settings_service = AsyncMock()

    shipment = _make_shipment(estimated_date=date(2026, 4, 20))
    shipment_repo.find_all = AsyncMock(return_value=([shipment], 1))
    order_repo.find_pending_orders = AsyncMock(return_value=([], 0))

    service = ShipmentService(
        shipment_repo=shipment_repo,
        order_repo=order_repo,
        file_storage=file_storage,
        settings_service=settings_service,
    )

    result = await service.list_with_pending_orders()

    assert result.items[0].estimated_shipping_date == date(2026, 4, 20)
    # settings_service should NOT be called for calculation
    settings_service.get_shipping_preparation_days_value.assert_not_called()


@pytest.mark.asyncio
async def test_pending_order_has_null_estimated_date():
    """Pending orderの納品予定日はNone（フロントで「-」表示）."""
    shipment_repo = AsyncMock()
    order_repo = AsyncMock()
    file_storage = MagicMock()
    settings_service = AsyncMock()

    order = MagicMock()
    order.id = "order-1"
    order.order_number = "ORD-001"
    order.customer_name = "テスト太郎"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "東京都"
    order.customer_address_city = "千代田区"
    order.customer_address_building = None
    order.customer_phone = "03-1234-5678"
    order.ordered_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order.created_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order.items = []

    shipment_repo.find_all = AsyncMock(return_value=([], 0))
    order_repo.find_pending_orders = AsyncMock(return_value=([order], 1))

    service = ShipmentService(
        shipment_repo=shipment_repo,
        order_repo=order_repo,
        file_storage=file_storage,
        settings_service=settings_service,
    )

    result = await service.list_with_pending_orders(
        pending_order_status=PendingOrderStatus.PREPARING,
    )

    assert result.items[0].estimated_shipping_date is None
    # settings_service should NOT be called
    settings_service.get_shipping_preparation_days_value.assert_not_called()
