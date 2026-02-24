"""Unit tests for OrderStatusHistoryRepository.

FEAT-0014: Tests for the repository layer that manages OrderStatusHistory persistence.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.repositories.order_status_history_repository import OrderStatusHistoryRepository
from app.models.order_status_history import OrderStatusHistory


class TestOrderStatusHistoryRepository:
    """Test OrderStatusHistoryRepository methods."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def repository(self, mock_db):
        """Create repository with mocked DB."""
        return OrderStatusHistoryRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_history_record(self, repository, mock_db):
        """Test: create() adds a history record and flushes.

        given: A valid OrderStatusHistory instance
        when: create() is called
        then: The record is added to the session and flushed
        """
        history = OrderStatusHistory(
            order_id="order-123",
            from_status="ordered",
            to_status="manufacturing",
            changed_by="Admin User",
        )

        await repository.create(history)

        mock_db.add.assert_called_once_with(history)
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_order_id_returns_records(self, repository, mock_db):
        """Test: find_by_order_id() returns history records for an order.

        given: An order has status history records
        when: find_by_order_id() is called
        then: Returns list of OrderStatusHistory records ordered by created_at desc
        """
        mock_history_1 = MagicMock(spec=OrderStatusHistory)
        mock_history_1.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_history_2 = MagicMock(spec=OrderStatusHistory)
        mock_history_2.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_history_2, mock_history_1]
        mock_db.execute.return_value = mock_result

        result = await repository.find_by_order_id("order-123")

        assert len(result) == 2
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_order_id_returns_empty_list(self, repository, mock_db):
        """Test: find_by_order_id() returns empty list when no records exist.

        given: An order has no status history records
        when: find_by_order_id() is called
        then: Returns empty list
        """
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await repository.find_by_order_id("order-no-history")

        assert result == []
