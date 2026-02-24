"""Unit tests for OrderService status history recording.

FEAT-0014: Tests verify that OrderService records status history
when creating orders, updating status (single and bulk).
"""

from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import pytest

from app.models.order import Order, OrderStatus
from app.models.shipment import Shipment, ShipmentStatus
from app.services.order_service import OrderService
from app.schemas.order import OrderBulkStatusUpdateResponse


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
def mock_status_history_repo():
    """Mock status history repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def order_service(mock_order_repo, mock_product_repo, mock_shipment_repo, mock_status_history_repo):
    """Create OrderService with mocked dependencies including status_history_repo."""
    return OrderService(
        order_repo=mock_order_repo,
        product_repo=mock_product_repo,
        shipment_repo=mock_shipment_repo,
        status_history_repo=mock_status_history_repo,
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


class TestOrderServiceStatusHistoryRecording:
    """Test that OrderService records status history on status changes."""

    @pytest.mark.asyncio
    async def test_update_status_records_history(
        self, order_service, mock_order_repo, mock_shipment_repo, mock_status_history_repo
    ):
        """Test: update_status records a status history entry.

        given: An order in 'ordered' status
        when: update_status is called to change to 'manufacturing'
        then: A status history record is created with from_status=ordered, to_status=manufacturing
        """
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {}

        await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.MANUFACTURING,
        )

        # Verify history was recorded
        mock_status_history_repo.create.assert_called_once()
        history_record = mock_status_history_repo.create.call_args[0][0]
        assert history_record.order_id == "order-123"
        assert history_record.from_status == OrderStatus.ORDERED.value
        assert history_record.to_status == OrderStatus.MANUFACTURING.value

    @pytest.mark.asyncio
    async def test_update_status_records_history_with_changed_by(
        self, order_service, mock_order_repo, mock_shipment_repo, mock_status_history_repo
    ):
        """Test: update_status records changed_by when provided.

        given: An order and a user name
        when: update_status is called with changed_by parameter
        then: The history record contains the user name
        """
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order
        mock_shipment_repo.find_by_order_ids.return_value = {}

        await order_service.update_status(
            order_id="order-123",
            status=OrderStatus.MANUFACTURING,
            changed_by="Test Admin",
        )

        mock_status_history_repo.create.assert_called_once()
        history_record = mock_status_history_repo.create.call_args[0][0]
        assert history_record.changed_by == "Test Admin"

    @pytest.mark.asyncio
    async def test_bulk_update_status_records_history_for_each_order(
        self, order_service, mock_order_repo, mock_shipment_repo, mock_status_history_repo
    ):
        """Test: bulk_update_status records history for each successfully updated order.

        given: 3 orders in 'ordered' status
        when: bulk_update_status changes them to 'manufacturing'
        then: 3 status history records are created
        """
        order_ids = ["order-1", "order-2", "order-3"]
        orders = {
            oid: create_mock_order(order_id=oid, status=OrderStatus.ORDERED.value)
            for oid in order_ids
        }

        async def find_by_id(order_id):
            return orders.get(order_id)

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}

        result = await order_service.bulk_update_status(
            order_ids=order_ids,
            status=OrderStatus.MANUFACTURING,
        )

        assert result.updated_count == 3
        assert mock_status_history_repo.create.call_count == 3

    @pytest.mark.asyncio
    async def test_bulk_update_status_does_not_record_history_for_failed(
        self, order_service, mock_order_repo, mock_shipment_repo, mock_status_history_repo
    ):
        """Test: bulk_update_status does not record history for failed orders.

        given: 1 valid order and 1 non-existent order
        when: bulk_update_status is called
        then: Only 1 history record is created (for the valid order)
        """
        order_valid = create_mock_order(order_id="order-valid", status=OrderStatus.ORDERED.value)

        async def find_by_id(order_id):
            if order_id == "order-valid":
                return order_valid
            return None

        mock_order_repo.find_by_id.side_effect = find_by_id
        mock_order_repo.update.side_effect = lambda o: o
        mock_shipment_repo.find_by_order_ids.return_value = {}

        result = await order_service.bulk_update_status(
            order_ids=["order-valid", "order-not-found"],
            status=OrderStatus.MANUFACTURING,
        )

        assert result.updated_count == 1
        assert result.failed_count == 1
        assert mock_status_history_repo.create.call_count == 1

    @pytest.mark.asyncio
    async def test_update_status_no_history_on_invalid_transition(
        self, order_service, mock_order_repo, mock_status_history_repo
    ):
        """Test: No history is recorded when status transition is invalid.

        given: An order in 'ordered' status
        when: Attempting to transition to 'shipped' (invalid)
        then: No history record is created
        """
        from app.utils.exceptions import InvalidStatusTransitionError

        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order

        with pytest.raises(InvalidStatusTransitionError):
            await order_service.update_status(
                order_id="order-123",
                status=OrderStatus.SHIPPED,
            )

        mock_status_history_repo.create.assert_not_called()
