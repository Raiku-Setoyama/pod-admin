"""Unit tests for OrderService bulk status update.

FEAT-0007: Order bulk status update functionality.
Tests cover bulk_update_status method with various scenarios.

NOTE: These tests are written in TDD Red phase - the implementation does not exist yet.
Tests will fail until the implementation is completed.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderStatus
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.services.order_service import OrderService
from app.utils.exceptions import ValidationError

# Import schemas - these will be created during implementation
try:
    from app.schemas.order import OrderBulkStatusUpdateResponse
except ImportError:
    # TDD Red phase: Schemas don't exist yet, create mock classes for testing structure
    from pydantic import BaseModel

    class OrderBulkStatusUpdateResponse(BaseModel):  # type: ignore[no-redef]  # import 失敗時のみ使うフォールバック
        """Mock schema for testing - will be replaced by actual implementation."""
        updated_count: int
        failed_count: int
        failed_ids: list[str]


@pytest.fixture
def mock_order_repo() -> Any:
    """Mock order repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_product_repo() -> Any:
    """Mock product repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_shipment_repo() -> Any:
    """Mock shipment repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def order_service(mock_order_repo: Any, mock_product_repo: Any, mock_shipment_repo: Any) -> Any:
    """Create OrderService with mocked dependencies."""
    return OrderService(
        order_repo=mock_order_repo,
        product_repo=mock_product_repo,
        shipment_repo=mock_shipment_repo,
    )


def create_mock_order(
    order_id: str = "order-123",
    status: str = OrderStatus.ORDERED.value,
) -> MagicMock:
    """Create a mock order object."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.status = status
    order.order_number = f"TEST-{order_id[:8]}"
    order.customer_name = "Test Customer"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "Tokyo"
    order.customer_address_city = "Chiyoda"
    order.customer_address_building = None
    order.customer_phone = "090-1234-5678"
    order.customer_email = "test@example.com"
    order.ordered_at = datetime.now(UTC)
    order.total_price = 1000
    order.items = []
    order.order_source = None
    order.order_source_id = None
    order.product_id = None
    order.product_name = None
    order.price = None
    order.quantity = None
    order.manufacturing_data_path = None
    order.manufacturing_data_filename = None
    order.manufacturing_data_size = None
    order.created_at = datetime.now(UTC)
    order.updated_at = datetime.now(UTC)
    return order


def create_mock_shipment(
    shipment_id: str = "shipment-123",
    status: str = ShipmentStatus.PENDING.value,
    order_ids: list[str] | None = None,
) -> MagicMock:
    """Create a mock shipment object."""
    shipment = MagicMock(spec=Shipment)
    shipment.id = shipment_id
    shipment.status = status
    shipment.tracking_number = None
    shipment.carrier = None
    shipment.shipped_at = None
    shipment.items = []

    if order_ids:
        for order_id in order_ids:
            item = MagicMock(spec=ShipmentItem)
            item.order_id = order_id
            shipment.items.append(item)

    return shipment


class TestOrderBulkStatusUpdate:
    """Test order bulk status update functionality."""

    # ===========================================
    # Basic bulk update (all success)
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_all_orders_to_manufacturing_success(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: Multiple orders from ordered to manufacturing all succeed."""
        # Arrange
        order_ids = ["order-1", "order-2", "order-3"]
        orders = {
            oid: create_mock_order(order_id=oid, status=OrderStatus.ORDERED.value)
            for oid in order_ids
        }

        async def find_by_id(order_id: Any) -> Any:
            return orders.get(order_id)

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.bulk_update_status(
            order_ids=order_ids,
            status=OrderStatus.MANUFACTURING,
        )

        # Assert
        assert result.updated_count == 3
        assert result.failed_count == 0
        assert result.failed_ids == []
        for order in orders.values():
            assert order.status == OrderStatus.MANUFACTURING.value

    @pytest.mark.asyncio
    async def test_bulk_update_all_orders_to_delivered_creates_shipments(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: Bulk update to delivered creates shipments for all orders."""
        # Arrange
        order_ids = ["order-1", "order-2"]
        orders = {
            oid: create_mock_order(order_id=oid, status=OrderStatus.MANUFACTURING.value)
            for oid in order_ids
        }

        async def find_by_id(order_id: Any) -> Any:
            return orders.get(order_id)

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}
        mock_shipment_repo.exists_for_order.return_value = False

        # Act
        result = await order_service.bulk_update_status(
            order_ids=order_ids,
            status=OrderStatus.DELIVERED,
        )

        # Assert
        assert result.updated_count == 2
        assert result.failed_count == 0
        # Shipment should be created for each order
        assert mock_shipment_repo.create.call_count == 2

    # ===========================================
    # Partial success (some fail)
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_partial_success_mixed_statuses(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: Mixed order statuses - only valid transitions succeed."""
        # Arrange: ordered and shipped orders mixed
        order_ordered = create_mock_order(
            order_id="order-ordered", status=OrderStatus.ORDERED.value
        )
        order_shipped = create_mock_order(
            order_id="order-shipped", status=OrderStatus.SHIPPED.value
        )

        orders = {
            "order-ordered": order_ordered,
            "order-shipped": order_shipped,
        }

        async def find_by_id(order_id: Any) -> Any:
            return orders.get(order_id)

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.bulk_update_status(
            order_ids=["order-ordered", "order-shipped"],
            status=OrderStatus.MANUFACTURING,
        )

        # Assert: Only ordered -> manufacturing succeeds, shipped cannot transition
        assert result.updated_count == 1
        assert result.failed_count == 1
        assert "order-shipped" in result.failed_ids

    @pytest.mark.asyncio
    async def test_bulk_update_partial_success_some_not_found(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: Some order IDs do not exist - only existing orders are updated."""
        # Arrange
        order_valid = create_mock_order(
            order_id="order-valid", status=OrderStatus.ORDERED.value
        )

        async def find_by_id(order_id: Any) -> Any:
            if order_id == "order-valid":
                return order_valid
            return None  # Not found

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.bulk_update_status(
            order_ids=["order-valid", "order-not-found"],
            status=OrderStatus.MANUFACTURING,
        )

        # Assert
        assert result.updated_count == 1
        assert result.failed_count == 1
        assert "order-not-found" in result.failed_ids

    # ===========================================
    # Invalid status transitions
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_to_shipped_rejected(
        self, order_service: Any, mock_order_repo: Any
    ) -> None:
        """Test: Bulk update to shipped status is rejected with 422 error."""
        # Arrange
        order_ids = ["order-1", "order-2"]

        # Act & Assert: shipped への直接遷移は拒否
        with pytest.raises(ValidationError) as exc_info:
            await order_service.bulk_update_status(
                order_ids=order_ids,
                status=OrderStatus.SHIPPED,
            )

        assert "shipped" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_bulk_update_from_shipped_all_fail(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: Orders in shipped status cannot be updated."""
        # Arrange
        order_ids = ["order-1", "order-2"]
        orders = {
            oid: create_mock_order(order_id=oid, status=OrderStatus.SHIPPED.value)
            for oid in order_ids
        }

        async def find_by_id(order_id: Any) -> Any:
            return orders.get(order_id)

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.bulk_update_status(
            order_ids=order_ids,
            status=OrderStatus.MANUFACTURING,
        )

        # Assert: All fail because shipped orders cannot transition
        assert result.updated_count == 0
        assert result.failed_count == 2
        assert set(result.failed_ids) == set(order_ids)

    # ===========================================
    # Delivered -> ordered/manufacturing (Shipment deletion)
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_delivered_to_ordered_deletes_shipments(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: delivered -> ordered deletes related shipments for all orders."""
        # Arrange
        order_ids = ["order-1", "order-2"]
        orders = {
            oid: create_mock_order(order_id=oid, status=OrderStatus.DELIVERED.value)
            for oid in order_ids
        }
        shipments = {
            oid: create_mock_shipment(
                shipment_id=f"shipment-{oid}",
                status=ShipmentStatus.PENDING.value,
            )
            for oid in order_ids
        }

        async def find_by_id(order_id: Any) -> Any:
            return orders.get(order_id)

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = shipments

        # Act
        result = await order_service.bulk_update_status(
            order_ids=order_ids,
            status=OrderStatus.ORDERED,
        )

        # Assert
        assert result.updated_count == 2
        assert result.failed_count == 0
        # Shipments should be deleted for each order
        assert mock_shipment_repo.delete_by_order_id.call_count == 2

    @pytest.mark.asyncio
    async def test_bulk_update_delivered_to_manufacturing_deletes_shipments(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: delivered -> manufacturing deletes related shipments."""
        # Arrange
        order_ids = ["order-1"]
        orders = {
            "order-1": create_mock_order(
                order_id="order-1", status=OrderStatus.DELIVERED.value
            )
        }
        shipments = {
            "order-1": create_mock_shipment(
                shipment_id="shipment-1", status=ShipmentStatus.READY.value
            )
        }

        mock_order_repo.find_by_id.return_value = orders["order-1"]
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = shipments

        # Act
        result = await order_service.bulk_update_status(
            order_ids=order_ids,
            status=OrderStatus.MANUFACTURING,
        )

        # Assert
        assert result.updated_count == 1
        mock_shipment_repo.delete_by_order_id.assert_called_once_with("order-1")

    @pytest.mark.asyncio
    async def test_bulk_update_delivered_with_shipped_shipment_fails(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: delivered -> ordered fails if shipment is already shipped."""
        # Arrange
        order = create_mock_order(
            order_id="order-1", status=OrderStatus.DELIVERED.value
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", status=ShipmentStatus.SHIPPED.value
        )

        mock_order_repo.find_by_id.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {"order-1": shipment}

        # Act
        result = await order_service.bulk_update_status(
            order_ids=["order-1"],
            status=OrderStatus.ORDERED,
        )

        # Assert: Fails because shipment is shipped
        assert result.updated_count == 0
        assert result.failed_count == 1
        assert "order-1" in result.failed_ids

    @pytest.mark.asyncio
    async def test_bulk_update_partial_delivered_shipped_shipment_mixed(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: delivered orders with mixed shipment statuses - only pending succeed."""
        # Arrange
        order_pending = create_mock_order(
            order_id="order-pending", status=OrderStatus.DELIVERED.value
        )
        order_shipped = create_mock_order(
            order_id="order-shipped", status=OrderStatus.DELIVERED.value
        )

        orders = {"order-pending": order_pending, "order-shipped": order_shipped}
        shipments = {
            "order-pending": create_mock_shipment(
                shipment_id="ship-pending", status=ShipmentStatus.PENDING.value
            ),
            "order-shipped": create_mock_shipment(
                shipment_id="ship-shipped", status=ShipmentStatus.SHIPPED.value
            ),
        }

        async def find_by_id(order_id: Any) -> Any:
            return orders.get(order_id)

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = shipments

        # Act
        result = await order_service.bulk_update_status(
            order_ids=["order-pending", "order-shipped"],
            status=OrderStatus.ORDERED,
        )

        # Assert
        assert result.updated_count == 1
        assert result.failed_count == 1
        assert "order-shipped" in result.failed_ids
        assert "order-pending" not in result.failed_ids

    # ===========================================
    # Empty order_ids validation
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_empty_order_ids_raises_validation_error(
        self, order_service: Any
    ) -> None:
        """Test: Empty order_ids list raises validation error."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await order_service.bulk_update_status(
                order_ids=[],
                status=OrderStatus.MANUFACTURING,
            )

        assert "order_ids" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()

    # ===========================================
    # Edge cases
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_idempotent_same_status(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: Updating to the same status is idempotent (still succeeds)."""
        # Arrange
        order = create_mock_order(
            order_id="order-1", status=OrderStatus.MANUFACTURING.value
        )

        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.bulk_update_status(
            order_ids=["order-1"],
            status=OrderStatus.MANUFACTURING,
        )

        # Assert: Same status transition is allowed (idempotent)
        assert result.updated_count == 1
        assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_bulk_update_to_delivered_does_not_duplicate_shipment(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: Going to delivered when shipment already exists does not create duplicate."""
        # Arrange
        order = create_mock_order(
            order_id="order-1", status=OrderStatus.MANUFACTURING.value
        )

        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}
        mock_shipment_repo.exists_for_order.return_value = True  # Shipment already exists

        # Act
        result = await order_service.bulk_update_status(
            order_ids=["order-1"],
            status=OrderStatus.DELIVERED,
        )

        # Assert
        assert result.updated_count == 1
        mock_shipment_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_update_large_batch(
        self, order_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """Test: Large batch of orders can be updated efficiently."""
        # Arrange: 100 orders
        order_ids = [f"order-{i}" for i in range(100)]
        orders = {
            oid: create_mock_order(order_id=oid, status=OrderStatus.ORDERED.value)
            for oid in order_ids
        }

        async def find_by_id(order_id: Any) -> Any:
            return orders.get(order_id)

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.bulk_update_status(
            order_ids=order_ids,
            status=OrderStatus.MANUFACTURING,
        )

        # Assert
        assert result.updated_count == 100
        assert result.failed_count == 0


class TestOrderBulkStatusUpdateResponse:
    """Test the response schema for bulk status update."""

    def test_response_schema_structure(self) -> None:
        """Test: Response schema has correct structure."""
        response = OrderBulkStatusUpdateResponse(
            updated_count=5,
            failed_count=2,
            failed_ids=["order-1", "order-2"],
        )

        assert response.updated_count == 5
        assert response.failed_count == 2
        assert len(response.failed_ids) == 2
        assert "order-1" in response.failed_ids

    def test_response_schema_all_success(self) -> None:
        """Test: Response schema with all success."""
        response = OrderBulkStatusUpdateResponse(
            updated_count=10,
            failed_count=0,
            failed_ids=[],
        )

        assert response.updated_count == 10
        assert response.failed_count == 0
        assert response.failed_ids == []

    def test_response_schema_all_failed(self) -> None:
        """Test: Response schema with all failed."""
        response = OrderBulkStatusUpdateResponse(
            updated_count=0,
            failed_count=3,
            failed_ids=["a", "b", "c"],
        )

        assert response.updated_count == 0
        assert response.failed_count == 3
        assert len(response.failed_ids) == 3
