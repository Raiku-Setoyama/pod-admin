"""Order status history service."""

from app.models.order_status_history import OrderStatusHistory
from app.repositories.order_repository import OrderRepository
from app.repositories.order_status_history_repository import OrderStatusHistoryRepository
from app.schemas.order import (
    OrderStatusHistoryListResponse,
    OrderStatusHistoryResponse,
)
from app.utils.exceptions import OrderNotFoundError


class OrderStatusHistoryService:
    """Service for order status history operations."""

    def __init__(
        self,
        history_repo: OrderStatusHistoryRepository,
        order_repo: OrderRepository,
    ):
        self._history_repo = history_repo
        self._order_repo = order_repo

    async def record_status_change(
        self,
        order_id: str,
        from_status: str | None,
        to_status: str,
        changed_by: str | None = None,
        note: str | None = None,
    ) -> None:
        """Record a status change in the history."""
        history = OrderStatusHistory(
            order_id=order_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            note=note,
        )
        await self._history_repo.create(history)

    async def get_history(self, order_id: str) -> OrderStatusHistoryListResponse:
        """Get status history for an order."""
        # Verify the order exists
        order = await self._order_repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        records = await self._history_repo.find_by_order_id(order_id)

        items = [
            OrderStatusHistoryResponse(
                id=record.id,
                order_id=record.order_id,
                from_status=record.from_status,
                to_status=record.to_status,
                changed_by=record.changed_by,
                note=record.note,
                created_at=record.created_at,
            )
            for record in records
        ]

        return OrderStatusHistoryListResponse(items=items)
