"""Order repository for database operations."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderItemStatus, OrderStatus
from app.models.product import ProductType


class OrderRepository:
    """Repository for Order model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, order_id: str) -> Order | None:
        """Find an order by ID with items and order_source loaded."""
        result = await self._db.execute(
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.order_source),
            )
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def find_by_order_number(self, order_number: str) -> Order | None:
        """Find an order by order number with items and order_source loaded."""
        result = await self._db.execute(
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.order_source),
            )
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
        query = select(Order).options(
            selectinload(Order.items),
            selectinload(Order.order_source),
        )
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
        """メーカー別のORDERED受注明細サマリーを取得（OrderItem.statusベース）"""
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
            .where(OrderItem.status == OrderItemStatus.ORDERED.value)  # OrderItem.statusでフィルタ
            .where(Manufacturer.is_active == True)
            .group_by(Manufacturer.id)
            .having(func.count(OrderItem.id) > 0)
            .order_by(func.max(Order.ordered_at).desc())
        )

        result = await self._db.execute(query)
        return [dict(row._mapping) for row in result.all()]

    async def find_ordered_items_by_manufacturer_detail(
        self,
        manufacturer_id: str,
        status: str | None = None,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        product_type: str | None = None,
        search: str | None = None,
        expected_delivery_from: date | None = None,
        expected_delivery_to: date | None = None,
    ) -> list[tuple]:
        """メーカー別の受注明細を詳細情報付きで取得

        Args:
            manufacturer_id: メーカーID
            status: ステータスフィルター（OrderItem.statusでフィルタ、None の場合は全て）
            ordered_from: 発注日From
            ordered_to: 発注日To
            product_type: 商品タイプ
            search: キーワード検索（注文番号・製品番号・商品名）
            expected_delivery_from: 納品予定日From
            expected_delivery_to: 納品予定日To

        Returns:
            受注明細のタプルリスト（OrderItem, order_number, ordered_at, customer_name, cost, item_status, order_status, lead_time_days）
        """
        from app.models.product import Product
        from app.models.manufacturer import Manufacturer

        query = (
            select(
                OrderItem,
                Order.order_number,
                Order.ordered_at,
                Order.customer_name,
                Product.cost,
                OrderItem.status,  # item_status
                Order.status,  # order_status（後方互換性のため）
                Manufacturer.lead_time_days,
            )
            .join(Order, OrderItem.order_id == Order.id)
            .join(Product, OrderItem.product_id == Product.id)
            .join(Manufacturer, Product.manufacturer_id == Manufacturer.id)
            .where(Product.manufacturer_id == manufacturer_id)
        )

        # ステータスフィルター（OrderItem.statusでフィルタ）
        if status:
            query = query.where(OrderItem.status == status)

        if ordered_from:
            query = query.where(func.date(Order.ordered_at) >= ordered_from)

        if ordered_to:
            query = query.where(func.date(Order.ordered_at) <= ordered_to)

        if product_type:
            query = query.where(OrderItem.product_type == product_type)

        # キーワード検索（注文番号・製品番号・商品名）
        if search:
            search_pattern = f"%{search}%"
            search_filter = (
                Order.order_number.ilike(search_pattern)
                | OrderItem.uid.ilike(search_pattern)
                | OrderItem.product_name.ilike(search_pattern)
            )
            query = query.where(search_filter)

        # 納品予定日フィルター（ordered_at + lead_time_days）
        if expected_delivery_from:
            query = query.where(
                func.date(Order.ordered_at) + Manufacturer.lead_time_days >= expected_delivery_from
            )

        if expected_delivery_to:
            query = query.where(
                func.date(Order.ordered_at) + Manufacturer.lead_time_days <= expected_delivery_to
            )

        query = query.order_by(Order.ordered_at.desc())

        result = await self._db.execute(query)
        return result.all()

    async def find_all_ordered_items_detail(
        self,
        status: str | None = None,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        product_type: str | None = None,
        search: str | None = None,
        manufacturer_id: str | None = None,
        expected_delivery_from: date | None = None,
        expected_delivery_to: date | None = None,
    ) -> list[tuple]:
        """全メーカー横断の受注明細を詳細情報付きで取得

        Args:
            status: ステータスフィルター（None の場合は shipped 以外の全て）
            ordered_from: 発注日From
            ordered_to: 発注日To
            product_type: 商品タイプ
            search: キーワード検索（注文番号・製品番号・商品名）
            manufacturer_id: メーカーIDフィルター
            expected_delivery_from: 納品予定日From
            expected_delivery_to: 納品予定日To

        Returns:
            受注明細のタプルリスト（OrderItem, order_number, ordered_at, customer_name, cost, status, manufacturer_id, manufacturer_name, lead_time_days）
        """
        from app.models.product import Product
        from app.models.manufacturer import Manufacturer

        query = (
            select(
                OrderItem,
                Order.order_number,
                Order.ordered_at,
                Order.customer_name,
                Product.cost,
                Order.status,
                Manufacturer.id.label("manufacturer_id"),
                Manufacturer.name.label("manufacturer_name"),
                Manufacturer.lead_time_days,
            )
            .join(Order, OrderItem.order_id == Order.id)
            .join(Product, OrderItem.product_id == Product.id)
            .join(Manufacturer, Product.manufacturer_id == Manufacturer.id)
        )

        # ステータスフィルター
        if status:
            query = query.where(Order.status == status)
        else:
            # デフォルトは shipped 以外の全ステータス
            query = query.where(Order.status != OrderStatus.SHIPPED.value)

        # メーカーIDフィルター
        if manufacturer_id:
            query = query.where(Manufacturer.id == manufacturer_id)

        if ordered_from:
            query = query.where(func.date(Order.ordered_at) >= ordered_from)

        if ordered_to:
            query = query.where(func.date(Order.ordered_at) <= ordered_to)

        if product_type:
            query = query.where(OrderItem.product_type == product_type)

        # キーワード検索（注文番号・製品番号・商品名）
        if search:
            search_pattern = f"%{search}%"
            search_filter = (
                Order.order_number.ilike(search_pattern)
                | OrderItem.uid.ilike(search_pattern)
                | OrderItem.product_name.ilike(search_pattern)
            )
            query = query.where(search_filter)

        # 納品予定日フィルター（ordered_at + lead_time_days）
        if expected_delivery_from:
            query = query.where(
                func.date(Order.ordered_at) + Manufacturer.lead_time_days >= expected_delivery_from
            )

        if expected_delivery_to:
            query = query.where(
                func.date(Order.ordered_at) + Manufacturer.lead_time_days <= expected_delivery_to
            )

        query = query.order_by(Order.ordered_at.desc())

        result = await self._db.execute(query)
        return result.all()

    async def update_item_status_by_manufacturer(
        self,
        manufacturer_id: str,
        new_status: OrderItemStatus,
        order_item_ids: list[str] | None = None,
    ) -> tuple[list[OrderItem], set[str]]:
        """メーカーの受注明細ステータスをOrderItem単位で更新

        指定されたメーカーに紐づくOrderItemのステータスを更新。
        発注中・製造中・納入済みの全ステータス間で遷移可能。
        （同じステータスへの更新はスキップ）

        Args:
            manufacturer_id: メーカーID
            new_status: 新しいステータス（ordered, manufacturing, delivered）
            order_item_ids: 更新対象のOrderItem ID（指定がなければ全て）

        Returns:
            tuple[list[OrderItem], set[str]]: (更新されたOrderItemリスト, 影響を受けたorder_idのセット)
        """
        from app.models.product import Product

        # 更新可能な元ステータス（新ステータスと同じものは除外）
        all_updatable_statuses = [
            OrderItemStatus.ORDERED.value,
            OrderItemStatus.MANUFACTURING.value,
            OrderItemStatus.DELIVERED.value,
        ]
        valid_from_statuses = [s for s in all_updatable_statuses if s != new_status.value]

        # 対象のOrderItemを取得
        query = (
            select(OrderItem)
            .join(Product, OrderItem.product_id == Product.id)
            .where(Product.manufacturer_id == manufacturer_id)
            .where(OrderItem.status.in_(valid_from_statuses))
        )

        if order_item_ids:
            query = query.where(OrderItem.id.in_(order_item_ids))

        result = await self._db.execute(query)
        items = list(result.scalars().all())

        # OrderItemのステータスを更新
        affected_order_ids: set[str] = set()
        for item in items:
            item.status = new_status.value
            affected_order_ids.add(item.order_id)

        await self._db.flush()

        return items, affected_order_ids

    async def check_all_items_delivered(self, order_id: str) -> bool:
        """指定されたOrderの全OrderItemがdeliveredかどうかを確認

        Args:
            order_id: 注文ID

        Returns:
            bool: 全てのOrderItemがdeliveredならTrue
        """
        # deliveredでないOrderItemが1件でもあればFalse
        query = (
            select(func.count(OrderItem.id))
            .where(OrderItem.order_id == order_id)
            .where(OrderItem.status != OrderItemStatus.DELIVERED.value)
        )
        result = await self._db.execute(query)
        non_delivered_count = result.scalar() or 0

        return non_delivered_count == 0

    def derive_order_status(self, order: Order) -> str:
        """OrderItemのステータスからOrder.statusを導出

        導出ルール:
        - "shipped": Shipmentが存在し、shipped状態（この関数では判定しない、サービス層で処理）
        - "delivered": 全OrderItemが "delivered"
        - "manufacturing": 1つ以上のOrderItemが "manufacturing"
        - "ordered": それ以外

        Args:
            order: Orderオブジェクト（itemsがロード済みであること）

        Returns:
            str: 導出されたステータス
        """
        if not order.items:
            return OrderStatus.ORDERED.value

        statuses = [item.status for item in order.items]

        # 全てdeliveredなら"delivered"
        if all(s == OrderItemStatus.DELIVERED.value for s in statuses):
            return OrderStatus.DELIVERED.value

        # 1つでもmanufacturingがあれば"manufacturing"
        if any(s == OrderItemStatus.MANUFACTURING.value for s in statuses):
            return OrderStatus.MANUFACTURING.value

        # それ以外は"ordered"
        return OrderStatus.ORDERED.value

    async def update_order_derived_status(self, order_id: str) -> Order | None:
        """Orderのステータスを配下のOrderItemから導出して更新

        Args:
            order_id: 注文ID

        Returns:
            更新されたOrderオブジェクト
        """
        order = await self.find_by_id(order_id)
        if not order:
            return None

        # shippedまたはcancelledの場合は変更しない
        if order.status in (OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value):
            return order

        new_status = self.derive_order_status(order)
        if order.status != new_status:
            order.status = new_status
            await self._db.flush()

        return order

    async def find_pending_orders(
        self,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        """Find orders that don't have associated shipments.

        Returns orders that:
        - Have no associated ShipmentItem
        - Are not in SHIPPED or CANCELLED status

        Args:
            page: Page number (1-indexed)
            limit: Number of items per page

        Returns:
            Tuple of (orders, total_count)
        """
        from app.models.shipment import ShipmentItem

        # Subquery to find orders that have shipments
        orders_with_shipment = select(ShipmentItem.order_id).distinct()

        # Query for orders without shipments
        query = (
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.order_source),
            )
            .where(Order.id.notin_(orders_with_shipment))
            .where(Order.status.notin_([OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value]))
        )

        count_query = (
            select(func.count(Order.id))
            .where(Order.id.notin_(orders_with_shipment))
            .where(Order.status.notin_([OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value]))
        )

        # Get total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.order_by(Order.ordered_at.desc()).offset(offset).limit(limit)

        result = await self._db.execute(query)
        orders = list(result.scalars().all())

        return orders, total
