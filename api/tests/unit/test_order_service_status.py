"""Unit tests for OrderService status transitions.

FEAT-0006: Order status manual switching functionality.
Tests cover all order status transition scenarios.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import pytest

from app.models.order import Order, OrderStatus
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.services.order_service import OrderService
from app.utils.exceptions import InvalidStatusTransitionError, ValidationError


@pytest.fixture
def mock_order_repo():
    """Mock order repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_product_repo():
    """Mock product repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_shipment_repo():
    """Mock shipment repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def order_service(mock_order_repo, mock_product_repo, mock_shipment_repo):
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
    order.order_number = "TEST-001"
    order.customer_name = "Test Customer"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "Tokyo"
    order.customer_address_city = "Chiyoda"
    order.customer_address_building = None
    order.customer_phone = "090-1234-5678"
    order.customer_email = "test@example.com"
    order.ordered_at = datetime.now(timezone.utc)
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
    order.created_at = datetime.now(timezone.utc)
    order.updated_at = datetime.now(timezone.utc)
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


class TestOrderStatusTransition:
    """Test order status transition functionality."""

    # ===========================================
    # Normal transitions (forward)
    # ===========================================

    @pytest.mark.asyncio
    async def test_ordered_to_manufacturing_success(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: ordered -> manufacturing is allowed."""
        # Arrange
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.MANUFACTURING,
        )

        # Assert
        assert order.status == OrderStatus.MANUFACTURING.value
        mock_order_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_manufacturing_to_ordered_success(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: manufacturing -> ordered is allowed (reverse transition)."""
        # Arrange
        order = create_mock_order(status=OrderStatus.MANUFACTURING.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.ORDERED,
        )

        # Assert
        assert order.status == OrderStatus.ORDERED.value
        mock_order_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_ordered_to_delivered_creates_shipment(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: ordered -> delivered creates shipment automatically."""
        # Arrange
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.exists_for_order.return_value = False
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.DELIVERED,
        )

        # Assert
        assert order.status == OrderStatus.DELIVERED.value
        mock_shipment_repo.create.assert_called_once_with(
            order_ids=["order-123"], estimated_shipping_date=None
        )

    @pytest.mark.asyncio
    async def test_manufacturing_to_delivered_creates_shipment(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: manufacturing -> delivered creates shipment automatically."""
        # Arrange
        order = create_mock_order(status=OrderStatus.MANUFACTURING.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.exists_for_order.return_value = False
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.DELIVERED,
        )

        # Assert
        assert order.status == OrderStatus.DELIVERED.value
        mock_shipment_repo.create.assert_called_once()

    # ===========================================
    # Reverse transitions (from delivered)
    # ===========================================

    @pytest.mark.asyncio
    async def test_delivered_to_ordered_deletes_shipment(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: delivered -> ordered deletes related shipment."""
        # Arrange
        order = create_mock_order(status=OrderStatus.DELIVERED.value)
        shipment = create_mock_shipment(status=ShipmentStatus.PENDING.value)

        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {"order-123": shipment}
        mock_shipment_repo.delete_by_order_id.return_value = None

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.ORDERED,
        )

        # Assert
        assert order.status == OrderStatus.ORDERED.value
        mock_shipment_repo.delete_by_order_id.assert_called_once_with("order-123")

    @pytest.mark.asyncio
    async def test_delivered_to_manufacturing_deletes_shipment(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: delivered -> manufacturing deletes related shipment."""
        # Arrange
        order = create_mock_order(status=OrderStatus.DELIVERED.value)
        shipment = create_mock_shipment(status=ShipmentStatus.PENDING.value)

        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {"order-123": shipment}
        mock_shipment_repo.delete_by_order_id.return_value = None

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.MANUFACTURING,
        )

        # Assert
        assert order.status == OrderStatus.MANUFACTURING.value
        mock_shipment_repo.delete_by_order_id.assert_called_once_with("order-123")

    # ===========================================
    # Invalid transitions
    # ===========================================

    @pytest.mark.asyncio
    async def test_cannot_transition_to_shipped_directly(
        self, order_service, mock_order_repo
    ):
        """Test: Direct transition to shipped is not allowed."""
        # Arrange
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order

        # Act & Assert
        with pytest.raises(InvalidStatusTransitionError):
            await order_service.update_status(
                order_id="order-123",
                status=OrderStatus.SHIPPED,
            )

    @pytest.mark.asyncio
    async def test_cannot_transition_from_delivered_when_shipment_is_shipped(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: Cannot go back from delivered when shipment is already shipped."""
        # Arrange
        order = create_mock_order(status=OrderStatus.DELIVERED.value)
        shipment = create_mock_shipment(status=ShipmentStatus.SHIPPED.value)

        mock_order_repo.find_by_id.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {"order-123": shipment}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await order_service.update_status(
                order_id="order-123",
                status=OrderStatus.ORDERED,
            )

        assert "shipped" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cannot_transition_from_shipped(
        self, order_service, mock_order_repo
    ):
        """Test: Cannot transition from shipped status."""
        # Arrange
        order = create_mock_order(status=OrderStatus.SHIPPED.value)
        mock_order_repo.find_by_id.return_value = order

        # Act & Assert
        with pytest.raises(InvalidStatusTransitionError):
            await order_service.update_status(
                order_id="order-123",
                status=OrderStatus.DELIVERED,
            )

    # ===========================================
    # Edge cases
    # ===========================================

    @pytest.mark.asyncio
    async def test_delivered_to_ordered_when_no_shipment_exists(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: delivered -> ordered when no shipment exists (no error)."""
        # Arrange
        order = create_mock_order(status=OrderStatus.DELIVERED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {}  # No shipment

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.ORDERED,
        )

        # Assert
        assert order.status == OrderStatus.ORDERED.value
        mock_shipment_repo.delete_by_order_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_status_transition_is_idempotent(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: Transitioning to the same status is allowed (idempotent)."""
        # Arrange
        order = create_mock_order(status=OrderStatus.MANUFACTURING.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.MANUFACTURING,
        )

        # Assert
        assert order.status == OrderStatus.MANUFACTURING.value

    @pytest.mark.asyncio
    async def test_to_delivered_does_not_duplicate_shipment(
        self, order_service, mock_order_repo, mock_shipment_repo
    ):
        """Test: Going to delivered when shipment already exists does not create duplicate."""
        # Arrange
        order = create_mock_order(status=OrderStatus.MANUFACTURING.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.exists_for_order.return_value = True  # Shipment already exists
        mock_shipment_repo.find_by_order_ids.return_value = {}

        # Act
        result = await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.DELIVERED,
        )

        # Assert
        assert order.status == OrderStatus.DELIVERED.value
        mock_shipment_repo.create.assert_not_called()
