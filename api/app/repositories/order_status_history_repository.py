"""Order status history repository for database operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order_status_history import OrderStatusHistory


class OrderStatusHistoryRepository:
    """Repository for OrderStatusHistory model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, history: OrderStatusHistory) -> None:
        """Create a new status history record."""
        self._db.add(history)
        await self._db.flush()

    async def find_by_order_id(self, order_id: str) -> list[OrderStatusHistory]:
        """Find all status history records for an order, ordered by created_at DESC."""
        result = await self._db.execute(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at.desc())
        )
        return list(result.scalars().all())
