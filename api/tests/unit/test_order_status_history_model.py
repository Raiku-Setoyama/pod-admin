"""Unit tests for OrderStatusHistory model.

FEAT-0014: AC-001, AC-012
Tests verify the OrderStatusHistory model has the correct column structure
and that from_status can be null (for initial order creation).
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.models.order_status_history import OrderStatusHistory


class TestOrderStatusHistoryModel:
    """Test OrderStatusHistory model structure (AC-001)."""

    def test_model_has_required_attributes(self):
        """AC-001: OrderStatusHistory has correct column structure.

        given: OrderStatusHistory model is defined
        when: Check model attributes
        then: id(UUID), order_id(FK), from_status(nullable), to_status(not null),
              changed_by(nullable), note(nullable), created_at, updated_at exist
        """
        history = OrderStatusHistory()

        # Verify all required attributes exist
        assert hasattr(history, "id")
        assert hasattr(history, "order_id")
        assert hasattr(history, "from_status")
        assert hasattr(history, "to_status")
        assert hasattr(history, "changed_by")
        assert hasattr(history, "note")
        assert hasattr(history, "created_at")
        assert hasattr(history, "updated_at")

    def test_model_tablename(self):
        """Verify the table name is 'order_status_history'."""
        assert OrderStatusHistory.__tablename__ == "order_status_history"

    def test_from_status_nullable(self):
        """AC-012: from_status can be null for initial order creation.

        given: OrderStatusHistory record is created
        when: from_status is not specified (initial order creation)
        then: from_status is null
        """
        history = OrderStatusHistory(
            order_id="test-order-id",
            from_status=None,
            to_status="ordered",
            changed_by="system",
        )

        assert history.from_status is None
        assert history.to_status == "ordered"

    def test_model_with_all_fields(self):
        """Verify model can be instantiated with all fields."""
        history = OrderStatusHistory(
            order_id="test-order-id",
            from_status="ordered",
            to_status="manufacturing",
            changed_by="Test Admin",
            note="Status updated",
        )

        assert history.order_id == "test-order-id"
        assert history.from_status == "ordered"
        assert history.to_status == "manufacturing"
        assert history.changed_by == "Test Admin"
        assert history.note == "Status updated"

    def test_note_nullable(self):
        """Verify note can be null."""
        history = OrderStatusHistory(
            order_id="test-order-id",
            from_status="ordered",
            to_status="manufacturing",
            changed_by="Test Admin",
            note=None,
        )

        assert history.note is None

    def test_changed_by_nullable(self):
        """Verify changed_by can be null."""
        history = OrderStatusHistory(
            order_id="test-order-id",
            from_status="ordered",
            to_status="manufacturing",
            changed_by=None,
        )

        assert history.changed_by is None

    def test_repr(self):
        """Verify __repr__ returns a useful string."""
        history = OrderStatusHistory(
            order_id="test-order-id",
            from_status="ordered",
            to_status="manufacturing",
        )
        history.id = "history-id-123"

        repr_str = repr(history)
        assert "OrderStatusHistory" in repr_str
