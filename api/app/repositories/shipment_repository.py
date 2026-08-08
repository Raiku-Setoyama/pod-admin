"""Shipment repository for database operations."""

from datetime import date

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus


class ShipmentRepository:
    """Repository for Shipment model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, shipment_id: str) -> Shipment | None:
        """Find a shipment by ID."""
        result = await self._db.execute(
            select(Shipment)
            .options(
                selectinload(Shipment.items)
                .selectinload(ShipmentItem.order)
                .selectinload(Order.items),
                selectinload(Shipment.items)
                .selectinload(ShipmentItem.order)
                .selectinload(Order.order_source),
            )
            .where(Shipment.id == shipment_id)
        )
        return result.scalar_one_or_none()

    async def find_by_tracking_number(self, tracking_number: str) -> Shipment | None:
        """Find a shipment by tracking number."""
        result = await self._db.execute(
            select(Shipment)
            .options(
                selectinload(Shipment.items)
                .selectinload(ShipmentItem.order)
                .selectinload(Order.items),
                selectinload(Shipment.items)
                .selectinload(ShipmentItem.order)
                .selectinload(Order.order_source),
            )
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
        estimated_shipping_date_from: date | None = None,
        estimated_shipping_date_to: date | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Shipment], int]:
        """Find all shipments with pagination and filters."""
        query = select(Shipment).options(
            selectinload(Shipment.items)
            .selectinload(ShipmentItem.order)
            .selectinload(Order.items)
        )
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
            # Search by tracking_number, shipment id, or order_number / customer_name via Order
            pattern = f"%{search}%"
            search_subquery = (
                select(ShipmentItem.shipment_id)
                .join(Order, ShipmentItem.order_id == Order.id)
                .where(
                    or_(
                        Order.customer_name.ilike(pattern),
                        Order.order_number.ilike(pattern),
                    )
                )
            )
            search_filter = or_(
                Shipment.tracking_number.ilike(pattern),
                # Shipment.id は PostgreSQL の uuid 型で ILIKE 演算子を持たない。
                # 一覧に出る先頭 8 桁で引けるよう、text にキャストしてから部分一致させる。
                cast(Shipment.id, Text).ilike(pattern),
                Shipment.id.in_(search_subquery),
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

        if estimated_shipping_date_from or estimated_shipping_date_to:
            # estimated_shipping_date is on Order, join via ShipmentItem
            est_date_subquery = select(ShipmentItem.shipment_id).join(
                Order, ShipmentItem.order_id == Order.id
            )
            if estimated_shipping_date_from:
                est_date_subquery = est_date_subquery.where(
                    Order.estimated_shipping_date >= estimated_shipping_date_from
                )
            if estimated_shipping_date_to:
                est_date_subquery = est_date_subquery.where(
                    Order.estimated_shipping_date <= estimated_shipping_date_to
                )
            est_date_filter = Shipment.id.in_(est_date_subquery)
            query = query.where(est_date_filter)
            count_query = count_query.where(est_date_filter)

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

    async def create(self, order_ids: list[str]) -> Shipment:
        """Create a new shipment.

        顧客情報は order_ids の最初の注文から参照します。
        """
        shipment = Shipment()
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

    async def find_by_order_ids(self, order_ids: list[str]) -> dict[str, Shipment]:
        """Find shipments by order IDs.

        Returns a dict mapping order_id -> Shipment for batch lookup (N+1 avoidance).
        """
        if not order_ids:
            return {}

        query = (
            select(Shipment, ShipmentItem.order_id)
            .join(ShipmentItem, ShipmentItem.shipment_id == Shipment.id)
            .where(ShipmentItem.order_id.in_(order_ids))
        )

        result = await self._db.execute(query)
        rows = result.all()

        # Map order_id -> Shipment
        order_shipment_map: dict[str, Shipment] = {}
        for shipment, order_id in rows:
            order_shipment_map[order_id] = shipment

        return order_shipment_map

    async def exists_for_order(self, order_id: str) -> bool:
        """Check if a shipment already exists for the given order.

        Args:
            order_id: The order ID to check.

        Returns:
            True if a shipment exists for this order, False otherwise.
        """
        query = (
            select(func.count(ShipmentItem.id))
            .where(ShipmentItem.order_id == order_id)
        )
        result = await self._db.execute(query)
        count = result.scalar() or 0
        return count > 0

    async def delete_by_order_id(self, order_id: str) -> None:
        """Delete shipment and shipment items for a given order.

        This removes the ShipmentItem for the order, and if the Shipment
        has no more items, deletes the Shipment as well.

        Args:
            order_id: The order ID whose shipment should be deleted.
        """
        # Find the shipment item for this order
        query = select(ShipmentItem).where(ShipmentItem.order_id == order_id)
        result = await self._db.execute(query)
        shipment_item = result.scalar_one_or_none()

        if not shipment_item:
            return

        shipment_id = shipment_item.shipment_id

        # Delete the shipment item
        await self._db.delete(shipment_item)
        await self._db.flush()

        # Check if shipment has any remaining items
        remaining_query = (
            select(func.count(ShipmentItem.id))
            .where(ShipmentItem.shipment_id == shipment_id)
        )
        remaining_result = await self._db.execute(remaining_query)
        remaining_count = remaining_result.scalar() or 0

        # If no items remain, delete the shipment
        if remaining_count == 0:
            shipment_query = select(Shipment).where(Shipment.id == shipment_id)
            shipment_result = await self._db.execute(shipment_query)
            shipment = shipment_result.scalar_one_or_none()
            if shipment:
                await self._db.delete(shipment)
                await self._db.flush()
