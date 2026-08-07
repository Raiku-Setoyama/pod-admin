"""Dashboard service."""

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus
from app.models.shipment import Shipment
from app.schemas.dashboard import DashboardSummary, StatusCount


class DashboardService:
    """Service for dashboard operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_summary(self) -> DashboardSummary:
        """Get dashboard summary."""
        # Today's order count
        orders_today = await self._count_today(Order, Order.ordered_at)

        # Today's shipment count
        shipments_today = await self._count_today(Shipment, Shipment.created_at)

        # Order status breakdown
        order_status_counts = await self._get_status_counts(Order, Order.status)

        # Shipment status breakdown
        shipment_status_counts = await self._get_status_counts(Shipment, Shipment.status)

        # Alerts
        ordered_count = await self._count_by_status(Order, OrderStatus.ORDERED.value)
        manufacturing_count = await self._count_by_status(Order, OrderStatus.MANUFACTURING.value)

        return DashboardSummary(
            orders_today=orders_today,
            shipments_today=shipments_today,
            order_status_counts=order_status_counts,
            shipment_status_counts=shipment_status_counts,
            ordered_count=ordered_count,
            manufacturing_count=manufacturing_count,
        )

    async def _count_today(self, model: Any, date_column: Any) -> int:
        """Count records created today."""
        today = date.today()
        result = await self._db.execute(
            select(func.count(model.id)).where(func.date(date_column) == today)
        )
        return result.scalar() or 0

    async def _get_status_counts(self, model: Any, status_column: Any) -> list[StatusCount]:
        """Get counts grouped by status."""
        result = await self._db.execute(
            select(status_column, func.count(model.id))
            .group_by(status_column)
        )
        return [StatusCount(status=row[0], count=row[1]) for row in result.all()]

    async def _count_by_status(self, model: Any, status: str) -> int:
        """Count records with specific status."""
        result = await self._db.execute(
            select(func.count(model.id)).where(model.status == status)
        )
        return result.scalar() or 0
