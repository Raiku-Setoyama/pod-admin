"""Shipment repository for database operations."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus


class ShipmentRepository:
    """Repository for Shipment model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, shipment_id: str) -> Shipment | None:
        """Find a shipment by ID."""
        result = await self._db.execute(
            select(Shipment)
            .options(selectinload(Shipment.items))
            .where(Shipment.id == shipment_id)
        )
        return result.scalar_one_or_none()

    async def find_by_tracking_number(self, tracking_number: str) -> Shipment | None:
        """Find a shipment by tracking number."""
        result = await self._db.execute(
            select(Shipment)
            .options(selectinload(Shipment.items))
            .where(Shipment.tracking_number == tracking_number)
        )
        return result.scalar_one_or_none()

    async def find_all(
        self,
        page: int = 1,
        limit: int = 20,
        status: ShipmentStatus | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        search: str | None = None,
        tracking_number: str | None = None,
        carrier: str | None = None,
        shipped_from: date | None = None,
        shipped_to: date | None = None,
        delivered_from: date | None = None,
        delivered_to: date | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Shipment], int]:
        """Find all shipments with pagination and filters."""
        query = select(Shipment).options(selectinload(Shipment.items))
        count_query = select(func.count(Shipment.id))

        # Apply filters
        if status:
            query = query.where(Shipment.status == status.value)
            count_query = count_query.where(Shipment.status == status.value)

        if created_from:
            query = query.where(func.date(Shipment.created_at) >= created_from)
            count_query = count_query.where(func.date(Shipment.created_at) >= created_from)

        if created_to:
            query = query.where(func.date(Shipment.created_at) <= created_to)
            count_query = count_query.where(func.date(Shipment.created_at) <= created_to)

        if search:
            search_filter = (
                Shipment.tracking_number.ilike(f"%{search}%")
                | Shipment.customer_name.ilike(f"%{search}%")
                | Shipment.id.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # New filters
        if tracking_number:
            query = query.where(Shipment.tracking_number.ilike(f"%{tracking_number}%"))
            count_query = count_query.where(Shipment.tracking_number.ilike(f"%{tracking_number}%"))

        if carrier:
            query = query.where(Shipment.carrier.ilike(f"%{carrier}%"))
            count_query = count_query.where(Shipment.carrier.ilike(f"%{carrier}%"))

        if shipped_from:
            query = query.where(func.date(Shipment.shipped_at) >= shipped_from)
            count_query = count_query.where(func.date(Shipment.shipped_at) >= shipped_from)

        if shipped_to:
            query = query.where(func.date(Shipment.shipped_at) <= shipped_to)
            count_query = count_query.where(func.date(Shipment.shipped_at) <= shipped_to)

        if delivered_from:
            query = query.where(func.date(Shipment.delivered_at) >= delivered_from)
            count_query = count_query.where(func.date(Shipment.delivered_at) >= delivered_from)

        if delivered_to:
            query = query.where(func.date(Shipment.delivered_at) <= delivered_to)
            count_query = count_query.where(func.date(Shipment.delivered_at) <= delivered_to)

        # Get total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(Shipment, sort_by, Shipment.created_at)
        if sort_order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self._db.execute(query)
        shipments = list(result.scalars().all())

        return shipments, total

    async def create(
        self,
        order_ids: list[str],
        customer_name: str,
        customer_postal_code: str,
        customer_address: str,
        customer_phone: str,
    ) -> Shipment:
        """Create a new shipment."""
        shipment = Shipment(
            customer_name=customer_name,
            customer_postal_code=customer_postal_code,
            customer_address=customer_address,
            customer_phone=customer_phone,
        )
        self._db.add(shipment)
        await self._db.flush()

        # Create items
        for order_id in order_ids:
            item = ShipmentItem(
                shipment_id=shipment.id,
                order_id=order_id,
            )
            self._db.add(item)

        await self._db.flush()
        await self._db.refresh(shipment)

        return await self.find_by_id(shipment.id)  # type: ignore

    async def update(self, shipment: Shipment) -> Shipment:
        """Update an existing shipment."""
        await self._db.flush()
        await self._db.refresh(shipment)
        return shipment
