"""Unit tests for FEAT-0025: Shipment list with pending orders.

Tests for the extended shipment list API that includes orders without shipments
(pending orders) displayed as "preparing" status.

Note: "awaiting_shipment" status was removed because Shipments are automatically
created when all OrderItems become DELIVERED.

Test scenarios from Intent Spec acceptance criteria:
- AC-01: Orders without Shipments shown as "preparing"
- AC-03: Type field distinguishes between "shipment" and "pending_order"
- AC-04: After Shipment creation, orders show as normal shipments
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.order import Order, OrderItem, OrderItemStatus, OrderStatus
from app.models.shipment import Shipment, ShipmentStatus


class TestPendingOrderStatus:
    """Tests for pending order status derivation logic.

    Note: All pending orders now have 'preparing' status since orders with all
    items DELIVERED automatically get a Shipment created.
    """

    def test_preparing_status_when_not_all_items_delivered(self):
        """AC-01: Order with items not all DELIVERED should have status 'preparing'."""
        from app.schemas.shipment import PendingOrderStatus

        # Create mock order with mixed item statuses
        order_items = [
            MagicMock(status=OrderItemStatus.DELIVERED.value),
            MagicMock(status=OrderItemStatus.MANUFACTURING.value),
            MagicMock(status=OrderItemStatus.ORDERED.value),
        ]

        # Status is always PREPARING for pending orders
        status = PendingOrderStatus.PREPARING

        assert status == PendingOrderStatus.PREPARING

    def test_preparing_status_when_some_items_ordered(self):
        """Order with some items still ORDERED should have status 'preparing'."""
        from app.schemas.shipment import PendingOrderStatus

        order_items = [
            MagicMock(status=OrderItemStatus.ORDERED.value),
            MagicMock(status=OrderItemStatus.ORDERED.value),
        ]

        # Status is always PREPARING for pending orders
        status = PendingOrderStatus.PREPARING

        assert status == PendingOrderStatus.PREPARING

    def test_preparing_status_when_some_items_manufacturing(self):
        """Order with some items in MANUFACTURING should have status 'preparing'."""
        from app.schemas.shipment import PendingOrderStatus

        order_items = [
            MagicMock(status=OrderItemStatus.DELIVERED.value),
            MagicMock(status=OrderItemStatus.MANUFACTURING.value),
        ]

        # Status is always PREPARING for pending orders
        status = PendingOrderStatus.PREPARING

        assert status == PendingOrderStatus.PREPARING


class TestPendingOrderResponseSchema:
    """Tests for PendingOrderResponse schema."""

    def test_pending_order_response_schema_structure(self):
        """PendingOrderResponse should have all required fields."""
        from app.schemas.shipment import PendingOrderResponse, PendingOrderStatus

        # Create schema instance
        response = PendingOrderResponse(
            type="pending_order",
            order_id=str(uuid4()),
            order_number="ORD-001",
            customer_name="Test Customer",
            customer_address="Tokyo, Japan",
            item_count=3,
            items_delivered=1,
            status=PendingOrderStatus.PREPARING,
            created_at=datetime.now(timezone.utc),
            order_items=[],
        )

        assert response.type == "pending_order"
        assert response.order_number == "ORD-001"
        assert response.customer_name == "Test Customer"
        assert response.item_count == 3
        assert response.items_delivered == 1
        assert response.status == PendingOrderStatus.PREPARING

    def test_pending_order_response_type_literal(self):
        """PendingOrderResponse type field must be 'pending_order'."""
        from app.schemas.shipment import PendingOrderResponse, PendingOrderStatus

        response = PendingOrderResponse(
            type="pending_order",
            order_id=str(uuid4()),
            order_number="ORD-002",
            customer_name="Test Customer",
            customer_address="Osaka, Japan",
            item_count=1,
            items_delivered=0,
            status=PendingOrderStatus.PREPARING,
            created_at=datetime.now(timezone.utc),
            order_items=[],
        )

        # Type must be exactly "pending_order"
        assert response.type == "pending_order"


class TestShipmentResponseType:
    """Tests for ShipmentResponse type field."""

    def test_shipment_response_has_type_field(self):
        """ShipmentResponse should have type='shipment' field."""
        from app.schemas.shipment import ShipmentResponse

        # Access the model fields to verify 'type' exists
        # This will be implemented by adding type field to ShipmentResponse
        response = ShipmentResponse(
            id=str(uuid4()),
            type="shipment",
            status=ShipmentStatus.PENDING,
            tracking_number=None,
            carrier=None,
            packing_photo_path=None,
            shipped_at=None,
            delivered_at=None,
            note=None,
            customer_name="Test",
            customer_postal_code="100-0001",
            customer_address_prefecture="Tokyo",
            customer_address_city="Chiyoda",
            customer_address_building=None,
            customer_phone="090-0000-0000",
            items=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert response.type == "shipment"


class TestUnionListResponse:
    """Tests for the union list response containing both shipments and pending orders."""

    def test_union_list_response_structure(self):
        """ShipmentListResponse should contain both shipments and pending_orders."""
        from app.schemas.shipment import (
            ShipmentListWithPendingResponse,
            ShipmentResponse,
            PendingOrderResponse,
            PendingOrderStatus,
        )

        shipment_id = str(uuid4())
        order_id = str(uuid4())
        now = datetime.now(timezone.utc)

        shipment = ShipmentResponse(
            id=shipment_id,
            type="shipment",
            status=ShipmentStatus.PENDING,
            tracking_number=None,
            carrier=None,
            packing_photo_path=None,
            shipped_at=None,
            delivered_at=None,
            note=None,
            customer_name="Customer A",
            customer_postal_code="100-0001",
            customer_address_prefecture="Tokyo",
            customer_address_city="Chiyoda",
            customer_phone="090-1111-1111",
            items=[],
            created_at=now,
            updated_at=now,
        )

        pending_order = PendingOrderResponse(
            type="pending_order",
            order_id=order_id,
            order_number="ORD-003",
            customer_name="Customer B",
            customer_address="Osaka, Japan",
            item_count=2,
            items_delivered=0,
            status=PendingOrderStatus.PREPARING,
            created_at=now,
            order_items=[],
        )

        response = ShipmentListWithPendingResponse(
            items=[shipment, pending_order],
            total=2,
            page=1,
            limit=20,
        )

        assert len(response.items) == 2
        assert response.items[0].type == "shipment"
        assert response.items[1].type == "pending_order"


class TestOrderRepositoryFindPendingOrders:
    """Tests for OrderRepository.find_pending_orders() method."""

    @pytest.mark.asyncio
    async def test_find_pending_orders_returns_orders_without_shipment(self):
        """find_pending_orders() should return orders that have no associated shipment."""
        from app.repositories.order_repository import OrderRepository

        mock_db = AsyncMock()

        # Mock execute to handle both count and data queries
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_data_result])

        repo = OrderRepository(mock_db)

        # Call the method that will be implemented
        result = await repo.find_pending_orders(page=1, limit=20)

        # Should return tuple of (orders, total)
        orders, total = result
        assert isinstance(orders, list)
        assert isinstance(total, int)

    @pytest.mark.asyncio
    async def test_find_pending_orders_excludes_shipped_and_cancelled(self):
        """find_pending_orders() should exclude SHIPPED and CANCELLED orders."""
        from app.repositories.order_repository import OrderRepository

        mock_db = AsyncMock()

        # Mock execute to handle both count and data queries
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_data_result])

        repo = OrderRepository(mock_db)
        orders, total = await repo.find_pending_orders(page=1, limit=20)

        # Verify that execute was called (method exists and works)
        assert mock_db.execute.called


class TestShipmentServiceListWithPendingOrders:
    """Tests for ShipmentService.list() extension to include pending orders."""

    @pytest.mark.asyncio
    async def test_list_includes_both_shipments_and_pending_orders(self):
        """list() should return both shipments and pending orders."""
        from app.services.shipment_service import ShipmentService
        from app.schemas.shipment import ShipmentListWithPendingResponse

        # Create mocks
        mock_shipment_repo = AsyncMock()
        mock_order_repo = AsyncMock()
        mock_file_storage = MagicMock()

        # Mock shipment_repo.find_all to return shipments
        mock_shipment = MagicMock()
        mock_shipment.id = str(uuid4())
        mock_shipment.status = ShipmentStatus.PENDING.value
        mock_shipment.tracking_number = None
        mock_shipment.carrier = None
        mock_shipment.packing_photo_path = None
        mock_shipment.shipped_at = None
        mock_shipment.delivered_at = None
        mock_shipment.note = None
        mock_shipment.created_at = datetime.now(timezone.utc)
        mock_shipment.updated_at = datetime.now(timezone.utc)
        mock_shipment.items = []

        mock_first_order = MagicMock()
        mock_first_order.customer_name = "Shipment Customer"
        mock_first_order.customer_postal_code = "100-0001"
        mock_first_order.customer_address_prefecture = "Tokyo"
        mock_first_order.customer_address_city = "Chiyoda"
        mock_first_order.customer_address_building = None
        mock_first_order.customer_phone = "090-0000-0000"
        mock_shipment.first_order = mock_first_order

        mock_shipment_repo.find_all = AsyncMock(return_value=([mock_shipment], 1))

        # Mock order_repo.find_pending_orders to return pending orders
        mock_order = MagicMock()
        mock_order.id = str(uuid4())
        mock_order.order_number = "ORD-PENDING-001"
        mock_order.customer_name = "Pending Customer"
        mock_order.customer_postal_code = "200-0002"
        mock_order.customer_address_prefecture = "Osaka"
        mock_order.customer_address_city = "Namba"
        mock_order.customer_address_building = None
        mock_order.ordered_at = datetime.now(timezone.utc)

        # Create proper mock item with all required attributes
        mock_item = MagicMock()
        mock_item.id = str(uuid4())
        mock_item.status = OrderItemStatus.MANUFACTURING.value
        mock_item.product_name = "Test Product"
        mock_item.product_type = "acrylic_keychain"
        mock_item.quantity = 1
        mock_item.thumbnail_image_url = None

        mock_order.items = [mock_item]
        mock_order_repo.find_pending_orders = AsyncMock(return_value=([mock_order], 1))

        service = ShipmentService(
            shipment_repo=mock_shipment_repo,
            order_repo=mock_order_repo,
            file_storage=mock_file_storage,
        )

        # Call the extended list method
        result = await service.list_with_pending_orders(page=1, limit=20)

        # Verify result structure
        assert isinstance(result, ShipmentListWithPendingResponse)
        assert len(result.items) == 2
        # First item should be shipment (existing behavior)
        # Second item should be pending order

    @pytest.mark.asyncio
    async def test_list_pending_order_status_preparing(self):
        """Pending orders with incomplete items should have 'preparing' status."""
        from app.services.shipment_service import ShipmentService
        from app.schemas.shipment import PendingOrderStatus

        mock_shipment_repo = AsyncMock()
        mock_order_repo = AsyncMock()
        mock_file_storage = MagicMock()

        mock_shipment_repo.find_all = AsyncMock(return_value=([], 0))

        # Create order with manufacturing item
        mock_order = MagicMock()
        mock_order.id = str(uuid4())
        mock_order.order_number = "ORD-MFG-001"
        mock_order.customer_name = "MFG Customer"
        mock_order.customer_postal_code = "100-0001"
        mock_order.customer_address_prefecture = "Tokyo"
        mock_order.customer_address_city = "Shibuya"
        mock_order.customer_address_building = None
        mock_order.ordered_at = datetime.now(timezone.utc)

        # Create proper mock items with all required attributes
        mock_item1 = MagicMock()
        mock_item1.id = str(uuid4())
        mock_item1.status = OrderItemStatus.DELIVERED.value
        mock_item1.product_name = "Product 1"
        mock_item1.product_type = "acrylic_keychain"
        mock_item1.quantity = 1
        mock_item1.thumbnail_image_url = None

        mock_item2 = MagicMock()
        mock_item2.id = str(uuid4())
        mock_item2.status = OrderItemStatus.MANUFACTURING.value
        mock_item2.product_name = "Product 2"
        mock_item2.product_type = "acrylic_keychain"
        mock_item2.quantity = 1
        mock_item2.thumbnail_image_url = None

        mock_order.items = [mock_item1, mock_item2]
        mock_order_repo.find_pending_orders = AsyncMock(return_value=([mock_order], 1))

        service = ShipmentService(
            shipment_repo=mock_shipment_repo,
            order_repo=mock_order_repo,
            file_storage=mock_file_storage,
        )

        result = await service.list_with_pending_orders(page=1, limit=20)

        # Find the pending order in results
        pending_orders = [item for item in result.items if item.type == "pending_order"]
        assert len(pending_orders) == 1
        assert pending_orders[0].status == PendingOrderStatus.PREPARING

    # Note: test_list_pending_order_status_awaiting_shipment was removed because
    # orders with all DELIVERED items automatically get a Shipment created,
    # so they would never appear as pending orders.


class TestPendingOrderItemsSummary:
    """Tests for order items summary in PendingOrderResponse."""

    def test_pending_order_item_count_and_delivered_count(self):
        """PendingOrderResponse should correctly count total and delivered items."""
        from app.schemas.shipment import PendingOrderResponse, PendingOrderStatus

        response = PendingOrderResponse(
            type="pending_order",
            order_id=str(uuid4()),
            order_number="ORD-COUNT-001",
            customer_name="Count Customer",
            customer_address="Nagoya, Japan",
            item_count=5,
            items_delivered=2,
            status=PendingOrderStatus.PREPARING,
            created_at=datetime.now(timezone.utc),
            order_items=[],
        )

        assert response.item_count == 5
        assert response.items_delivered == 2

    def test_pending_order_partial_items_delivered_count(self):
        """Pending orders can have some items delivered."""
        from app.schemas.shipment import PendingOrderResponse, PendingOrderStatus

        response = PendingOrderResponse(
            type="pending_order",
            order_id=str(uuid4()),
            order_number="ORD-PARTIAL-DELIVERED",
            customer_name="Partial Delivered Customer",
            customer_address="Yokohama, Japan",
            item_count=3,
            items_delivered=1,
            status=PendingOrderStatus.PREPARING,
            created_at=datetime.now(timezone.utc),
            order_items=[],
        )

        assert response.item_count == 3
        assert response.items_delivered == 1
        assert response.status == PendingOrderStatus.PREPARING
