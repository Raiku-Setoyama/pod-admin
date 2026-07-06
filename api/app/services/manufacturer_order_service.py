"""Manufacturer order service for managing orders by manufacturer."""

import logging
import os
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import Order, OrderItem, OrderItemStatus
from app.repositories.manufacturer_repository import ManufacturerRepository
from app.repositories.manufacturing_data_repository import ManufacturingDataRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.schemas.manufacturer import (
    AllManufacturerOrderItemListResponse,
    AllManufacturerOrderItemResponse,
    ManufacturerOrderItemListResponse,
    ManufacturerOrderItemResponse,
    ManufacturerOrderStatusUpdate,
    ManufacturerOrderSummary,
    ManufacturerOrderSummaryListResponse,
)
from app.utils.exceptions import (
    ManufacturingDataNotReadyError,
    NoOrderedItemsError,
    NotFoundError,
)
from app.utils.file_storage import FileStorage
from app.utils.order_list_generator import OrderListGenerator, get_product_type_name
from app.utils.stand_file_config import load_stand_file
from app.utils.zip_builder import ZipBuilder

logger = logging.getLogger(__name__)


class ManufacturerOrderService:
    """Service for manufacturer order operations."""

    def __init__(
        self,
        order_repo: OrderRepository,
        manufacturer_repo: ManufacturerRepository,
        shipment_repo: ShipmentRepository,
        mfg_repo: ManufacturingDataRepository | None = None,
        file_storage: FileStorage | None = None,
    ):
        self._order_repo = order_repo
        self._manufacturer_repo = manufacturer_repo
        self._shipment_repo = shipment_repo
        self._mfg_repo = mfg_repo
        self._file_storage = file_storage
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
        expected_delivery_from: date | None = None,
        expected_delivery_to: date | None = None,
    ) -> ManufacturerOrderItemListResponse:
        """メーカー別受注明細一覧を取得

        Args:
            manufacturer_id: メーカーID
            ordered_from: 発注日From
            ordered_to: 発注日To
            product_type: 商品タイプ
            status: ステータスフィルター（None の場合は shipped 以外の全て）
            search: キーワード検索（注文番号・製品番号・商品名）
            expected_delivery_from: 納品予定日From
            expected_delivery_to: 納品予定日To
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
            expected_delivery_from=expected_delivery_from,
            expected_delivery_to=expected_delivery_to,
        )

        items = []
        total_quantity = 0
        total_amount = 0

        for order_item, order_number, ordered_at, customer_name, cost, item_status, order_status, lead_time_days in rows:
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
                    status=item_status,  # OrderItem.statusを使用
                    item_status=item_status,  # 新フィールド
                    lead_time_days=lead_time_days,
                    expected_delivery_date=order_item.expected_delivery_date,
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

    async def get_all_order_items(
        self,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        product_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
        manufacturer_id: str | None = None,
        expected_delivery_from: date | None = None,
        expected_delivery_to: date | None = None,
    ) -> AllManufacturerOrderItemListResponse:
        """全メーカー横断の受注明細一覧を取得

        Args:
            ordered_from: 発注日From
            ordered_to: 発注日To
            product_type: 商品タイプ
            status: ステータスフィルター（None の場合は shipped 以外の全て）
            search: キーワード検索（注文番号・製品番号・商品名）
            manufacturer_id: メーカーIDフィルター
            expected_delivery_from: 納品予定日From
            expected_delivery_to: 納品予定日To
        """
        rows = await self._order_repo.find_all_ordered_items_detail(
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            product_type=product_type,
            status=status,
            search=search,
            manufacturer_id=manufacturer_id,
            expected_delivery_from=expected_delivery_from,
            expected_delivery_to=expected_delivery_to,
        )

        items = []
        total_quantity = 0
        total_amount = 0

        for order_item, order_number, ordered_at, customer_name, cost, order_status, mfr_id, mfr_name, lead_time_days in rows:
            items.append(
                AllManufacturerOrderItemResponse(
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
                    manufacturer_id=mfr_id,
                    manufacturer_name=mfr_name,
                    lead_time_days=lead_time_days,
                    expected_delivery_date=order_item.expected_delivery_date,
                )
            )
            total_quantity += order_item.quantity
            total_amount += order_item.price * order_item.quantity

        return AllManufacturerOrderItemListResponse(
            items=items,
            total=len(items),
            total_quantity=total_quantity,
            total_amount=total_amount,
        )

    async def update_order_status(
        self,
        manufacturer_id: str,
        data: ManufacturerOrderStatusUpdate,
    ) -> tuple[int, int]:
        """メーカーの受注ステータスを一括更新（OrderItem単位）

        OrderItemのステータスを更新し、Order.statusを導出して更新します。
        全OrderItemがdeliveredになった場合のみShipmentを自動作成します。
        Shipment作成に失敗した場合、トランザクション全体がロールバックされます。

        Returns:
            tuple[int, int]: (更新されたOrderItem数, 作成されたShipment数)
        """
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise NotFoundError("Manufacturer", manufacturer_id)

        # Convert string status to OrderItemStatus enum
        new_status = OrderItemStatus(data.status)

        # 製造中への遷移時は、製造データが未readyの明細を拒否（誤操作防止）
        if new_status == OrderItemStatus.MANUFACTURING:
            await self._assert_manufacturing_ready(manufacturer_id, data.order_item_ids)

        # OrderItem単位でステータス更新
        updated_items, affected_order_ids = await self._order_repo.update_item_status_by_manufacturer(
            manufacturer_id=manufacturer_id,
            new_status=new_status,
            order_item_ids=data.order_item_ids,
        )

        # 影響を受けた各Orderのステータスを導出して更新
        shipments_created = 0
        for order_id in affected_order_ids:
            order = await self._order_repo.update_order_derived_status(order_id)

            # 全OrderItemがdeliveredになった場合のみShipmentを作成
            if order and new_status == OrderItemStatus.DELIVERED:
                all_delivered = await self._order_repo.check_all_items_delivered(order_id)
                if all_delivered:
                    created = await self._create_shipment_for_order(order)
                    if created:
                        shipments_created += 1

        return len(updated_items), shipments_created

    async def _create_shipment_for_order(self, order: Order) -> bool:
        """Create a shipment for the delivered order.

        This method is idempotent - if a shipment already exists for the order,
        it will not create a duplicate.

        Returns:
            bool: True if a shipment was created, False if it already existed
        """
        # Check if shipment already exists (prevent duplicates)
        if await self._shipment_repo.exists_for_order(order.id):
            return False

        # Customer info is now accessed via shipment.first_order relationship
        await self._shipment_repo.create(order_ids=[order.id])
        return True

    # Product type -> manufacturing data extension mapping
    _MANUFACTURING_EXT: dict[str, str] = {
        "tshirt": "_front.pdf",
        "tote_bag": ".pdf",
        "acrylic_keychain": ".ai",
        "acrylic_stand": ".ai",
        "sticker": ".ai",
    }

    async def generate_order_documents(
        self,
        manufacturer_id: str,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        product_type: str | None = None,
        order_item_ids: list[str] | None = None,
        status: str | None = None,
        update_status: bool = True,
    ) -> tuple[bytes, str]:
        """発注資料ZIPを生成

        全ステータスの明細をダウンロード可能。
        update_status=True かつメーカーポータルからの呼び出しの場合、
        「発注中（ORDERED）」ステータスの明細のみ「製造中（MANUFACTURING）」に更新する。

        命名規則:
        - ZIP名: TAPI_{メーカー名}_発注資料.zip
        - タイプフォルダ: {商品種類カテゴリ}_{YYYYMMDD}
        - Tシャツ特殊: Tシャツ- {印刷位置} -_{YYYYMMDD}
        - XLSX名: {prefix}発注リスト_{YYYYMMDD}.xlsx
        - 画像: {注文番号}_{製造番号}.png
        - 製造データ①: {商品フルネーム}【{数量}個】_{注文番号}_{製造番号}_{MMDD}.{ext}
        - 製造データ②: アクリルフィギュアのみ _stand.ai
        - 注文番号別サブフォルダに配置（XLSXはタイプフォルダ直下）

        Args:
            manufacturer_id: メーカーID
            ordered_from: 発注日From（オプション）
            ordered_to: 発注日To（オプション）
            product_type: 商品種類フィルタ（オプション）
            order_item_ids: 対象のOrderItem ID（オプション、指定がなければ全て）
            status: ステータスフィルタ（オプション、指定がなければ全ステータス）
            update_status: ステータスを更新するかどうか（メーカーポータル=True、管理者=False）

        Returns:
            tuple[bytes, str]: (ZIPファイルのバイト列, ファイル名)

        Raises:
            NotFoundError: メーカーが存在しない場合
            NoOrderedItemsError: ダウンロード対象の明細が0件の場合
        """
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise NotFoundError("Manufacturer", manufacturer_id)

        # 指定されたステータス（または全ステータス）の明細を取得
        rows = await self._order_repo.find_ordered_items_by_manufacturer_detail(
            manufacturer_id,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            product_type=product_type,
            status=status,
        )

        # order_item_idsが指定された場合、そのIDのみにフィルタリング
        if order_item_ids:
            rows = [row for row in rows if row[0].id in order_item_ids]

        # ダウンロード対象の明細が0件の場合はエラー
        if not rows:
            raise NoOrderedItemsError()

        # 製造データが ready でない v2 明細は発注資料から除外し ORDERED のまま保留する
        rows, held_count, mfg_content_by_item = await self._partition_by_readiness(rows)
        if not rows:
            raise NoOrderedItemsError()
        if held_count:
            logger.info(
                "発注資料生成: 製造データ未readyの %d 明細を保留 (manufacturer=%s)",
                held_count,
                manufacturer_id,
            )

        # 発注中ステータスのorder_item_idsを記録（ステータス更新対象、保留分は含めない）
        # row[5]はitem_status
        ordered_item_ids = [
            row[0].id for row in rows if row[5] == OrderItemStatus.ORDERED.value
        ]

        # グループキー別にアイテムを整理
        # Tシャツは (product_type, position) でグループ、他は (product_type,) でグループ
        items_by_group: dict[tuple, list[dict]] = {}
        for order_item, order_number, ordered_at, customer_name, cost, item_status, order_status, lead_time_days in rows:
            item_product_type = order_item.product_type
            if item_product_type == "tshirt":
                group_key = (item_product_type, order_item.position or "")
            else:
                group_key = (item_product_type,)

            if group_key not in items_by_group:
                items_by_group[group_key] = []

            items_by_group[group_key].append(
                {
                    "ordered_date": ordered_at,
                    "order_number": order_number,
                    "uid": order_item.uid,
                    "product_name": order_item.product_name,
                    "product_type": item_product_type,
                    "quantity": order_item.quantity,
                    "size": order_item.size,
                    "position": order_item.position,
                    "color": order_item.color,
                    "cost": cost,
                    "design_image_url": order_item.design_image_url,
                    "thumbnail_image_url": order_item.thumbnail_image_url,
                    "mfg_content": mfg_content_by_item.get(order_item.id),
                }
            )

        # ZIP生成
        now = datetime.now()
        zip_builder = ZipBuilder()
        date_str = now.strftime("%Y%m%d")

        # タイプフォルダ名を収集
        type_folder_names: list[str] = []

        for group_key, group_items in items_by_group.items():
            item_product_type = group_key[0]
            product_type_name = get_product_type_name(item_product_type)

            # タイプフォルダ名の決定
            if item_product_type == "tshirt":
                position = group_key[1]
                type_folder = f"Tシャツ- {position} -_{date_str}"
                folder_prefix = f"Tシャツ- {position} -"
            else:
                type_folder = f"{product_type_name}_{date_str}"
                folder_prefix = product_type_name

            type_folder_names.append(type_folder)

            # Excel追加（CSV→XLSX変更）
            xlsx_filename = f"{folder_prefix}_発注リスト_{date_str}.xlsx"
            xlsx_content = self._order_list_gen.generate_order_list_xlsx(
                group_items, product_type=item_product_type
            )
            zip_builder.add_excel(f"{type_folder}/{xlsx_filename}", xlsx_content)

            # 各アイテムのファイルを注文番号フォルダに配置
            for item in group_items:
                order_number = item["order_number"]
                uid = item.get("uid") or "unknown"
                quantity = item["quantity"]
                ordered_date = item.get("ordered_date")

                # Build product detail: {商品種類} - {サイズ} - {位置} - {色}
                detail_parts = [product_type_name]
                if item.get("size"):
                    detail_parts.append(item["size"])
                if item.get("position"):
                    detail_parts.append(item["position"])
                if item.get("color"):
                    detail_parts.append(item["color"])
                product_detail = " - ".join(detail_parts)

                # MMDDを注文日から計算
                mmdd = ordered_date.strftime("%m%d") if ordered_date else ""

                # 製造データ①のファイル名
                ext = self._MANUFACTURING_EXT.get(item_product_type, ".ai")
                mfg_filename = (
                    f"{product_detail}【個数】{quantity}個"
                    f"_{order_number}_{uid}_{mmdd}{ext}"
                )

                # 注文番号フォルダのパスプレフィックス
                order_folder = f"{type_folder}/{order_number}"

                # 製造データ①: v2は保存済み生成ファイルを封入、旧v1はdesign_image_urlをDL
                mfg_content = item.get("mfg_content")
                if mfg_content is not None:
                    zip_builder.add_file(f"{order_folder}/{mfg_filename}", mfg_content)
                elif item.get("design_image_url"):
                    content, _original_filename = await self._download_file(
                        item["design_image_url"]
                    )
                    if content:
                        zip_builder.add_file(f"{order_folder}/{mfg_filename}", content)

                # サムネイル画像 → {注文番号}_{製造番号}.png
                if item.get("thumbnail_image_url"):
                    content, _filename = await self._download_file(
                        item["thumbnail_image_url"]
                    )
                    if content:
                        image_filename = f"{order_number}_{uid}.png"
                        zip_builder.add_file(
                            f"{order_folder}/{image_filename}", content
                        )

                # 製造データ②（アクリルフィギュアのみ: _stand.ai）
                if item_product_type == "acrylic_stand":
                    stand_content = load_stand_file(item.get("size"))
                    if stand_content:
                        stand_filename = (
                            f"{product_detail}【個数】{quantity}個"
                            f"_{order_number}_{uid}_{mmdd}_stand.ai"
                        )
                        zip_builder.add_file(
                            f"{order_folder}/{stand_filename}", stand_content
                        )

        # ZIP生成
        zip_bytes = zip_builder.build()

        # メーカーポータルからのダウンロード時のみ、発注中の明細を「製造中」に更新
        if update_status and ordered_item_ids:
            _, affected_order_ids = await self._order_repo.update_item_status_by_manufacturer(
                manufacturer_id=manufacturer_id,
                new_status=OrderItemStatus.MANUFACTURING,
                order_item_ids=ordered_item_ids,
            )
            # 影響を受けた各Orderのステータスを導出して更新
            for order_id in affected_order_ids:
                await self._order_repo.update_order_derived_status(order_id)

        # ZIP名: TAPI_{メーカー名}_発注資料.zip
        zip_name = f"TAPI_{manufacturer.name}_発注資料.zip"

        return zip_bytes, zip_name

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

    def _is_mfg_item(self, order_item: OrderItem) -> bool:
        """製造データ生成対象の v2 明細か（product_code か manufacturing_data_id を持つ）."""
        return bool(order_item.product_code) or order_item.manufacturing_data_id is not None

    async def _partition_by_readiness(
        self, rows: list[tuple[Any, ...]]
    ) -> tuple[list[tuple[Any, ...]], int, dict[str, bytes]]:
        """rows を「発注可能」と「保留(未ready)」に分ける。

        旧v1明細は常に発注可能。v2明細は ready かつ保存ファイルが存在する場合のみ発注可能で、
        その生成ファイル bytes を返す。mfg_repo / file_storage 未設定時はゲート無効（全件発注可能）。
        """
        if self._mfg_repo is None or self._file_storage is None:
            return list(rows), 0, {}

        mfg_ids = [row[0].manufacturing_data_id for row in rows if row[0].manufacturing_data_id]
        mfg_map: dict[str, ManufacturingData] = {}
        if mfg_ids:
            mfg_map = {md.id: md for md in await self._mfg_repo.find_by_ids(mfg_ids)}

        includable: list[tuple[Any, ...]] = []
        held_count = 0
        content_by_item: dict[str, bytes] = {}
        for row in rows:
            order_item = row[0]
            if not self._is_mfg_item(order_item):
                includable.append(row)  # 旧v1明細はそのまま封入
                continue
            md = (
                mfg_map.get(order_item.manufacturing_data_id)
                if order_item.manufacturing_data_id
                else None
            )
            content: bytes | None = None
            if md is not None and md.status == MfgDataStatus.READY.value and md.file_path:
                content = await self._file_storage.get(md.file_path)
            if content is None:
                held_count += 1  # 未ready or 保存ファイル消失 → 保留
                continue
            content_by_item[order_item.id] = content
            includable.append(row)
        return includable, held_count, content_by_item

    async def _assert_manufacturing_ready(
        self, manufacturer_id: str, order_item_ids: list[str] | None
    ) -> None:
        """→MANUFACTURING 対象に未ready の v2 明細があれば拒否する（管理者の誤操作防止）."""
        if self._mfg_repo is None or self._file_storage is None:
            return
        candidates = await self._order_repo.find_manufacturer_items(
            manufacturer_id,
            order_item_ids=order_item_ids,
            statuses=[OrderItemStatus.ORDERED.value, OrderItemStatus.DELIVERED.value],
        )
        mfg_items = [oi for oi in candidates if self._is_mfg_item(oi)]
        if not mfg_items:
            return
        mfg_ids: list[str] = []
        for oi in mfg_items:
            if oi.manufacturing_data_id is not None:
                mfg_ids.append(oi.manufacturing_data_id)
        mfg_map: dict[str, ManufacturingData] = {}
        if mfg_ids:
            mfg_map = {md.id: md for md in await self._mfg_repo.find_by_ids(mfg_ids)}
        not_ready: list[str] = []
        for oi in mfg_items:
            md = mfg_map.get(oi.manufacturing_data_id) if oi.manufacturing_data_id else None
            ready = False
            if md is not None and md.status == MfgDataStatus.READY.value and md.file_path:
                ready = await self._file_storage.exists(md.file_path)
            if not ready:
                not_ready.append(oi.id)
        if not_ready:
            raise ManufacturingDataNotReadyError(not_ready)
