"""Shipment service."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile

import csv
import io

import httpx

from app.models.order import OrderStatus
from app.models.shipment import Shipment, ShipmentStatus
from app.repositories.order_repository import OrderRepository
from app.repositories.order_source_repository import OrderSourceRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.models.order import OrderItemStatus
from app.schemas.shipment import (
    OrderItemSummary,
    PendingOrderResponse,
    PendingOrderStatus,
    ShipmentBulkStatusUpdate,
    ShipmentBulkStatusUpdateResponse,
    ShipmentCreate,
    ShipmentItemResponse,
    ShipmentListResponse,
    ShipmentListWithPendingResponse,
    ShipmentResponse,
    ShipmentStatusUpdate,
    TrackingFileImportError,
    TrackingFileImportResult,
    TrackingFileImportRowResult,
    TrackingImportRequest,
)
from app.utils.exceptions import InvalidStatusTransitionError, NotFoundError, ValidationError
from app.utils.file_storage import FileStorage
from app.utils.order_list_generator import format_product_detail
from app.utils.zip_builder import ZipBuilder

import chardet
import openpyxl

logger = logging.getLogger(__name__)


class ShipmentService:
    """Service for shipment operations."""

    def __init__(
        self,
        shipment_repo: ShipmentRepository,
        order_repo: OrderRepository,
        file_storage: FileStorage,
        order_source_repo: OrderSourceRepository | None = None,
        email_service: "EmailService | None" = None,
    ):
        from app.services.email_service import EmailService  # noqa: F811

        self._shipment_repo = shipment_repo
        self._order_repo = order_repo
        self._file_storage = file_storage
        self._order_source_repo = order_source_repo
        self._email_service = email_service

    async def create(self, data: ShipmentCreate) -> ShipmentResponse:
        """Create a new shipment."""
        # Verify all orders exist and are in the correct status
        for order_id in data.order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if not order:
                raise ValidationError(f"Order {order_id} not found")
            if order.status != OrderStatus.DELIVERED.value:
                raise ValidationError(f"Order {order_id} is not in delivered status")
            # Check if shipment already exists for this order (prevent duplicates)
            if await self._shipment_repo.exists_for_order(order_id):
                raise ValidationError(f"Order {order_id} already has a shipment")

        # Create shipment (customer info is accessed via first order relationship)
        shipment = await self._shipment_repo.create(order_ids=data.order_ids)

        return self._to_response(shipment)

    async def get_by_id(self, shipment_id: str) -> ShipmentResponse:
        """Get a shipment by ID."""
        shipment = await self._shipment_repo.find_by_id(shipment_id)
        if not shipment:
            raise NotFoundError("Shipment", shipment_id)
        return self._to_response(shipment)

    async def list(
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
    ) -> ShipmentListResponse:
        """List shipments with pagination and filters."""
        shipments, total = await self._shipment_repo.find_all(
            page=page,
            limit=limit,
            status=status,
            created_from=created_from,
            created_to=created_to,
            search=search,
            tracking_number=tracking_number,
            carrier=carrier,
            shipped_from=shipped_from,
            shipped_to=shipped_to,
            delivered_from=delivered_from,
            delivered_to=delivered_to,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        items = [self._to_response(shipment) for shipment in shipments]

        return ShipmentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    async def list_with_pending_orders(
        self,
        page: int = 1,
        limit: int = 20,
        shipment_status: ShipmentStatus | None = None,
        pending_order_status: PendingOrderStatus | None = None,
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
    ) -> ShipmentListWithPendingResponse:
        """List shipments with pending orders.

        Returns both existing shipments and orders without shipments (pending orders).
        Pending orders are displayed with "preparing" status.

        Args:
            shipment_status: Filter by ShipmentStatus (pending, ready, shipped).
                             If set, only shipments are returned.
            pending_order_status: Filter by PendingOrderStatus (preparing).
                                  If set, only pending orders are returned.
        """
        items: list = []
        shipment_total = 0
        pending_total = 0

        # If filtering by PendingOrderStatus, skip shipments
        if pending_order_status is None:
            # Get shipments
            shipments, shipment_total = await self._shipment_repo.find_all(
                page=page,
                limit=limit,
                status=shipment_status,
                created_from=created_from,
                created_to=created_to,
                search=search,
                tracking_number=tracking_number,
                carrier=carrier,
                shipped_from=shipped_from,
                shipped_to=shipped_to,
                delivered_from=delivered_from,
                delivered_to=delivered_to,
                estimated_shipping_date_from=estimated_shipping_date_from,
                estimated_shipping_date_to=estimated_shipping_date_to,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            # Convert shipments to responses
            items = [self._to_response(shipment) for shipment in shipments]

        # If filtering by ShipmentStatus, skip pending orders
        if shipment_status is None:
            # Get pending orders (orders without shipments)
            pending_orders, pending_total = await self._order_repo.find_pending_orders(
                page=page,
                limit=limit,
                status=pending_order_status,
                estimated_shipping_date_from=estimated_shipping_date_from,
                estimated_shipping_date_to=estimated_shipping_date_to,
            )
            # Convert pending orders to responses
            for order in pending_orders:
                items.append(self._to_pending_order_response(order))

        # Calculate total
        total = shipment_total + pending_total

        return ShipmentListWithPendingResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    def _to_pending_order_response(self, order) -> PendingOrderResponse:
        """Convert Order to PendingOrderResponse.

        Status is always 'preparing' since orders with all items delivered
        automatically get a Shipment created.
        """
        # Count items and delivered items
        item_count = len(order.items) if order.items else 0
        items_delivered = sum(
            1 for item in (order.items or [])
            if item.status == OrderItemStatus.DELIVERED.value
        )

        # Status is always PREPARING for pending orders
        status = PendingOrderStatus.PREPARING

        # Build customer address
        address_parts = [
            order.customer_postal_code or "",
            order.customer_address_prefecture or "",
            order.customer_address_city or "",
            order.customer_address_building or "",
        ]
        customer_address = " ".join(p for p in address_parts if p)

        # Build order items summary
        order_items_summary = [
            OrderItemSummary(
                id=item.id,
                product_name=item.product_name,
                product_type=item.product_type,
                quantity=item.quantity,
                status=item.status,
                thumbnail_image_url=item.thumbnail_image_url,
            )
            for item in (order.items or [])
        ]

        return PendingOrderResponse(
            type="pending_order",
            order_id=order.id,
            order_number=order.order_number,
            customer_name=order.customer_name,
            customer_address=customer_address,
            item_count=item_count,
            items_delivered=items_delivered,
            estimated_shipping_date=order.estimated_shipping_date,
            status=status,
            created_at=order.ordered_at,
            order_items=order_items_summary,
        )

    async def update_status(
        self, shipment_id: str, data: ShipmentStatusUpdate
    ) -> ShipmentResponse:
        """Update shipment status."""
        shipment = await self._shipment_repo.find_by_id(shipment_id)
        if not shipment:
            raise NotFoundError("Shipment", shipment_id)

        current_status = ShipmentStatus(shipment.status)
        if not self._is_valid_transition(current_status, data.status):
            raise InvalidStatusTransitionError(current_status.value, data.status.value)

        # Handle reverting from shipped to pending/ready
        is_reverting_from_shipped = (
            current_status == ShipmentStatus.SHIPPED and
            data.status in (ShipmentStatus.PENDING, ShipmentStatus.READY)
        )

        shipment.status = data.status.value

        if data.tracking_number is not None:
            shipment.tracking_number = data.tracking_number
        if data.carrier is not None:
            shipment.carrier = data.carrier
        if data.note is not None:
            shipment.note = data.note

        # Set timestamps
        if data.status == ShipmentStatus.SHIPPED:
            shipment.shipped_at = datetime.now(timezone.utc)
            # Set delivered_at (配送完了予定日時) if provided, or use default
            if data.delivered_at:
                shipment.delivered_at = data.delivered_at
            # Update related orders to SHIPPED
            for item in shipment.items:
                await self._order_repo.update_status(item.order_id, OrderStatus.SHIPPED)

        # When reverting from shipped, clear shipped_at and revert orders to delivered
        if is_reverting_from_shipped:
            shipment.shipped_at = None
            for item in shipment.items:
                await self._order_repo.update_status(item.order_id, OrderStatus.DELIVERED)

        await self._shipment_repo.update(shipment)

        # Refresh shipment to get updated relationships
        refreshed_shipment = await self._shipment_repo.find_by_id(shipment_id)
        return self._to_response(refreshed_shipment)

    async def upload_packing_photo(
        self, shipment_id: str, photo: UploadFile
    ) -> ShipmentResponse:
        """Upload packing photo for a shipment."""
        shipment = await self._shipment_repo.find_by_id(shipment_id)
        if not shipment:
            raise NotFoundError("Shipment", shipment_id)

        # Save photo
        path = await self._file_storage.save(photo, f"shipments/{shipment_id}/")
        shipment.packing_photo_path = path

        await self._shipment_repo.update(shipment)
        return self._to_response(shipment)

    async def get_packing_photo(self, shipment_id: str) -> tuple[bytes, str]:
        """Get packing photo for a shipment.

        Args:
            shipment_id: The shipment ID.

        Returns:
            Tuple of (file content bytes, content type).

        Raises:
            NotFoundError: If shipment not found or has no packing photo.
        """
        shipment = await self._shipment_repo.find_by_id(shipment_id)
        if not shipment:
            raise NotFoundError("Shipment", shipment_id)

        if not shipment.packing_photo_path:
            raise NotFoundError("Packing photo", shipment_id)

        content = await self._file_storage.get(shipment.packing_photo_path)
        if content is None:
            raise NotFoundError("Packing photo file", shipment_id)

        # Determine content type from file extension
        import mimetypes
        content_type, _ = mimetypes.guess_type(shipment.packing_photo_path)
        if not content_type or not content_type.startswith("image/"):
            content_type = "image/jpeg"  # Default to JPEG

        return content, content_type

    async def import_tracking_numbers(
        self, data: TrackingImportRequest
    ) -> list[ShipmentResponse]:
        """Import tracking numbers from CSV data."""
        results = []
        for item in data.items:
            shipment = await self._shipment_repo.find_by_id(item.shipment_id)
            if shipment:
                shipment.tracking_number = item.tracking_number
                if item.carrier:
                    shipment.carrier = item.carrier
                await self._shipment_repo.update(shipment)
                results.append(self._to_response(shipment))
        return results

    async def bulk_update_status(
        self, data: ShipmentBulkStatusUpdate
    ) -> ShipmentBulkStatusUpdateResponse:
        """配送ステータスを一括更新（バリデーション付き）"""
        updated_count = 0
        failed_count = 0
        failed_ids = []

        for shipment_id in data.shipment_ids:
            shipment = await self._shipment_repo.find_by_id(shipment_id)
            if not shipment:
                failed_ids.append(shipment_id)
                failed_count += 1
                continue

            current_status = ShipmentStatus(shipment.status)
            if not self._is_valid_transition(current_status, data.status):
                failed_ids.append(shipment_id)
                failed_count += 1
                continue

            shipment.status = data.status.value
            if data.tracking_number:
                shipment.tracking_number = data.tracking_number
            if data.carrier:
                shipment.carrier = data.carrier

            if data.status == ShipmentStatus.SHIPPED:
                shipment.shipped_at = datetime.now(timezone.utc)
                for item in shipment.items:
                    await self._order_repo.update_status(item.order_id, OrderStatus.SHIPPED)

            await self._shipment_repo.update(shipment)
            updated_count += 1

        return ShipmentBulkStatusUpdateResponse(
            updated_count=updated_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
        )

    async def import_tracking_from_file(
        self, file: UploadFile
    ) -> TrackingFileImportResult:
        """CSV/XLSXファイルから伝票番号を一括インポート.

        Args:
            file: アップロードされたCSVまたはXLSXファイル

        Returns:
            TrackingFileImportResult: インポート結果

        Raises:
            ValidationError: ファイル形式やサイズが不正な場合
        """
        # ファイル拡張子チェック
        filename = file.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("csv", "xlsx"):
            raise ValidationError(
                "対応していないファイル形式です。CSVまたはXLSXファイルをアップロードしてください"
            )

        # ファイルサイズチェック (10MB上限)
        max_size = 10 * 1024 * 1024
        if file.size is not None and file.size > max_size:
            raise ValidationError("ファイルサイズが上限（10MB）を超えています")

        # ファイル内容を読み込み
        content = await file.read()

        # 読み込んだ内容でもサイズチェック
        if len(content) > max_size:
            raise ValidationError("ファイルサイズが上限（10MB）を超えています")

        # ファイル解析
        if ext == "xlsx":
            rows = self._parse_xlsx(content)
        else:
            rows = self._parse_csv(content)

        # ヘッダーバリデーション
        if not rows:
            raise ValidationError("ファイルにデータがありません")

        header = [col.strip() for col in rows[0]]

        # 必須列チェック
        if "注文番号" not in header:
            raise ValidationError("「注文番号」列が見つかりません")
        if "伝票番号" not in header:
            raise ValidationError("「伝票番号」列が見つかりません")

        order_number_idx = header.index("注文番号")
        tracking_number_idx = header.index("伝票番号")

        # 運送会社名列（オプション）
        carrier_idx = None
        for carrier_name in ("運送会社名", "運送会社"):
            if carrier_name in header:
                carrier_idx = header.index(carrier_name)
                break

        # データ行の解析（空行スキップ、重複はlast-write-wins）
        # parsed_entries: order_number -> (tracking_number, carrier, row_number)
        parsed_entries: dict[str, tuple[str, str | None, int]] = {}
        errors: list[TrackingFileImportError] = []
        data_rows = rows[1:]
        valid_row_count = 0

        for i, row in enumerate(data_rows, start=1):
            # 空行スキップ
            if not row or all(cell.strip() == "" for cell in row):
                continue

            valid_row_count += 1

            # 列数が足りない場合
            order_number = row[order_number_idx].strip() if order_number_idx < len(row) else ""
            tracking_number = row[tracking_number_idx].strip() if tracking_number_idx < len(row) else ""

            # 注文番号チェック
            if not order_number:
                errors.append(TrackingFileImportError(
                    row=i,
                    order_number=None,
                    message="注文番号が空です",
                ))
                continue

            # 伝票番号チェック
            if not tracking_number:
                errors.append(TrackingFileImportError(
                    row=i,
                    order_number=order_number,
                    message="伝票番号が空です",
                ))
                continue

            carrier_value = None
            if carrier_idx is not None and carrier_idx < len(row):
                carrier_value = row[carrier_idx].strip() or None

            # last-write-wins
            parsed_entries[order_number] = (tracking_number, carrier_value, i)

        # 注文番号からshipmentを検索して更新
        success_count = 0
        email_sent_count = 0
        email_failed_count = 0
        updated_shipments: list[ShipmentResponse] = []
        results: list[TrackingFileImportRowResult] = []

        for order_number, (tracking_number, carrier_value, row_num) in parsed_entries.items():
            # 注文を検索
            order = await self._order_repo.find_by_order_number(order_number)
            if not order:
                errors.append(TrackingFileImportError(
                    row=row_num,
                    order_number=order_number,
                    message="注文番号が見つかりません",
                ))
                continue

            # shipmentを検索
            order_shipment_map = await self._shipment_repo.find_by_order_ids([order.id])
            shipment = order_shipment_map.get(order.id)
            if not shipment:
                errors.append(TrackingFileImportError(
                    row=row_num,
                    order_number=order_number,
                    message="配送レコードが存在しません",
                ))
                continue

            # 伝票番号・運送会社の更新
            shipment.tracking_number = tracking_number
            if carrier_value is not None:
                shipment.carrier = carrier_value

            # 配送ステータス更新
            shipment.status = ShipmentStatus.SHIPPED.value
            shipment.shipped_at = datetime.now(timezone.utc)

            # 注文ステータス更新
            order.status = OrderStatus.SHIPPED.value

            # メール送信（失敗してもDB更新はロールバックしない）
            email_sent = False
            if (
                self._email_service
                and order.customer_email
                and not shipment.shipping_email_sent
            ):
                email_sent = await self._email_service.send_shipping_notification(
                    to_email=order.customer_email,
                    customer_name=order.customer_name or "",
                    tracking_number=tracking_number,
                    carrier_name=carrier_value or "",
                    order_external_id=order.order_number,
                    order_items=[
                        {
                            "product_name": item.product_name,
                            "quantity": item.quantity,
                            "thumbnail_image_url": item.thumbnail_image_url,
                        }
                        for item in order.items
                    ],
                )
                if email_sent:
                    shipment.shipping_email_sent = True
                    email_sent_count += 1
                else:
                    email_failed_count += 1

            await self._shipment_repo.update(shipment)
            success_count += 1
            results.append(TrackingFileImportRowResult(
                order_number=order_number,
                tracking_number=tracking_number,
                email_sent=email_sent,
            ))

        return TrackingFileImportResult(
            total_count=valid_row_count,
            success_count=success_count,
            error_count=len(errors),
            email_sent_count=email_sent_count,
            email_failed_count=email_failed_count,
            errors=errors,
            results=results,
            updated_shipments=updated_shipments,
        )

    def _parse_csv(self, content: bytes) -> list[list[str]]:
        """CSVバイトデータを解析する.

        UTF-8 (BOM付き/なし) および Shift-JIS に対応。
        chardet でエンコーディングを自動検出する。
        """
        # BOM付きUTF-8の場合はBOMを除去
        if content.startswith(b"\xef\xbb\xbf"):
            text = content[3:].decode("utf-8")
        else:
            # chardetでエンコーディングを検出
            detected = chardet.detect(content)
            encoding = detected.get("encoding", "utf-8") or "utf-8"
            # chardetが "SHIFT_JIS" や "Windows-1252" 等を返す場合がある
            # 日本語のCSVではShift-JIS系のエンコーディングを正しく扱う
            if encoding.upper() in ("SHIFT_JIS", "SHIFT-JIS", "WINDOWS-31J", "CP932"):
                encoding = "shift_jis"
            try:
                text = content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                text = content.decode("utf-8", errors="replace")

        reader = csv.reader(io.StringIO(text))
        return list(reader)

    def _parse_xlsx(self, content: bytes) -> list[list[str]]:
        """XLSXバイトデータを解析する."""
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        rows: list[list[str]] = []
        for row in ws.iter_rows(values_only=True):
            rows.append([str(cell) if cell is not None else "" for cell in row])
        wb.close()
        return rows

    async def generate_import_template(self) -> tuple[bytes, str]:
        """インポート用サンプルCSVテンプレートを生成.

        Returns:
            Tuple of (CSV content as bytes with UTF-8 BOM, filename).
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["注文番号", "伝票番号", "運送会社名"])
        writer.writerow(["ORD-0001", "1234-5678-9012", "ヤマト運輸"])

        csv_content = output.getvalue()
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")

        filename = "tracking_import_template.csv"
        return csv_bytes, filename

    async def download_thumbnails(
        self,
        shipment_ids: list[str] | None = None,
        order_ids: list[str] | None = None,
    ) -> tuple[bytes, str]:
        """Download thumbnail images from shipments and/or orders and build a ZIP file.

        Args:
            shipment_ids: List of shipment IDs to collect thumbnails from.
            order_ids: List of order IDs to collect thumbnails from (for pending orders).

        Returns:
            Tuple of (ZIP file bytes, filename).

        Raises:
            HTTPException: 404 if no thumbnail images could be collected.
            ValidationError: If neither shipment_ids nor order_ids are provided.
        """
        shipment_ids = shipment_ids or []
        order_ids = order_ids or []

        if not shipment_ids and not order_ids:
            raise ValidationError("shipment_ids または order_ids が必要です")

        # Collect image tasks from shipments and orders
        image_tasks: list[dict] = []

        # Process shipments
        for shipment_id in shipment_ids:
            shipment = await self._shipment_repo.find_by_id(shipment_id)
            if shipment is None:
                logger.warning(f"Shipment not found: {shipment_id}")
                continue

            for shipment_item in shipment.items:
                order = shipment_item.order
                if not order:
                    continue
                self._collect_order_thumbnails(order, image_tasks)

        # Process orders (for pending orders without shipments)
        for order_id in order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if order is None:
                logger.warning(f"Order not found: {order_id}")
                continue
            self._collect_order_thumbnails(order, image_tasks)

        if not image_tasks:
            raise HTTPException(
                status_code=404,
                detail="ダウンロード対象のサムネイル画像がありません",
            )

        # Fetch images in parallel with semaphore
        semaphore = asyncio.Semaphore(10)

        async with httpx.AsyncClient() as client:

            async def fetch_image(task: dict) -> dict | None:
                async with semaphore:
                    try:
                        response = await client.get(
                            task["thumbnail_image_url"],
                            timeout=10.0,
                        )
                        if response.status_code != 200:
                            logger.warning(
                                f"Failed to fetch thumbnail: {task['thumbnail_image_url']} "
                                f"(status={response.status_code})"
                            )
                            return None

                        # Determine file extension
                        ext = self._get_extension_from_url(task["thumbnail_image_url"])
                        if not ext:
                            ext = self._get_extension_from_content_type(
                                response.headers.get("content-type", "")
                            )
                        if not ext:
                            ext = ".png"

                        return {
                            "order_number": task["order_number"],
                            "uid": task["uid"],
                            "content": response.content,
                            "extension": ext,
                        }
                    except Exception as e:
                        logger.warning(
                            f"Error fetching thumbnail {task['thumbnail_image_url']}: {e}"
                        )
                        return None

            results = await asyncio.gather(
                *[fetch_image(task) for task in image_tasks]
            )
            fetched_images = [r for r in results if r is not None]

        if not fetched_images:
            raise HTTPException(
                status_code=404,
                detail="ダウンロード対象のサムネイル画像がありません",
            )

        # Build ZIP
        builder = ZipBuilder()
        for img in fetched_images:
            file_path = f"{img['order_number']}_{img['uid']}{img['extension']}"
            builder.add_file(file_path, img["content"])

        zip_bytes = builder.build()

        # Generate filename
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"配送サムネイル_{timestamp}.zip"

        return zip_bytes, filename

    @staticmethod
    def _get_extension_from_url(url: str) -> str | None:
        """Extract file extension from URL path."""
        parsed = urlparse(url)
        path = parsed.path
        if "." in path:
            ext = path.rsplit(".", 1)[-1].lower()
            if ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "tiff"):
                return f".{ext}"
        return None

    @staticmethod
    def _get_extension_from_content_type(content_type: str) -> str | None:
        """Get file extension from Content-Type header."""
        if not content_type:
            return None
        mime_type = content_type.split(";")[0].strip().lower()

        mime_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/bmp": ".bmp",
            "image/svg+xml": ".svg",
            "image/tiff": ".tiff",
        }

        ext = mime_map.get(mime_type)
        if ext:
            return ext

        guessed_ext = mimetypes.guess_extension(mime_type)
        if guessed_ext and guessed_ext != ".bin":
            return guessed_ext

        return None

    def _is_valid_transition(
        self, current: ShipmentStatus, target: ShipmentStatus
    ) -> bool:
        """Check if status transition is valid.

        Supports bidirectional transitions for manual status switching.
        """
        # Allow same status (idempotent)
        if current == target:
            return True

        valid_transitions = {
            ShipmentStatus.PENDING: [ShipmentStatus.READY, ShipmentStatus.SHIPPED],
            ShipmentStatus.READY: [ShipmentStatus.PENDING, ShipmentStatus.SHIPPED],
            ShipmentStatus.SHIPPED: [ShipmentStatus.PENDING, ShipmentStatus.READY],
        }
        return target in valid_transitions.get(current, [])

    def _to_response(self, shipment: Shipment) -> ShipmentResponse:
        """Convert shipment model to response schema.

        顧客情報は最初の注文 (first_order) から取得します。
        OrderItem 単位で ShipmentItemResponse を展開します。
        """
        items = []
        first_order = shipment.first_order
        for item in shipment.items:
            order = item.order
            if order and order.items:
                # OrderItem ごとに1行を生成（複合ID: {shipment_item_id}_{order_item_id}）
                for oi in order.items:
                    items.append(ShipmentItemResponse(
                        id=f"{item.id}_{oi.id}",
                        order_id=item.order_id,
                        order_number=order.order_number,
                        product_name=oi.product_name,
                        quantity=oi.quantity,
                        thumbnail_image_url=oi.thumbnail_image_url,
                    ))
            else:
                # フォールバック: OrderItem がない場合は order.product_name で1行生成
                items.append(ShipmentItemResponse(
                    id=item.id,
                    order_id=item.order_id,
                    order_number=order.order_number if order else None,
                    product_name=order.product_name if order else None,
                    quantity=None,
                    thumbnail_image_url=None,
                ))

        # estimated_shipping_date: MAX of all related orders' estimated_shipping_date
        estimated_shipping_date = None
        for item in shipment.items:
            order = item.order
            if order and order.estimated_shipping_date:
                if estimated_shipping_date is None or order.estimated_shipping_date > estimated_shipping_date:
                    estimated_shipping_date = order.estimated_shipping_date

        return ShipmentResponse(
            id=shipment.id,
            status=ShipmentStatus(shipment.status),
            tracking_number=shipment.tracking_number,
            carrier=shipment.carrier,
            packing_photo_path=shipment.packing_photo_path,
            shipped_at=shipment.shipped_at,
            delivered_at=shipment.delivered_at,
            note=shipment.note,
            # Customer info from first order
            customer_name=first_order.customer_name if first_order else "",
            customer_postal_code=first_order.customer_postal_code if first_order else "",
            customer_address_prefecture=first_order.customer_address_prefecture if first_order else "",
            customer_address_city=first_order.customer_address_city if first_order else "",
            customer_address_building=first_order.customer_address_building if first_order else None,
            customer_phone=first_order.customer_phone if first_order else "",
            estimated_shipping_date=estimated_shipping_date,
            items=items,
            created_at=shipment.created_at,
            updated_at=shipment.updated_at,
        )

    async def export_csv(
        self,
        shipment_ids: list[str] | None = None,
        order_ids: list[str] | None = None,
    ) -> tuple[bytes, str]:
        """Export shipments and/or orders to CSV for delivery.

        Generates a CSV file with 18 columns for delivery company import.
        Each row represents one order item (not one shipment).

        Args:
            shipment_ids: List of shipment IDs to export.
            order_ids: List of order IDs to export (for pending orders without shipments).

        Returns:
            Tuple of (CSV content as bytes with BOM, filename)

        Raises:
            NotFoundError: If a shipment or order is not found.
            ValidationError: If neither shipment_ids nor order_ids are provided.
        """
        shipment_ids = shipment_ids or []
        order_ids = order_ids or []

        if not shipment_ids and not order_ids:
            raise ValidationError("shipment_ids または order_ids が必要です")

        # Collect CSV rows (one row per order item)
        rows = []

        # Process shipments
        for shipment_id in shipment_ids:
            shipment = await self._shipment_repo.find_by_id(shipment_id)
            if not shipment:
                raise NotFoundError("Shipment", shipment_id)

            # Iterate through all orders in this shipment
            for shipment_item in shipment.items:
                order = shipment_item.order
                if not order:
                    continue
                self._append_order_rows(order, rows)

        # Process orders (for pending orders without shipments)
        for order_id in order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if not order:
                raise NotFoundError("Order", order_id)
            self._append_order_rows(order, rows)

        # Generate CSV with UTF-8 BOM for Excel compatibility
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header (matching template exactly)
        header = [
            "注文番号",
            "お客様氏名",
            "商品名",
            "商品種類",
            "数量",
            "商品番号",
            "お届け先電話番号",
            "お届け先郵便番号",
            "お届け先住所1(都道府県)",
            "お届け先住所2(市区町村番地以下)",
            "お届け先住所3(建物名等)",
            "配送元電話番号",
            "配送元郵便番号",
            "配送元住所1(都道府県)",
            "配送元住所2(市区町村番地以下)",
            "配送元住所3(建物名等)",
            "配送元氏名",
            "商品名（処理用）",
        ]
        writer.writerow(header)

        # Write data rows
        for row in rows:
            writer.writerow(row)

        # Get CSV content with BOM
        csv_content = output.getvalue()
        csv_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")

        # Generate filename
        filename = f"shipments_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return csv_bytes, filename

    def _append_order_rows(self, order: Order, rows: list[list[str]]) -> None:
        """Append CSV rows for an order's items.

        Args:
            order: The order to process.
            rows: The list to append rows to.
        """
        order_source = order.order_source

        for item in order.items:
            row = [
                order.order_number,  # 1. 注文番号
                order.customer_name,  # 2. お客様氏名
                item.product_name,  # 3. 商品名
                # 4. 商品種類: {商品種類} - {サイズ} - {位置} - {色}（発注リストと統一）
                format_product_detail(
                    item.product_type, item.size, item.position, item.color
                ),
                str(item.quantity),  # 5. 数量
                item.uid or "",  # 6. 商品番号（アイテムUID）
                order.customer_phone,  # 7. お届け先電話番号
                order.customer_postal_code,  # 8. お届け先郵便番号
                order.customer_address_prefecture,  # 9. お届け先住所1（都道府県）
                order.customer_address_city,  # 10. お届け先住所2（市区町村番地以下）
                order.customer_address_building or "",  # 11. お届け先住所3（建物名等）
                order_source.phone if order_source else "",  # 12. 配送元電話番号
                order_source.postal_code if order_source else "",  # 13. 配送元郵便番号
                order_source.address_prefecture if order_source else "",  # 14. 配送元住所1
                order_source.address_city if order_source else "",  # 15. 配送元住所2
                order_source.address_building or "" if order_source else "",  # 16. 配送元住所3
                order_source.name if order_source else "",  # 17. 配送元氏名
                f"{order.order_number}_{item.uid or ''}",  # 18. 商品名（処理用）
            ]
            rows.append(row)

    def _collect_order_thumbnails(
        self, order: Order, image_tasks: list[dict]
    ) -> None:
        """Collect thumbnail image tasks from an order.

        Args:
            order: The order to collect thumbnails from.
            image_tasks: The list to append tasks to.
        """
        for order_item in order.items:
            if order_item.thumbnail_image_url is None:
                continue
            image_tasks.append({
                "order_number": order.order_number,
                "uid": order_item.uid or "",
                "thumbnail_image_url": order_item.thumbnail_image_url,
            })
