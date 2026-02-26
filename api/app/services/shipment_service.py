"""Shipment service."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import UploadFile

import csv
import io

from app.models.order import OrderStatus
from app.models.shipment import Shipment, ShipmentStatus
from app.repositories.order_repository import OrderRepository
from app.repositories.order_source_repository import OrderSourceRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.schemas.shipment import (
    ShipmentBulkStatusUpdate,
    ShipmentBulkStatusUpdateResponse,
    ShipmentCreate,
    ShipmentItemResponse,
    ShipmentListResponse,
    ShipmentResponse,
    ShipmentStatusUpdate,
    TrackingImportRequest,
)
from app.utils.exceptions import InvalidStatusTransitionError, NotFoundError, ValidationError
from app.utils.file_storage import FileStorage


class ShipmentService:
    """Service for shipment operations."""

    def __init__(
        self,
        shipment_repo: ShipmentRepository,
        order_repo: OrderRepository,
        file_storage: FileStorage,
        order_source_repo: OrderSourceRepository | None = None,
    ):
        self._shipment_repo = shipment_repo
        self._order_repo = order_repo
        self._file_storage = file_storage
        self._order_source_repo = order_source_repo

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
        """
        items = []
        first_order = shipment.first_order
        for item in shipment.items:
            order = item.order
            # order.items から product_name を取得（order.product_name は deprecated）
            if order and order.items:
                product_name = ", ".join(
                    oi.product_name for oi in order.items
                )
            elif order:
                product_name = order.product_name  # フォールバック
            else:
                product_name = None
            items.append(ShipmentItemResponse(
                id=item.id,
                order_id=item.order_id,
                order_number=order.order_number if order else None,
                product_name=product_name,
            ))

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
            items=items,
            created_at=shipment.created_at,
            updated_at=shipment.updated_at,
        )

    def _format_product_type(self, product_type: str) -> str:
        """Convert product_type to Japanese display name."""
        type_map = {
            "acrylic_keychain": "アクリルキーホルダー",
            "acrylic_stand": "アクリルスタンド",
            "sticker": "ステッカー",
            "tote_bag": "トートバッグ",
            "mug": "マグカップ",
            "tshirt": "Tシャツ",
        }
        return type_map.get(product_type, product_type)

    async def export_csv(self, shipment_ids: list[str]) -> tuple[bytes, str]:
        """Export shipments to CSV for delivery.

        Generates a CSV file with 18 columns for delivery company import.
        Each row represents one order item (not one shipment).

        Args:
            shipment_ids: List of shipment IDs to export.

        Returns:
            Tuple of (CSV content as bytes with BOM, filename)

        Raises:
            NotFoundError: If a shipment is not found.
            ValidationError: If OrderSourceRepository is not configured.
        """
        if not self._order_source_repo:
            raise ValidationError("OrderSourceRepository is not configured")

        # Collect CSV rows (one row per order item)
        rows = []

        for shipment_id in shipment_ids:
            shipment = await self._shipment_repo.find_by_id(shipment_id)
            if not shipment:
                raise NotFoundError("Shipment", shipment_id)

            # Iterate through all orders in this shipment
            for shipment_item in shipment.items:
                order = shipment_item.order
                if not order:
                    continue

                # Get order source for sender info (from relationship)
                order_source = order.order_source

                # Create one row per order item
                for item in order.items:
                    row = [
                        order.order_number,  # 1. 注文番号
                        order.customer_name,  # 2. お客様氏名
                        item.product_name,  # 3. 商品名
                        self._format_product_type(item.product_type),  # 4. 商品種類
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
