"""OrderSource repository for database operations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order_source import OrderSource


class OrderSourceRepository:
    """Repository for OrderSource model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, order_source_id: str) -> OrderSource | None:
        """Find an order source by ID."""
        result = await self._db.execute(
            select(OrderSource).where(OrderSource.id == order_source_id)
        )
        return result.scalar_one_or_none()

    async def find_by_code(self, code: str) -> OrderSource | None:
        """Find an order source by code."""
        result = await self._db.execute(
            select(OrderSource).where(OrderSource.code == code)
        )
        return result.scalar_one_or_none()

    async def find_by_api_key(self, api_key: str) -> OrderSource | None:
        """Find an order source by API key."""
        result = await self._db.execute(
            select(OrderSource).where(OrderSource.api_key == api_key)
        )
        return result.scalar_one_or_none()

    async def find_all(
        self,
        page: int = 1,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> tuple[list[OrderSource], int]:
        """Find all order sources with pagination and filters."""
        query = select(OrderSource)
        count_query = select(func.count(OrderSource.id))

        # Apply filters
        if is_active is not None:
            query = query.where(OrderSource.is_active == is_active)
            count_query = count_query.where(OrderSource.is_active == is_active)

        # Get total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.order_by(OrderSource.code).offset(offset).limit(limit)

        result = await self._db.execute(query)
        order_sources = list(result.scalars().all())

        return order_sources, total

    async def create(self, order_source: OrderSource) -> OrderSource:
        """Create a new order source."""
        self._db.add(order_source)
        await self._db.flush()
        await self._db.refresh(order_source)
        return order_source

    async def update(self, order_source: OrderSource) -> OrderSource:
        """Update an existing order source."""
        await self._db.flush()
        await self._db.refresh(order_source)
        return order_source

    async def delete(self, order_source: OrderSource) -> None:
        """Delete an order source."""
        await self._db.delete(order_source)
        await self._db.flush()
