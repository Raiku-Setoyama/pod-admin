"""Unit tests for OrderStatusHistory schemas.

FEAT-0014: Tests for the Pydantic response schemas for status history.
"""

import pytest
from datetime import datetime, timezone

from app.schemas.order import OrderStatusHistoryResponse, OrderStatusHistoryListResponse


class TestOrderStatusHistoryResponseSchema:
    """Test OrderStatusHistoryResponse schema."""

    def test_schema_with_all_fields(self):
        """Test: Schema accepts all fields correctly."""
        response = OrderStatusHistoryResponse(
            id="history-123",
            order_id="order-123",
            from_status="ordered",
            to_status="manufacturing",
            changed_by="Admin User",
            note="Manual update",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        assert response.id == "history-123"
        assert response.order_id == "order-123"
        assert response.from_status == "ordered"
        assert response.to_status == "manufacturing"
        assert response.changed_by == "Admin User"
        assert response.note == "Manual update"

    def test_schema_with_null_from_status(self):
        """Test: Schema accepts null from_status (for initial order)."""
        response = OrderStatusHistoryResponse(
            id="history-123",
            order_id="order-123",
            from_status=None,
            to_status="ordered",
            changed_by="system",
            note=None,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        assert response.from_status is None

    def test_schema_with_null_changed_by(self):
        """Test: Schema accepts null changed_by."""
        response = OrderStatusHistoryResponse(
            id="history-123",
            order_id="order-123",
            from_status="ordered",
            to_status="manufacturing",
            changed_by=None,
            note=None,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        assert response.changed_by is None


class TestOrderStatusHistoryListResponseSchema:
    """Test OrderStatusHistoryListResponse schema."""

    def test_list_response_with_items(self):
        """Test: List response contains items."""
        items = [
            OrderStatusHistoryResponse(
                id="history-1",
                order_id="order-123",
                from_status="ordered",
                to_status="manufacturing",
                changed_by="Admin",
                note=None,
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
            OrderStatusHistoryResponse(
                id="history-2",
                order_id="order-123",
                from_status=None,
                to_status="ordered",
                changed_by="system",
                note=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        response = OrderStatusHistoryListResponse(items=items)

        assert len(response.items) == 2
        assert response.items[0].id == "history-1"
        assert response.items[1].id == "history-2"

    def test_list_response_empty(self):
        """Test: List response can be empty."""
        response = OrderStatusHistoryListResponse(items=[])

        assert len(response.items) == 0
