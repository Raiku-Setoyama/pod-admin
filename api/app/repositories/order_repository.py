"""Order repository for database operations."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import ProductType


class OrderRepository:
    """Repository for Order model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, order_id: str) -> Order | None:
        """Find an order by ID with items loaded."""
        result = await self._db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def find_by_order_number(self, order_number: str) -> Order | None:
        """Find an order by order number with items loaded."""
        result = await self._db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.order_number == order_number)
        )
        return result.scalar_one_or_none()

    async def find_all(
        self,
        page: int = 1,
        limit: int = 20,
        status: OrderStatus | None = None,
        product_type: ProductType | None = None,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        search: str | None = None,
    ) -> tuple[list[Order], int]:
        """Find all orders with pagination and filters."""
        query = select(Order).options(selectinload(Order.items))
        count_query = select(func.count(Order.id))

        # Apply filters
        if status:
            query = query.where(Order.status == status.value)
            count_query = count_query.where(Order.status == status.value)

        if product_type:
            # Filter orders that have items with the specified product type
            query = query.where(
                Order.id.in_(
                    select(OrderItem.order_id).where(
                        OrderItem.product_type == product_type.value
                    )
                )
            )
            count_query = count_query.where(
                Order.id.in_(
                    select(OrderItem.order_id).where(
                        OrderItem.product_type == product_type.value
                    )
                )
            )

        if ordered_from:
            query = query.where(func.date(Order.ordered_at) >= ordered_from)
            count_query = count_query.where(func.date(Order.ordered_at) >= ordered_from)

        if ordered_to:
            query = query.where(func.date(Order.ordered_at) <= ordered_to)
            count_query = count_query.where(func.date(Order.ordered_at) <= ordered_to)

        if search:
            search_filter = Order.order_number.ilike(f"%{search}%") | Order.customer_name.ilike(
                f"%{search}%"
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Get total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.order_by(Order.ordered_at.desc()).offset(offset).limit(limit)

        result = await self._db.execute(query)
        orders = list(result.scalars().all())

        return orders, total

    async def create(self, order: Order) -> Order:
        """Create a new order."""
        self._db.add(order)
        await self._db.flush()
        await self._db.refresh(order)
        # Reload order with items to avoid lazy loading issues
        return await self.find_by_id(order.id)

    async def update(self, order: Order) -> Order:
        """Update an existing order."""
        await self._db.flush()
        await self._db.refresh(order)
        # Reload order with items to avoid lazy loading issues
        return await self.find_by_id(order.id)

    async def update_status(self, order_id: str, status: OrderStatus) -> Order | None:
        """Update order status."""
        order = await self.find_by_id(order_id)
        if order:
            order.status = status.value
            await self._db.flush()
            await self._db.refresh(order)
        return order

    async def find_items_by_manufacturer(
        self,
        manufacturer_id: str,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        status: OrderStatus | None = None,
    ) -> list[dict]:
        """Find order items for a specific manufacturer.

        Joins: OrderItem -> Product -> Manufacturer
        Returns items with order details for CSV generation.

        Args:
            manufacturer_id: The manufacturer ID to filter by.
            ordered_from: Optional start date filter.
            ordered_to: Optional end date filter.
            status: Optional order status filter.

        Returns:
            List of dicts with order item details.
        """
        from app.models.product import Product

        query = (
            select(
                OrderItem,
                Order.order_number,
                Order.ordered_at,
                Product.cost,
            )
            .join(Order, OrderItem.order_id == Order.id)
            .join(Product, OrderItem.product_id == Product.id)
            .where(Product.manufacturer_id == manufacturer_id)
        )

        if status:
            query = query.where(Order.status == status.value)

        if ordered_from:
            query = query.where(func.date(Order.ordered_at) >= ordered_from)

        if ordered_to:
            query = query.where(func.date(Order.ordered_at) <= ordered_to)

        query = query.order_by(Order.ordered_at.desc())

        result = await self._db.execute(query)
        rows = result.all()

        items = []
        for order_item, order_number, ordered_at, cost in rows:
            items.append({
                "ordered_date": ordered_at,
                "order_number": order_number,
                "uid": order_item.uid,
                "product_name": order_item.product_name,
                "product_type": order_item.product_type,
                "quantity": order_item.quantity,
                "size": order_item.size,
                "position": order_item.position,
                "color": order_item.color,
                "cost": cost,
            })

        return items

    async def get_ordered_items_summary_by_manufacturer(
        self,
    ) -> list[dict]:
        """メーカー別のORDERED受注明細サマリーを取得"""
        from app.models.product import Product
        from app.models.manufacturer import Manufacturer

        query = (
            select(
                Manufacturer.id,
                Manufacturer.name,
                Manufacturer.email,
                Manufacturer.phone,
                Manufacturer.lead_time_days,
                Manufacturer.is_active,
                func.count(OrderItem.id).label("ordered_item_count"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("total_quantity"),
                func.coalesce(func.sum(OrderItem.price * OrderItem.quantity), 0).label("total_amount"),
            )
            .select_from(Manufacturer)
            .join(Product, Product.manufacturer_id == Manufacturer.id)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status == OrderStatus.ORDERED.value)
            .where(Manufacturer.is_active == True)
            .group_by(Manufacturer.id)
            .having(func.count(OrderItem.id) > 0)
            .order_by(Manufacturer.name)
        )

        result = await self._db.execute(query)
        return [dict(row._mapping) for row in result.all()]

    async def find_ordered_items_by_manufacturer_detail(
        self,
        manufacturer_id: str,
        status: OrderStatus = OrderStatus.ORDERED,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        product_type: str | None = None,
    ) -> list[tuple]:
        """メーカー別のORDERED受注明細を詳細情報付きで取得"""
        from app.models.product import Product

        query = (
            select(
                OrderItem,
                Order.order_number,
                Order.ordered_at,
                Order.customer_name,
                Product.cost,
            )
            .join(Order, OrderItem.order_id == Order.id)
            .join(Product, OrderItem.product_id == Product.id)
            .where(Product.manufacturer_id == manufacturer_id)
            .where(Order.status == status.value)
        )

        if ordered_from:
            query = query.where(func.date(Order.ordered_at) >= ordered_from)

        if ordered_to:
            query = query.where(func.date(Order.ordered_at) <= ordered_to)

        if product_type:
            query = query.where(OrderItem.product_type == product_type)

        query = query.order_by(Order.ordered_at.desc())

        result = await self._db.execute(query)
        return result.all()

    async def update_status_by_manufacturer(
        self,
        manufacturer_id: str,
        new_status: OrderStatus,
        order_item_ids: list[str] | None = None,
    ) -> int:
        """メーカーの受注ステータスを一括更新

        指定されたメーカーに紐づくORDEREDステータスの受注を一括更新。

        Args:
            manufacturer_id: メーカーID
            new_status: 新しいステータス
            order_item_ids: 更新対象のOrderItem ID（指定がなければ全て）

        Returns:
            更新された受注数
        """
        from app.models.product import Product

        # 対象のOrderItemに紐づくorder_idを取得
        query = (
            select(OrderItem.order_id)
            .distinct()
            .join(Order, OrderItem.order_id == Order.id)
            .join(Product, OrderItem.product_id == Product.id)
            .where(Product.manufacturer_id == manufacturer_id)
            .where(Order.status == OrderStatus.ORDERED.value)
        )

        if order_item_ids:
            query = query.where(OrderItem.id.in_(order_item_ids))

        result = await self._db.execute(query)
        order_ids = [row[0] for row in result.all()]

        # Orderのステータスを更新
        updated_count = 0
        for order_id in order_ids:
            order = await self.find_by_id(order_id)
            if order:
                order.status = new_status.value
                await self._db.flush()
                updated_count += 1

        return updated_count
