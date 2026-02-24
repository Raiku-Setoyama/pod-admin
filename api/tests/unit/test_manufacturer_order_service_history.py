"""Unit tests for ManufacturerOrderService status history recording.

FEAT-0014: AC-011
Tests verify that ManufacturerOrderService records status history
with changed_by="システム（メーカー発注）" when updating statuses.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.manufacturer_order_service import ManufacturerOrderService
from app.models.order import Order, OrderStatus


def _make_order_item(
    *,
    order_number: str = "POD-20260101-0001",
    uid: str = "abc123",
    product_name: str = "Tシャツ - M - 正面 - 白",
    product_type: str = "tshirt",
    quantity: int = 1,
    size: str = "M",
    position: str = "正面",
    color: str = "白",
    design_image_url: str | None = None,
    thumbnail_image_url: str | None = None,
    status: OrderStatus = OrderStatus.ORDERED,
    cost: int = 1000,
    ordered_at: datetime | None = None,
) -> tuple:
    """Create a mock order item tuple matching the repository return format."""
    order_item = MagicMock()
    order_item.id = str(uuid4())
    order_item.order_id = str(uuid4())
    order_item.uid = uid
    order_item.product_name = product_name
    order_item.product_type = product_type
    order_item.quantity = quantity
    order_item.size = size
    order_item.position = position
    order_item.color = color
    order_item.design_image_url = design_image_url
    order_item.thumbnail_image_url = thumbnail_image_url

    order = MagicMock()
    order.id = order_item.order_id
    order.order_number = order_number
    order.status = status.value
    order_item.order = order

    return (
        order_item,
        order_number,
        ordered_at or datetime(2026, 2, 24, 10, 0, 0),
        "顧客名",
        cost,
        status.value,
    )


class TestManufacturerOrderServiceStatusHistory:
    """Tests for status history recording in ManufacturerOrderService."""

    @pytest.fixture
    def mock_order_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_shipment_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_status_history_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_repo, mock_manufacturer_repo, mock_shipment_repo, mock_status_history_repo):
        return ManufacturerOrderService(
            order_repo=mock_order_repo,
            manufacturer_repo=mock_manufacturer_repo,
            shipment_repo=mock_shipment_repo,
            status_history_repo=mock_status_history_repo,
        )

    @pytest.fixture
    def mock_manufacturer(self):
        manufacturer = MagicMock()
        manufacturer.id = str(uuid4())
        manufacturer.name = "テストメーカー"
        return manufacturer

    @pytest.mark.asyncio
    async def test_update_order_status_records_history_with_system_manufacturer(
        self,
        service,
        mock_order_repo,
        mock_manufacturer_repo,
        mock_status_history_repo,
        mock_manufacturer,
    ):
        """AC-011: ManufacturerOrderService records changed_by="システム（メーカー発注）".

        given: Manufacturer status update is executed
        when: ManufacturerOrderService.update_order_status is called
        then: History records have changed_by="システム（メーカー発注）"
        """
        from app.schemas.manufacturer import ManufacturerOrderStatusUpdate

        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        # Mock updated orders
        mock_order_1 = MagicMock(spec=Order)
        mock_order_1.id = "order-1"
        mock_order_1.status = OrderStatus.ORDERED.value
        mock_order_2 = MagicMock(spec=Order)
        mock_order_2.id = "order-2"
        mock_order_2.status = OrderStatus.ORDERED.value

        mock_order_repo.update_status_by_manufacturer.return_value = [mock_order_1, mock_order_2]

        data = ManufacturerOrderStatusUpdate(
            status="manufacturing",
            order_item_ids=None,
        )

        await service.update_order_status(
            manufacturer_id=mock_manufacturer.id,
            data=data,
        )

        # Verify history records were created with correct changed_by
        assert mock_status_history_repo.create.call_count == 2
        for call in mock_status_history_repo.create.call_args_list:
            history_record = call[0][0]
            assert history_record.changed_by == "システム（メーカー発注）"
            assert history_record.to_status == "manufacturing"

    @pytest.mark.asyncio
    async def test_generate_order_documents_records_history(
        self,
        service,
        mock_order_repo,
        mock_manufacturer_repo,
        mock_status_history_repo,
        mock_manufacturer,
    ):
        """AC-011: generate_order_documents records status history.

        given: Manufacturer downloads order documents
        when: generate_order_documents is called (which updates status to manufacturing)
        then: History records are created with changed_by="システム（メーカー発注）"
        """
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        items = [
            _make_order_item(
                order_number="ORD-1",
                uid="UID-1",
                product_name="商品1",
                design_image_url=None,
                thumbnail_image_url=None,
            ),
        ]
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = items

        # Mock updated orders from status update
        mock_updated_orders = [MagicMock(spec=Order)]
        mock_updated_orders[0].id = items[0][0].order_id
        mock_updated_orders[0].status = OrderStatus.ORDERED.value
        mock_order_repo.update_status_by_manufacturer.return_value = mock_updated_orders

        with patch.object(service, '_download_file', return_value=(None, "")):
            zip_bytes, filename = await service.generate_order_documents(
                manufacturer_id=mock_manufacturer.id,
            )

        # Verify history was recorded
        assert mock_status_history_repo.create.call_count >= 1
        for call in mock_status_history_repo.create.call_args_list:
            history_record = call[0][0]
            assert history_record.changed_by == "システム（メーカー発注）"
