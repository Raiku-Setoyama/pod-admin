"""Manufacturer order service for managing orders by manufacturer."""

from datetime import date, datetime
from urllib.parse import urlparse
import os

import httpx

from app.models.order import Order, OrderStatus
from app.repositories.order_repository import OrderRepository
from app.repositories.manufacturer_repository import ManufacturerRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.schemas.manufacturer import (
    ManufacturerOrderSummary,
    ManufacturerOrderSummaryListResponse,
    ManufacturerOrderItemResponse,
    ManufacturerOrderItemListResponse,
    ManufacturerOrderStatusUpdate,
)
from app.utils.exceptions import NotFoundError, NoOrderedItemsError
from app.utils.order_list_generator import OrderListGenerator, get_product_type_name
from app.utils.zip_builder import ZipBuilder


class ManufacturerOrderService:
    """Service for manufacturer order operations."""

    def __init__(
        self,
        order_repo: OrderRepository,
        manufacturer_repo: ManufacturerRepository,
        shipment_repo: ShipmentRepository,
    ):
        self._order_repo = order_repo
        self._manufacturer_repo = manufacturer_repo
        self._shipment_repo = shipment_repo
        self._order_list_gen = OrderListGenerator()

    async def get_order_summary_list(
        self,
        page: int = 1,
        limit: int = 20,
    ) -> ManufacturerOrderSummaryListResponse:
        """メーカー別発注サマリー一覧を取得"""
        summaries = await self._order_repo.get_ordered_items_summary_by_manufacturer()

        total = len(summaries)
        offset = (page - 1) * limit
        paginated = summaries[offset : offset + limit]

        items = [
            ManufacturerOrderSummary(
                id=s["id"],
                name=s["name"],
                email=s["email"],
                phone=s["phone"],
                ordered_item_count=s["ordered_item_count"],
                total_quantity=s["total_quantity"] or 0,
                total_amount=s["total_amount"] or 0,
                lead_time_days=s["lead_time_days"],
                is_active=s["is_active"],
            )
            for s in paginated
        ]

        return ManufacturerOrderSummaryListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    async def get_order_items_by_manufacturer(
        self,
        manufacturer_id: str,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        product_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> ManufacturerOrderItemListResponse:
        """メーカー別受注明細一覧を取得

        Args:
            manufacturer_id: メーカーID
            ordered_from: 発注日From
            ordered_to: 発注日To
            product_type: 商品タイプ
            status: ステータスフィルター（None の場合は shipped 以外の全て）
            search: キーワード検索（注文番号・製品番号・商品名）
        """
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise NotFoundError("Manufacturer", manufacturer_id)

        rows = await self._order_repo.find_ordered_items_by_manufacturer_detail(
            manufacturer_id,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            product_type=product_type,
            status=status,
            search=search,
        )

        items = []
        total_quantity = 0
        total_amount = 0

        for order_item, order_number, ordered_at, customer_name, cost, order_status in rows:
            items.append(
                ManufacturerOrderItemResponse(
                    id=order_item.id,
                    order_id=order_item.order_id,
                    order_number=order_number,
                    uid=order_item.uid,
                    product_id=order_item.product_id,
                    product_name=order_item.product_name,
                    product_type=order_item.product_type,
                    price=order_item.price,
                    quantity=order_item.quantity,
                    size=order_item.size,
                    position=order_item.position,
                    color=order_item.color,
                    design_image_url=order_item.design_image_url,
                    thumbnail_image_url=order_item.thumbnail_image_url,
                    ordered_at=ordered_at,
                    customer_name=customer_name,
                    status=order_status,
                )
            )
            total_quantity += order_item.quantity
            total_amount += order_item.price * order_item.quantity

        return ManufacturerOrderItemListResponse(
            manufacturer_id=manufacturer_id,
            manufacturer_name=manufacturer.name,
            items=items,
            total=len(items),
            total_quantity=total_quantity,
            total_amount=total_amount,
        )

    async def update_order_status(
        self,
        manufacturer_id: str,
        data: ManufacturerOrderStatusUpdate,
    ) -> int:
        """メーカーの受注ステータスを一括更新

        delivered ステータスへの更新時は、各受注に対してShipmentを自動作成します。
        Shipment作成に失敗した場合、トランザクション全体がロールバックされます。
        """
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise NotFoundError("Manufacturer", manufacturer_id)

        # Convert string status to OrderStatus enum
        new_status = OrderStatus(data.status)

        updated_orders = await self._order_repo.update_status_by_manufacturer(
            manufacturer_id=manufacturer_id,
            new_status=new_status,
            order_item_ids=data.order_item_ids,
        )

        # delivered になった場合は Shipment を自動作成
        if new_status == OrderStatus.DELIVERED:
            for order in updated_orders:
                await self._create_shipment_for_order(order)

        return len(updated_orders)

    async def _create_shipment_for_order(self, order: Order) -> None:
        """Create a shipment for the delivered order.

        This method is idempotent - if a shipment already exists for the order,
        it will not create a duplicate.
        """
        # Check if shipment already exists (prevent duplicates)
        if await self._shipment_repo.exists_for_order(order.id):
            return

        # Customer info is now accessed via shipment.first_order relationship
        await self._shipment_repo.create(order_ids=[order.id])

    async def generate_order_documents(
        self,
        manufacturer_id: str,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        product_type: str | None = None,
        order_item_ids: list[str] | None = None,
    ) -> tuple[bytes, str]:
        """発注資料ZIPを生成

        ダウンロード対象は「発注中（ORDERED）」ステータスの明細のみ。
        ZIP生成成功後、対象明細のステータスを「製造中（MANUFACTURING）」に更新する。

        Args:
            manufacturer_id: メーカーID
            ordered_from: 発注日From（オプション）
            ordered_to: 発注日To（オプション）
            product_type: 商品種類フィルタ（オプション）
            order_item_ids: 対象のOrderItem ID（オプション、指定がなければ全て）

        Returns:
            tuple[bytes, str]: (ZIPファイルのバイト列, ファイル名)

        Raises:
            NotFoundError: メーカーが存在しない場合
            NoOrderedItemsError: 発注中の明細が0件の場合
        """
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise NotFoundError("Manufacturer", manufacturer_id)

        # 「発注中」ステータスの明細のみを取得
        rows = await self._order_repo.find_ordered_items_by_manufacturer_detail(
            manufacturer_id,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            product_type=product_type,
            status=OrderStatus.ORDERED.value,
        )

        # order_item_idsが指定された場合、そのIDのみにフィルタリング
        if order_item_ids:
            rows = [row for row in rows if row[0].id in order_item_ids]

        # 発注中の明細が0件の場合はエラー
        if not rows:
            raise NoOrderedItemsError()

        # ZIP生成対象のorder_item_idsを記録
        target_order_item_ids = [row[0].id for row in rows]

        # 商品タイプ別にグループ化
        items_by_type: dict[str, list[dict]] = {}
        for order_item, order_number, ordered_at, customer_name, cost, order_status in rows:
            item_product_type = order_item.product_type
            if item_product_type not in items_by_type:
                items_by_type[item_product_type] = []

            items_by_type[item_product_type].append(
                {
                    "ordered_date": ordered_at,
                    "order_number": order_number,
                    "uid": order_item.uid,
                    "product_name": order_item.product_name,
                    "quantity": order_item.quantity,
                    "size": order_item.size,
                    "position": order_item.position,
                    "color": order_item.color,
                    "cost": cost,
                    "design_image_url": order_item.design_image_url,
                    "thumbnail_image_url": order_item.thumbnail_image_url,
                }
            )

        # ZIP生成
        now = datetime.now()
        zip_builder = ZipBuilder()
        dir_name = ZipBuilder.create_directory_name(manufacturer.name, now)
        date_str = now.strftime("%Y%m%d")

        for item_product_type, type_items in items_by_type.items():
            product_type_name = get_product_type_name(item_product_type)
            type_folder = f"{dir_name}/{product_type_name}_{date_str}"

            # CSV追加
            csv_filename = f"{product_type_name}-発注リスト_{date_str}.csv"
            csv_content = self._order_list_gen.generate_order_list_csv(
                type_items, product_type=item_product_type
            )
            zip_builder.add_csv(f"{type_folder}/{csv_filename}", csv_content)

            # 画像ダウンロード・追加
            for item in type_items:
                order_folder = f"{type_folder}/{item['order_number']}"

                # デザイン画像（製造データ）
                if item.get("design_image_url"):
                    content, original_filename = await self._download_file(
                        item["design_image_url"]
                    )
                    if content:
                        # ai形式の場合はファイル名を {注文番号}_{製造番号}_{商品種類}.ai に変更
                        ext = os.path.splitext(original_filename)[1].lower()
                        if ext == ".ai":
                            uid = item.get("uid") or "unknown"
                            filename = f"{item['order_number']}_{uid}_{product_type_name}.ai"
                        else:
                            filename = original_filename
                        zip_builder.add_file(f"{order_folder}/{filename}", content)

                # サムネイル画像
                if item.get("thumbnail_image_url"):
                    content, filename = await self._download_file(
                        item["thumbnail_image_url"]
                    )
                    if content:
                        zip_builder.add_file(
                            f"{order_folder}/thumbnail_{filename}", content
                        )

        # ZIP生成
        zip_bytes = zip_builder.build()

        # ZIP生成成功後、対象明細のステータスを「製造中」に更新
        await self._order_repo.update_status_by_manufacturer(
            manufacturer_id=manufacturer_id,
            new_status=OrderStatus.MANUFACTURING,
            order_item_ids=target_order_item_ids,
        )

        return zip_bytes, f"{dir_name}.zip"

    async def _download_file(self, url: str) -> tuple[bytes | None, str]:
        """URLからファイルをダウンロード"""
        if not url:
            return None, ""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    parsed = urlparse(url)
                    filename = os.path.basename(parsed.path) or "file"
                    return response.content, filename
        except Exception:
            pass
        return None, ""
