"""Unit tests for OrderStatusHistoryService.

FEAT-0014: Tests for the service layer that manages status history recording and retrieval.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.order_status_history_service import OrderStatusHistoryService
from app.models.order_status_history import OrderStatusHistory
from app.schemas.order import OrderStatusHistoryResponse, OrderStatusHistoryListResponse


class TestOrderStatusHistoryService:
    """Test OrderStatusHistoryService methods."""

    @pytest.fixture
    def mock_history_repo(self):
        """Mock OrderStatusHistoryRepository."""
        return AsyncMock()

    @pytest.fixture
    def mock_order_repo(self):
        """Mock OrderRepository."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_history_repo, mock_order_repo):
        """Create service with mocked dependencies."""
        return OrderStatusHistoryService(
            history_repo=mock_history_repo,
            order_repo=mock_order_repo,
        )

    @pytest.mark.asyncio
    async def test_record_status_change(self, service, mock_history_repo):
        """Test: record_status_change() creates a history record.

        given: A valid status change occurs
        when: record_status_change() is called
        then: A new OrderStatusHistory record is created via repository
        """
        await service.record_status_change(
            order_id="order-123",
            from_status="ordered",
            to_status="manufacturing",
            changed_by="Admin User",
        )

        mock_history_repo.create.assert_called_once()
        created_record = mock_history_repo.create.call_args[0][0]
        assert isinstance(created_record, OrderStatusHistory)
        assert created_record.order_id == "order-123"
        assert created_record.from_status == "ordered"
        assert created_record.to_status == "manufacturing"
        assert created_record.changed_by == "Admin User"

    @pytest.mark.asyncio
    async def test_record_status_change_initial_status(self, service, mock_history_repo):
        """Test: record_status_change() with null from_status for initial order.

        given: An order is created (initial status)
        when: record_status_change() is called with from_status=None
        then: A history record with from_status=None is created
        """
        await service.record_status_change(
            order_id="order-123",
            from_status=None,
            to_status="ordered",
            changed_by="system",
        )

        mock_history_repo.create.assert_called_once()
        created_record = mock_history_repo.create.call_args[0][0]
        assert created_record.from_status is None
        assert created_record.to_status == "ordered"

    @pytest.mark.asyncio
    async def test_get_history_returns_list(self, service, mock_history_repo, mock_order_repo):
        """Test: get_history() returns formatted history list.

        given: An order has status history records
        when: get_history() is called
        then: Returns OrderStatusHistoryListResponse with formatted records
        """
        # Mock order exists
        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order_repo.find_by_id.return_value = mock_order

        # Mock history records
        mock_history_1 = MagicMock(spec=OrderStatusHistory)
        mock_history_1.id = "history-1"
        mock_history_1.order_id = "order-123"
        mock_history_1.from_status = "ordered"
        mock_history_1.to_status = "manufacturing"
        mock_history_1.changed_by = "Admin"
        mock_history_1.note = None
        mock_history_1.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)

        mock_history_2 = MagicMock(spec=OrderStatusHistory)
        mock_history_2.id = "history-2"
        mock_history_2.order_id = "order-123"
        mock_history_2.from_status = None
        mock_history_2.to_status = "ordered"
        mock_history_2.changed_by = "system"
        mock_history_2.note = None
        mock_history_2.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        mock_history_repo.find_by_order_id.return_value = [mock_history_1, mock_history_2]

        result = await service.get_history("order-123")

        assert isinstance(result, OrderStatusHistoryListResponse)
        assert len(result.items) == 2
        mock_history_repo.find_by_order_id.assert_called_once_with("order-123")

    @pytest.mark.asyncio
    async def test_get_history_order_not_found(self, service, mock_history_repo, mock_order_repo):
        """Test: get_history() raises error when order not found.

        given: An order does not exist
        when: get_history() is called
        then: OrderNotFoundError is raised
        """
        from app.utils.exceptions import OrderNotFoundError

        mock_order_repo.find_by_id.return_value = None

        with pytest.raises(OrderNotFoundError):
            await service.get_history("non-existent-order")

    @pytest.mark.asyncio
    async def test_get_history_empty(self, service, mock_history_repo, mock_order_repo):
        """Test: get_history() returns empty list when no history exists.

        given: An order exists but has no history
        when: get_history() is called
        then: Returns empty list
        """
        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order_repo.find_by_id.return_value = mock_order
        mock_history_repo.find_by_order_id.return_value = []

        result = await service.get_history("order-123")

        assert isinstance(result, OrderStatusHistoryListResponse)
        assert len(result.items) == 0
