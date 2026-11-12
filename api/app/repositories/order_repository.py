"""Order repository for database operations."""

from collections.abc import Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, Row, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.manufacturer import Manufacturer
from app.models.manufacturing_data import ManufacturingData
from app.models.order import (
    Order,
    OrderItem,
    OrderItemStatus,
    OrderStatus,
    item_status_for_manufacturing_ready,
)
from app.models.order_source import OrderSource
from app.models.product import Product, ProductType
from app.models.shipment import Shipment, ShipmentItem

if TYPE_CHECKING:
    # 型注釈でのみ使う。リポジトリがスキーマを実行時に読み込まないようにする。
    from app.schemas.shipment import PendingOrderStatus


def order_list_conditions(
    *,
    status: OrderStatus | None = None,
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    search: str | None = None,
    shipping_from: date | None = None,
    shipping_to: date | None = None,
) -> list[ColumnElement[bool]]:
    """受注一覧の絞り込み条件（商品種別を除く）を組み立てる.

    受注一覧（``find_all``）とデータ出力（``find_item_rows_for_export``）が同じ条件で
    絞り込めるよう、1 か所にまとめている。商品種別だけは 1 行の単位が違う
    （一覧は受注、データ出力は受注明細）ので、それぞれの呼び出し側で組み立てる。
    """
    conditions: list[ColumnElement[bool]] = []
    if status:
        conditions.append(Order.status == status.value)
    if ordered_from:
        conditions.append(func.date(Order.ordered_at) >= ordered_from)
    if ordered_to:
        conditions.append(func.date(Order.ordered_at) <= ordered_to)
    if search:
        conditions.append(
            Order.order_number.ilike(f"%{search}%") | Order.customer_name.ilike(f"%{search}%")
        )
    if shipping_from:
        conditions.append(Order.estimated_shipping_date >= shipping_from)
    if shipping_to:
        conditions.append(Order.estimated_shipping_date <= shipping_to)
    return conditions


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
        shipping_from: date | None = None,
        shipping_to: date | None = None,
    ) -> tuple[list[Order], int]:
        """Find all orders with pagination and filters."""
        query = select(Order).options(
            selectinload(Order.items),
            selectinload(Order.order_source),
        )
        count_query = select(func.count(Order.id))

        conditions = order_list_conditions(
            status=status,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            search=search,
            shipping_from=shipping_from,
            shipping_to=shipping_to,
        )
        if product_type:
            # Filter orders that have items with the specified product type
            conditions.append(
                Order.id.in_(
                    select(OrderItem.order_id).where(
                        OrderItem.product_type == product_type.value
                    )
                )
            )
        if conditions:
            query = query.where(*conditions)
            count_query = count_query.where(*conditions)

        # Get total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.order_by(Order.ordered_at.desc()).offset(offset).limit(limit)

        result = await self._db.execute(query)
        orders = list(result.scalars().all())

        return orders, total

    async def find_item_rows_for_export(
        self,
        columns: Sequence[Any],
        *,
        status: OrderStatus | None = None,
        product_type: ProductType | None = None,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        search: str | None = None,
        shipping_from: date | None = None,
        shipping_to: date | None = None,
        sort: Any | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> Sequence[Row[Any]]:
        """データ出力用に、受注明細 1 件を 1 行として指定の列を取り出す（ADR-0023）.

        明細に受注・受注元・商品マスタ・メーカー・製造データ・配送を結合する。
        ``columns`` / ``sort`` はこれらのモデルの列（または列からなる式）であること。

        絞り込みは受注一覧と同じ条件（``order_list_conditions``）。ただし商品種別は
        1 行の単位に合わせて **明細の** 商品種別で絞る（受注一覧は「その種別の明細を含む受注」）。

        並べ替えは ``sort`` の後に、受注一覧と同じ受注日時の新しい順・注文番号・明細の登録順で
        決定的に並べる。NULL は昇順・降順とも末尾に置く。

        ``limit`` / ``offset`` を渡すと、並べた結果のその範囲だけ返す（画面のプレビュー用）。
        """
        # 配送は受注単位で 1 件（ShipmentService が重複作成を弾いている）。
        # 万一重複していても明細 1 行を崩さないよう、受注ごとに最新の 1 件だけを結合する。
        latest_shipment = (
            select(ShipmentItem.order_id, ShipmentItem.shipment_id)
            .distinct(ShipmentItem.order_id)
            .order_by(ShipmentItem.order_id, ShipmentItem.created_at.desc())
            .subquery()
        )

        query = (
            select(*columns)
            .select_from(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .outerjoin(OrderSource, Order.order_source_id == OrderSource.id)
            .outerjoin(Product, OrderItem.product_id == Product.id)
            .outerjoin(Manufacturer, Product.manufacturer_id == Manufacturer.id)
            .outerjoin(
                ManufacturingData, OrderItem.manufacturing_data_id == ManufacturingData.id
            )
            .outerjoin(latest_shipment, latest_shipment.c.order_id == Order.id)
            .outerjoin(Shipment, Shipment.id == latest_shipment.c.shipment_id)
        )

        conditions = self._export_conditions(
            status=status,
            product_type=product_type,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            search=search,
            shipping_from=shipping_from,
            shipping_to=shipping_to,
        )
        if conditions:
            query = query.where(*conditions)

        order_by: list[Any] = []
        if sort is not None:
            order_by.append((sort.desc() if descending else sort.asc()).nulls_last())
        order_by.extend(
            [
                Order.ordered_at.desc(),
                Order.order_number.asc(),
                OrderItem.created_at.asc(),
                OrderItem.id.asc(),
            ]
        )
        query = query.order_by(*order_by)
        if limit is not None:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        result = await self._db.execute(query)
        return result.all()

    async def count_item_rows_for_export(
        self,
        *,
        status: OrderStatus | None = None,
        product_type: ProductType | None = None,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        search: str | None = None,
        shipping_from: date | None = None,
        shipping_to: date | None = None,
    ) -> int:
        """``find_item_rows_for_export`` が返す行数（= 対象の受注明細の件数）.

        絞り込みは受注と明細の列だけを見るので、他のテーブルは結合しない
        （結合先はどれも明細 1 件につき高々 1 件なので、行数は変わらない）。
        """
        query = (
            select(func.count(OrderItem.id))
            .select_from(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
        )
        conditions = self._export_conditions(
            status=status,
            product_type=product_type,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            search=search,
            shipping_from=shipping_from,
            shipping_to=shipping_to,
        )
        if conditions:
            query = query.where(*conditions)
        result = await self._db.execute(query)
        return int(result.scalar_one())

    @staticmethod
    def _export_conditions(
        *,
        status: OrderStatus | None,
        product_type: ProductType | None,
        ordered_from: date | None,
        ordered_to: date | None,
        search: str | None,
        shipping_from: date | None,
        shipping_to: date | None,
    ) -> list[ColumnElement[bool]]:
        """データ出力の絞り込み条件（商品種別は明細の種別で絞る）."""
        conditions = order_list_conditions(
            status=status,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            search=search,
            shipping_from=shipping_from,
            shipping_to=shipping_to,
        )
        if product_type:
            conditions.append(OrderItem.product_type == product_type.value)
        return conditions

    async def create(self, order: Order) -> Order:
        """Create a new order."""
        self._db.add(order)
        await self._db.flush()
        await self._db.refresh(order)
        # Reload order with items to avoid lazy loading issues
        reloaded = await self.find_by_id(order.id)
        # 直前に flush / refresh しているので必ず見つかる
        assert reloaded is not None
        return reloaded

    async def update(self, order: Order) -> Order:
        """Update an existing order."""
        await self._db.flush()
        await self._db.refresh(order)
        # Reload order with items to avoid lazy loading issues
        reloaded = await self.find_by_id(order.id)
        # 直前に flush / refresh しているので必ず見つかる
        assert reloaded is not None
        return reloaded

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
    ) -> list[dict[str, Any]]:
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
    ) -> list[dict[str, Any]]:
        """メーカー別のORDERED受注明細サマリーを取得（OrderItem.statusベース）"""
        from app.models.manufacturer import Manufacturer
        from app.models.product import Product

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
            .where(Manufacturer.is_active.is_(True))
            .group_by(Manufacturer.id)
            .having(func.count(OrderItem.id) > 0)
            .order_by(func.max(Order.ordered_at).desc())
        )

        result = await self._db.execute(query)
        return [dict(row._mapping) for row in result.all()]

    async def find_unnotified_ordered_items_by_manufacturer(
        self, manufacturer_id: str
    ) -> list[tuple[str, int]]:
        """メーカー宛の日次発注メールにまだ載せていない明細を取得する.

        対象明細 = OrderItem WHERE Product.manufacturer_id = manufacturer_id
                   AND OrderItem.manufacturer_notified_at IS NULL
                   AND OrderItem.status IN (発注済み, 製造中, 納入済み)

        送信処理の時点のステータスが発注済みかどうかでは絞らない。送信処理より先に
        製造中へ進んだ明細も、一度も通知していなければ載せる。発注準備中（製造データが
        未準備）とキャンセル済みは発注できないので載せず、発注済みになった後の回で載せる。

        Returns:
            [(order_item_id, quantity), ...]
        """
        from app.models.product import Product

        query = (
            select(OrderItem.id, OrderItem.quantity)
            .join(Product, Product.id == OrderItem.product_id)
            .where(Product.manufacturer_id == manufacturer_id)
            .where(OrderItem.manufacturer_notified_at.is_(None))
            .where(
                OrderItem.status.in_(
                    [
                        OrderItemStatus.ORDERED.value,
                        OrderItemStatus.MANUFACTURING.value,
                        OrderItemStatus.DELIVERED.value,
                    ]
                )
            )
        )
        result = await self._db.execute(query)
        return [(row.id, row.quantity) for row in result.all()]

    async def mark_manufacturer_notified(
        self, order_item_ids: list[str], notified_at: datetime
    ) -> None:
        """明細をメーカー宛の日次発注メールで通知済みにする."""
        if not order_item_ids:
            return
        await self._db.execute(
            update(OrderItem)
            .where(OrderItem.id.in_(order_item_ids))
            .values(manufacturer_notified_at=notified_at)
            .execution_options(synchronize_session=False)
        )
        await self._db.flush()

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
    ) -> Sequence[Row[Any]]:
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
        from app.models.manufacturer import Manufacturer
        from app.models.product import Product

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

        # 納品予定日フィルター。一覧に表示している明細の納品予定日（注文作成時に営業日・
        # 〆切時刻を考慮して確定した値）で絞り込む。受注日 + メーカーのリードタイムを
        # 暦日で足し直すと表示と食い違うため使わない。
        if expected_delivery_from:
            query = query.where(OrderItem.expected_delivery_date >= expected_delivery_from)

        if expected_delivery_to:
            query = query.where(OrderItem.expected_delivery_date <= expected_delivery_to)

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
    ) -> Sequence[Row[Any]]:
        """全メーカー横断の受注明細を詳細情報付きで取得

        メーカー別の一覧（find_ordered_items_by_manufacturer_detail）と同じく
        OrderItem.status で絞り込み、注文ステータスによる除外は行わない。
        発送完了になった注文の明細も納入済みの明細として残る（REQ-0065）。

        Args:
            status: ステータスフィルター（OrderItem.statusでフィルタ、None の場合は全て）
            ordered_from: 発注日From
            ordered_to: 発注日To
            product_type: 商品タイプ
            search: キーワード検索（注文番号・製品番号・商品名）
            manufacturer_id: メーカーIDフィルター
            expected_delivery_from: 納品予定日From
            expected_delivery_to: 納品予定日To

        Returns:
            受注明細のタプルリスト（OrderItem, order_number, ordered_at, customer_name, cost, item_status, manufacturer_id, manufacturer_name, lead_time_days）
        """
        from app.models.manufacturer import Manufacturer
        from app.models.product import Product

        query = (
            select(
                OrderItem,
                Order.order_number,
                Order.ordered_at,
                Order.customer_name,
                Product.cost,
                OrderItem.status,
                Manufacturer.id.label("manufacturer_id"),
                Manufacturer.name.label("manufacturer_name"),
                Manufacturer.lead_time_days,
            )
            .join(Order, OrderItem.order_id == Order.id)
            .join(Product, OrderItem.product_id == Product.id)
            .join(Manufacturer, Product.manufacturer_id == Manufacturer.id)
        )

        # ステータスフィルター（OrderItem.statusでフィルタ）
        if status:
            query = query.where(OrderItem.status == status)

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

        # 納品予定日フィルター。一覧に表示している明細の納品予定日（注文作成時に営業日・
        # 〆切時刻を考慮して確定した値）で絞り込む。受注日 + メーカーのリードタイムを
        # 暦日で足し直すと表示と食い違うため使わない。
        if expected_delivery_from:
            query = query.where(OrderItem.expected_delivery_date >= expected_delivery_from)

        if expected_delivery_to:
            query = query.where(OrderItem.expected_delivery_date <= expected_delivery_to)

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

        # 発注ゲート: ORDERED→MANUFACTURING では、製造データが必要な明細のうち
        # ready でないものは遷移させない（未readyは ORDERED のまま保留）。
        if new_status == OrderItemStatus.MANUFACTURING:
            items = [item for item in items if item.is_manufacturing_ready]

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

        導出ルール（優先順位）:
        - "shipped": Shipmentが存在し、shipped状態（この関数では判定しない、サービス層で処理）
        - "cancelled": 全OrderItemが "cancelled"
        - "delivered": 全OrderItemが "delivered"
        - "manufacturing": 1つ以上のOrderItemが "manufacturing"
        - "preparing_order": 1つ以上のOrderItemが "preparing_order"（製造データ未準備）
        - "ordered": それ以外

        Args:
            order: Orderオブジェクト（itemsがロード済みであること）

        Returns:
            str: 導出されたステータス
        """
        if not order.items:
            return OrderStatus.ORDERED.value

        statuses = [item.status for item in order.items]

        # 全てcancelledなら"cancelled"（キャンセルは注文単位なので全明細が揃う）
        if all(s == OrderItemStatus.CANCELLED.value for s in statuses):
            return OrderStatus.CANCELLED.value

        # 全てdeliveredなら"delivered"
        if all(s == OrderItemStatus.DELIVERED.value for s in statuses):
            return OrderStatus.DELIVERED.value

        # 1つでもmanufacturingがあれば"manufacturing"
        if any(s == OrderItemStatus.MANUFACTURING.value for s in statuses):
            return OrderStatus.MANUFACTURING.value

        # 1つでも発注準備中（製造データ未準備）があれば"preparing_order"
        if any(s == OrderItemStatus.PREPARING_ORDER.value for s in statuses):
            return OrderStatus.PREPARING_ORDER.value

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

    async def sync_item_status_for_manufacturing_data(
        self, manufacturing_data_id: str, *, ready: bool
    ) -> set[str]:
        """製造データの ready 状態を、それを参照する明細の統合ステータスへ波及させる.

        ready=True: 参照する「発注準備中」明細を「発注済み」へ昇格する（生成完了時）。
        ready=False: 参照する「発注済み」明細を「発注準備中」へ戻す（再作成の開始時）。
        いずれも「製造中」/「納入済み」の明細（発注済みの後工程）は対象外。
        影響を受けた注文の Order.status も再導出する。

        Returns:
            影響を受けた order_id の集合。
        """
        from_status = (
            OrderItemStatus.PREPARING_ORDER.value
            if ready
            else OrderItemStatus.ORDERED.value
        )
        to_status = (
            OrderItemStatus.ORDERED.value
            if ready
            else OrderItemStatus.PREPARING_ORDER.value
        )
        result = await self._db.execute(
            update(OrderItem)
            .where(
                OrderItem.manufacturing_data_id == manufacturing_data_id,
                OrderItem.status == from_status,
            )
            .values(status=to_status)
            .returning(OrderItem.order_id)
            .execution_options(synchronize_session=False)
        )
        affected_order_ids = {row[0] for row in result.all()}
        await self._db.flush()

        # 波及した各注文の Order.status を再導出する。
        for order_id in affected_order_ids:
            await self.update_order_derived_status(order_id)

        return affected_order_ids

    def apply_cancellation_to_items(self, order: Order, *, cancelled: bool) -> None:
        """注文のキャンセル状態を、配下の明細の統合ステータスへ波及させる.

        derive_order_status（明細→注文）の逆向きにあたる。メーカー画面・メーカーポータルは
        明細ステータス（OrderItem.status）を表示・集計するため、注文だけをキャンセルすると
        明細が「発注済み」のまま残ってしまう。

        cancelled=True: 全明細を「キャンセル済み」にする。
        cancelled=False: キャンセルを解除した注文の明細をライフサイクルに戻す。
            製造データが未 ready の明細は「発注準備中」、それ以外は「発注済み」。

        ロード済みの Order を書き換えるだけなので、呼び出し元が続けて行う
        update() / update_status() の flush で明細の UPDATE も一緒に発行される。
        """
        for item in order.items:
            if cancelled:
                item.status = OrderItemStatus.CANCELLED.value
            elif item.status == OrderItemStatus.CANCELLED.value:
                item.status = item_status_for_manufacturing_ready(
                    item.is_manufacturing_ready
                )

    async def has_manufacturing_or_delivered_items(
        self, manufacturing_data_id: str
    ) -> bool:
        """指定した製造データを参照する明細に「製造中」/「納入済み」が1件でもあるか.

        製造データの再作成ゲート判定に使う（既に着手済みの in-production 注文を保護する）。
        """
        result = await self._db.execute(
            select(func.count(OrderItem.id)).where(
                OrderItem.manufacturing_data_id == manufacturing_data_id,
                OrderItem.status.in_(
                    [
                        OrderItemStatus.MANUFACTURING.value,
                        OrderItemStatus.DELIVERED.value,
                    ]
                ),
            )
        )
        return (result.scalar() or 0) > 0

    async def find_pending_orders(
        self,
        page: int = 1,
        limit: int = 20,
        status: "PendingOrderStatus | None" = None,
        estimated_shipping_date_from: date | None = None,
        estimated_shipping_date_to: date | None = None,
        search: str | None = None,
    ) -> tuple[list[Order], int]:
        """Find orders that don't have associated shipments.

        Returns orders that:
        - Have no associated ShipmentItem
        - Are not in SHIPPED or CANCELLED status

        Args:
            page: Page number (1-indexed)
            limit: Number of items per page
            status: Filter by PendingOrderStatus (preparing)
            search: 配送一覧のキーワード検索。宛先名（customer_name）と注文番号
                （order_number）に部分一致させる。実配送側と同じ検索語で絞り込むために
                受け取る（BUG-0001 / REQ-0048）

        Returns:
            Tuple of (orders, total_count)
        """
        from app.models.shipment import ShipmentItem
        from app.schemas.shipment import PendingOrderStatus

        # Subquery to find orders that have shipments
        orders_with_shipment = select(ShipmentItem.order_id).distinct()

        # Base query for orders without shipments
        base_conditions: list[ColumnElement[bool]] = [
            Order.id.notin_(orders_with_shipment),
            Order.status.notin_([OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value]),
        ]

        # Apply status filter based on OrderItem statuses
        # Note: Only PREPARING status exists now since AWAITING_SHIPMENT orders
        # automatically get a Shipment created when all items are DELIVERED
        if status == PendingOrderStatus.PREPARING:
            # Orders where NOT all items are DELIVERED
            # (i.e., at least one item is not DELIVERED)
            non_delivered_items = (
                select(OrderItem.order_id)
                .where(OrderItem.status != OrderItemStatus.DELIVERED.value)
                .distinct()
            )
            base_conditions.append(Order.id.in_(non_delivered_items))

        if estimated_shipping_date_from:
            base_conditions.append(Order.estimated_shipping_date >= estimated_shipping_date_from)
        if estimated_shipping_date_to:
            base_conditions.append(Order.estimated_shipping_date <= estimated_shipping_date_to)

        if search:
            search_pattern = f"%{search}%"
            base_conditions.append(
                or_(
                    Order.customer_name.ilike(search_pattern),
                    Order.order_number.ilike(search_pattern),
                )
            )

        # Query for orders without shipments
        query = (
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.order_source),
            )
            .where(*base_conditions)
        )

        count_query = (
            select(func.count(Order.id))
            .where(*base_conditions)
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
