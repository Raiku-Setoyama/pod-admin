"""Manufacturer repository for database operations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturer import Manufacturer


class ManufacturerRepository:
    """Repository for Manufacturer model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, manufacturer_id: str) -> Manufacturer | None:
        """Find a manufacturer by ID."""
        result = await self._db.execute(
            select(Manufacturer).where(Manufacturer.id == manufacturer_id)
        )
        return result.scalar_one_or_none()

    async def find_by_name(self, name: str) -> Manufacturer | None:
        """Find a manufacturer by name."""
        result = await self._db.execute(select(Manufacturer).where(Manufacturer.name == name))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> Manufacturer | None:
        """Find a manufacturer by email."""
        result = await self._db.execute(select(Manufacturer).where(Manufacturer.email == email))
        return result.scalar_one_or_none()

    async def find_all(
        self,
        page: int = 1,
        limit: int = 20,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Manufacturer], int]:
        """Find all manufacturers with pagination and filters."""
        query = select(Manufacturer)
        count_query = select(func.count(Manufacturer.id))

        # Apply filters
        if is_active is not None:
            query = query.where(Manufacturer.is_active == is_active)
            count_query = count_query.where(Manufacturer.is_active == is_active)

        if search:
            search_filter = Manufacturer.name.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Get total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.order_by(Manufacturer.created_at.desc()).offset(offset).limit(limit)

        result = await self._db.execute(query)
        manufacturers = list(result.scalars().all())

        return manufacturers, total

    async def create(self, manufacturer: Manufacturer) -> Manufacturer:
        """Create a new manufacturer."""
        self._db.add(manufacturer)
        await self._db.flush()
        await self._db.refresh(manufacturer)
        return manufacturer

    async def update(self, manufacturer: Manufacturer) -> Manufacturer:
        """Update an existing manufacturer."""
        await self._db.flush()
        await self._db.refresh(manufacturer)
        return manufacturer

    async def delete(self, manufacturer: Manufacturer) -> None:
        """Delete a manufacturer."""
        await self._db.delete(manufacturer)
        await self._db.flush()
