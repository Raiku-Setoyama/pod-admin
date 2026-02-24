"""Unit tests for ShipmentService status transitions.

FEAT-0006: Shipment status manual switching functionality.
Tests cover all shipment status transition scenarios including
bidirectional transitions and order status synchronization.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import pytest

from app.models.order import Order, OrderStatus
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.schemas.shipment import ShipmentStatusUpdate
from app.services.shipment_service import ShipmentService
from app.utils.exceptions import InvalidStatusTransitionError


@pytest.fixture
def mock_shipment_repo():
    """Mock shipment repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_order_repo():
    """Mock order repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_file_storage():
    """Mock file storage."""
    storage = AsyncMock()
    return storage


@pytest.fixture
def shipment_service(mock_shipment_repo, mock_order_repo, mock_file_storage):
    """Create ShipmentService with mocked dependencies."""
    return ShipmentService(
        shipment_repo=mock_shipment_repo,
        order_repo=mock_order_repo,
        file_storage=mock_file_storage,
    )


def create_mock_order(
    order_id: str = "order-123",
    status: str = OrderStatus.DELIVERED.value,
) -> MagicMock:
    """Create a mock order object."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.status = status
    order.order_number = "TEST-001"
    order.product_name = "Test Product"
    order.customer_name = "Test Customer"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "Tokyo"
    order.customer_address_city = "Chiyoda"
    order.customer_address_building = None
    order.customer_phone = "090-1234-5678"
    # items attribute for _to_response() product_name resolution (FEAT-0014)
    item = MagicMock()
    item.product_name = "Test Product"
    order.items = [item]
    return order


def create_mock_shipment(
    shipment_id: str = "shipment-123",
    status: str = ShipmentStatus.PENDING.value,
    order_ids: list[str] | None = None,
    shipped_at: datetime | None = None,
) -> MagicMock:
    """Create a mock shipment object."""
    shipment = MagicMock(spec=Shipment)
    shipment.id = shipment_id
    shipment.status = status
    shipment.tracking_number = None
    shipment.carrier = None
    shipment.packing_photo_path = None
    shipment.shipped_at = shipped_at
    shipment.delivered_at = None
    shipment.note = None
    shipment.created_at = datetime.now(timezone.utc)
    shipment.updated_at = datetime.now(timezone.utc)
    shipment.items = []

    if order_ids:
        for order_id in order_ids:
            item = MagicMock(spec=ShipmentItem)
            item.id = f"item-{order_id}"
            item.order_id = order_id
            item.order = create_mock_order(order_id)
            shipment.items.append(item)

    # Set first_order property
    if shipment.items:
        shipment.first_order = shipment.items[0].order
    else:
        shipment.first_order = None

    return shipment


class TestShipmentStatusTransition:
    """Test shipment status transition functionality."""

    # ===========================================
    # Normal forward transitions
    # ===========================================

    @pytest.mark.asyncio
    async def test_pending_to_ready_success(
        self, shipment_service, mock_shipment_repo
    ):
        """Test: pending -> ready is allowed."""
        # Arrange
        shipment = create_mock_shipment(status=ShipmentStatus.PENDING.value)
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(status=ShipmentStatus.READY)

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.status == ShipmentStatus.READY.value
        mock_shipment_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_ready_to_pending_success(
        self, shipment_service, mock_shipment_repo
    ):
        """Test: ready -> pending is allowed (reverse transition)."""
        # Arrange
        shipment = create_mock_shipment(status=ShipmentStatus.READY.value)
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(status=ShipmentStatus.PENDING)

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.status == ShipmentStatus.PENDING.value
        mock_shipment_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_pending_to_shipped_success(
        self, shipment_service, mock_shipment_repo, mock_order_repo
    ):
        """Test: pending -> shipped is allowed, sets shipped_at and updates orders."""
        # Arrange
        order_ids = ["order-123", "order-456"]
        shipment = create_mock_shipment(
            status=ShipmentStatus.PENDING.value,
            order_ids=order_ids,
        )
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(status=ShipmentStatus.SHIPPED)

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.status == ShipmentStatus.SHIPPED.value
        assert shipment.shipped_at is not None
        # All related orders should be updated to SHIPPED
        assert mock_order_repo.update_status.call_count == len(order_ids)

    @pytest.mark.asyncio
    async def test_ready_to_shipped_success(
        self, shipment_service, mock_shipment_repo, mock_order_repo
    ):
        """Test: ready -> shipped is allowed, sets shipped_at and updates orders."""
        # Arrange
        order_ids = ["order-123"]
        shipment = create_mock_shipment(
            status=ShipmentStatus.READY.value,
            order_ids=order_ids,
        )
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(status=ShipmentStatus.SHIPPED)

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.status == ShipmentStatus.SHIPPED.value
        assert shipment.shipped_at is not None
        mock_order_repo.update_status.assert_called_once_with(
            "order-123", OrderStatus.SHIPPED
        )

    # ===========================================
    # Reverse transitions (from shipped)
    # ===========================================

    @pytest.mark.asyncio
    async def test_shipped_to_pending_success(
        self, shipment_service, mock_shipment_repo, mock_order_repo
    ):
        """Test: shipped -> pending clears shipped_at and reverts order status to delivered."""
        # Arrange
        order_ids = ["order-123"]
        shipment = create_mock_shipment(
            status=ShipmentStatus.SHIPPED.value,
            order_ids=order_ids,
            shipped_at=datetime.now(timezone.utc),
        )
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(status=ShipmentStatus.PENDING)

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.status == ShipmentStatus.PENDING.value
        assert shipment.shipped_at is None
        mock_order_repo.update_status.assert_called_once_with(
            "order-123", OrderStatus.DELIVERED
        )

    @pytest.mark.asyncio
    async def test_shipped_to_ready_success(
        self, shipment_service, mock_shipment_repo, mock_order_repo
    ):
        """Test: shipped -> ready clears shipped_at and reverts order status to delivered."""
        # Arrange
        order_ids = ["order-123", "order-456"]
        shipment = create_mock_shipment(
            status=ShipmentStatus.SHIPPED.value,
            order_ids=order_ids,
            shipped_at=datetime.now(timezone.utc),
        )
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(status=ShipmentStatus.READY)

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.status == ShipmentStatus.READY.value
        assert shipment.shipped_at is None
        # All related orders should be reverted to DELIVERED
        assert mock_order_repo.update_status.call_count == len(order_ids)
        for call_args in mock_order_repo.update_status.call_args_list:
            assert call_args[0][1] == OrderStatus.DELIVERED

    # ===========================================
    # Multiple orders in one shipment
    # ===========================================

    @pytest.mark.asyncio
    async def test_shipped_to_pending_updates_all_orders(
        self, shipment_service, mock_shipment_repo, mock_order_repo
    ):
        """Test: When multiple orders in shipment, all are updated on status change."""
        # Arrange
        order_ids = ["order-1", "order-2", "order-3"]
        shipment = create_mock_shipment(
            status=ShipmentStatus.SHIPPED.value,
            order_ids=order_ids,
            shipped_at=datetime.now(timezone.utc),
        )
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(status=ShipmentStatus.PENDING)

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert mock_order_repo.update_status.call_count == 3
        called_order_ids = [call[0][0] for call in mock_order_repo.update_status.call_args_list]
        assert set(called_order_ids) == set(order_ids)

    # ===========================================
    # Additional fields on status update
    # ===========================================

    @pytest.mark.asyncio
    async def test_tracking_number_updated_on_transition(
        self, shipment_service, mock_shipment_repo, mock_order_repo
    ):
        """Test: Tracking number can be set during status update."""
        # Arrange
        shipment = create_mock_shipment(
            status=ShipmentStatus.READY.value,
            order_ids=["order-123"],
        )
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(
            status=ShipmentStatus.SHIPPED,
            tracking_number="1234567890",
            carrier="Yamato",
        )

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.tracking_number == "1234567890"
        assert shipment.carrier == "Yamato"

    @pytest.mark.asyncio
    async def test_note_updated_on_transition(
        self, shipment_service, mock_shipment_repo
    ):
        """Test: Note can be set during status update."""
        # Arrange
        shipment = create_mock_shipment(status=ShipmentStatus.PENDING.value)
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(
            status=ShipmentStatus.READY,
            note="Ready for pickup",
        )

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.note == "Ready for pickup"

    # ===========================================
    # Validation of bidirectional transitions
    # ===========================================

    @pytest.mark.asyncio
    async def test_all_transitions_allowed(
        self, shipment_service, mock_shipment_repo, mock_order_repo
    ):
        """Test: All status transitions are allowed in the new bidirectional model."""
        transitions = [
            (ShipmentStatus.PENDING, ShipmentStatus.READY),
            (ShipmentStatus.READY, ShipmentStatus.PENDING),
            (ShipmentStatus.PENDING, ShipmentStatus.SHIPPED),
            (ShipmentStatus.READY, ShipmentStatus.SHIPPED),
            (ShipmentStatus.SHIPPED, ShipmentStatus.PENDING),
            (ShipmentStatus.SHIPPED, ShipmentStatus.READY),
        ]

        for from_status, to_status in transitions:
            # Arrange
            shipment = create_mock_shipment(
                shipment_id=f"shipment-{from_status.value}-{to_status.value}",
                status=from_status.value,
                order_ids=["order-123"],
                shipped_at=datetime.now(timezone.utc) if from_status == ShipmentStatus.SHIPPED else None,
            )
            mock_shipment_repo.find_by_id.return_value = shipment
            mock_shipment_repo.update.return_value = shipment

            update_data = ShipmentStatusUpdate(status=to_status)

            # Act - should not raise
            result = await shipment_service.update_status(
                shipment_id=shipment.id,
                data=update_data,
            )

            # Assert
            assert shipment.status == to_status.value

    # ===========================================
    # Edge cases
    # ===========================================

    @pytest.mark.asyncio
    async def test_same_status_transition_is_idempotent(
        self, shipment_service, mock_shipment_repo
    ):
        """Test: Transitioning to the same status is allowed (idempotent)."""
        # Arrange
        shipment = create_mock_shipment(status=ShipmentStatus.READY.value)
        mock_shipment_repo.find_by_id.return_value = shipment
        mock_shipment_repo.update.return_value = shipment

        update_data = ShipmentStatusUpdate(status=ShipmentStatus.READY)

        # Act
        result = await shipment_service.update_status(
            shipment_id="shipment-123",
            data=update_data,
        )

        # Assert
        assert shipment.status == ShipmentStatus.READY.value
        mock_shipment_repo.update.assert_called_once()
