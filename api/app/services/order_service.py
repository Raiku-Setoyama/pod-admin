"""Order service."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import mimetypes
from datetime import date, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException

from app.models.order import (
    AcrylicKeychainSize,
    AcrylicStandSize,
    Order,
    OrderItem,
    OrderStatus,
    StickerColor,
    StickerSize,
    ToteBagColor,
    ToteBagPosition,
    ToteBagSize,
    TshirtColor,
    TshirtPosition,
    TshirtSize,
)
from app.models.product import Product, ProductType
from app.models.shipment import Shipment, ShipmentStatus
from app.repositories.company_holiday_repository import CompanyHolidayRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.order_source_repository import OrderSourceRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.schemas.order import (
    ManufacturingDataInfo,
    OrderBulkStatusUpdateResponse,
    OrderCreate,
    OrderItemCreate,
    OrderItemResponse,
    OrderListResponse,
    OrderResponse,
    OrderShipmentInfo,
)
from app.utils.business_day_calculator import add_business_days
from app.utils.exceptions import (
    DuplicateError,
    InvalidStatusTransitionError,
    NotFoundError,
    OrderNotFoundError,
    ProductNotFoundError,
    ValidationError,
)
from app.utils.zip_builder import ZipBuilder

logger = logging.getLogger(__name__)


class OrderService:
    """Service for order operations."""

    def __init__(
        self,
        order_repo: OrderRepository,
        product_repo: ProductRepository,
        shipment_repo: ShipmentRepository,
        order_source_repo: OrderSourceRepository | None = None,
        company_holiday_repo: CompanyHolidayRepository | None = None,
    ):
        self._order_repo = order_repo
        self._product_repo = product_repo
        self._shipment_repo = shipment_repo
        self._order_source_repo = order_source_repo
        self._company_holiday_repo = company_holiday_repo

    async def create(
        self,
        data: OrderCreate,
        order_source_id: str | None = None,
    ) -> OrderResponse:
        """Create a new order from external sales site."""
        # Check for duplicate order number
        existing = await self._order_repo.find_by_order_number(data.order_number)
        if existing:
            raise DuplicateError("Order", "order_number", data.order_number)

        # Validate items and find products
        products: dict[int, Product] = {}  # index -> Product
        for idx, item_data in enumerate(data.items):
            # Validate attributes based on product_type
            self._validate_item_attributes(item_data)

            # Find product by product_type and get product
            product = await self._product_repo.find_by_product_type(
                product_type=item_data.product_type,
            )
            if not product:
                raise ProductNotFoundError(item_data.product_type.value)
            products[idx] = product

        # Fetch company holidays for business day calculation
        company_holidays: set[date] | None = None
        if self._company_holiday_repo:
            company_holidays = await self._company_holiday_repo.find_all_dates()

        # Calculate total price
        total_price = sum(item.price * item.quantity for item in data.items)

        # Create order with split address fields
        customer = data.customer
        order = Order(
            order_number=data.order_number,
            order_source_id=order_source_id,
            customer_name=customer.name,
            customer_postal_code=customer.postal_code,
            customer_address_prefecture=customer.address_prefecture,
            customer_address_city=customer.address_city,
            customer_address_building=customer.address_building,
            customer_phone=customer.phone,
            customer_email=customer.email,
            ordered_at=data.ordered_at,
            total_price=total_price,
        )

        # Create order items with expected_delivery_date
        # JSTに正規化してからdate()を取得（UTCのままだと深夜帯で日付がずれる）
        jst = ZoneInfo("Asia/Tokyo")
        ordered_at_jst = data.ordered_at.astimezone(jst) if data.ordered_at.tzinfo else data.ordered_at
        ordered_date = ordered_at_jst.date()
        for idx, item_data in enumerate(data.items):
            product = products[idx]

            # Calculate expected_delivery_date using business day calculation
            expected_delivery = add_business_days(
                ordered_date,
                product.lead_time_days,
                company_holidays,
            )

            order_item = OrderItem(
                uid=item_data.uid,
                product_id=product.id,
                product_name=item_data.product_name,
                product_type=item_data.product_type.value,
                price=item_data.price,
                quantity=item_data.quantity,
                size=item_data.size,
                position=item_data.position,
                color=item_data.color,
                design_image_url=item_data.design_image_url,
                thumbnail_image_url=item_data.thumbnail_image_url,
                expected_delivery_date=expected_delivery,
            )
            order.items.append(order_item)

        order = await self._order_repo.create(order)
        return await self._to_response(order)

    def _validate_item_attributes(self, item_data: OrderItemCreate) -> None:
        """Validate item attributes based on product_type."""
        if item_data.product_type == ProductType.TSHIRT:
            self._validate_tshirt_attributes(item_data)
        elif item_data.product_type == ProductType.ACRYLIC_KEYCHAIN:
            self._validate_acrylic_keychain_attributes(item_data)
        elif item_data.product_type == ProductType.ACRYLIC_STAND:
            self._validate_acrylic_stand_attributes(item_data)
        elif item_data.product_type == ProductType.STICKER:
            self._validate_sticker_attributes(item_data)
        elif item_data.product_type == ProductType.TOTE_BAG:
            self._validate_tote_bag_attributes(item_data)

    async def get_by_id(self, order_id: str) -> OrderResponse:
        """Get an order by ID."""
        order = await self._order_repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        return await self._to_response(order)

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        status: OrderStatus | None = None,
        product_type: ProductType | None = None,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        search: str | None = None,
    ) -> OrderListResponse:
        """List orders with pagination and filters."""
        orders, total = await self._order_repo.find_all(
            page=page,
            limit=limit,
            status=status,
            product_type=product_type,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            search=search,
        )

        # Fetch shipment info for all orders in batch (N+1 avoidance)
        order_ids = [o.id for o in orders]
        shipment_map = await self._shipment_repo.find_by_order_ids(order_ids)

        # Convert to responses with pre-fetched shipments
        items = [
            await self._to_response(o, shipment_map.get(o.id))
            for o in orders
        ]

        return OrderListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    async def update_status(self, order_id: str, status: OrderStatus) -> OrderResponse:
        """Update order status.

        Implements manual status switching with the following rules:
        - shipped への直接遷移は拒否（Shipment経由でのみshippedになる）
        - shipped ステータスからの遷移は拒否（Shipment経由で戻す必要がある）
        - delivered -> ordered/manufacturing: 関連Shipmentがshippedなら拒否、そうでなければShipment削除
        - ordered/manufacturing -> delivered: Shipment自動作成
        """
        order = await self._order_repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        current_status = OrderStatus(order.status)

        # shipped への直接遷移は拒否
        if status == OrderStatus.SHIPPED:
            raise InvalidStatusTransitionError(current_status.value, status.value)

        # shipped ステータスからの遷移は拒否
        if current_status == OrderStatus.SHIPPED:
            raise InvalidStatusTransitionError(current_status.value, status.value)

        # delivered -> ordered/manufacturing の遷移時の処理
        if current_status == OrderStatus.DELIVERED and status in (
            OrderStatus.ORDERED,
            OrderStatus.MANUFACTURING,
        ):
            # 関連Shipmentを確認
            shipment_map = await self._shipment_repo.find_by_order_ids([order_id])
            shipment = shipment_map.get(order_id)

            if shipment:
                # Shipmentがshippedなら拒否
                if shipment.status == ShipmentStatus.SHIPPED.value:
                    raise ValidationError(
                        "Cannot revert order status: related shipment is already shipped. "
                        "Please revert the shipment status first."
                    )
                # そうでなければShipment削除
                await self._shipment_repo.delete_by_order_id(order_id)

        order.status = status.value
        order = await self._order_repo.update(order)

        # delivered になったら Shipment を自動作成
        if status == OrderStatus.DELIVERED:
            await self._create_shipment_for_order(order)

        return await self._to_response(order)

    async def _create_shipment_for_order(self, order: Order) -> None:
        """Create a shipment for the delivered order.

        This method is idempotent - if a shipment already exists for the order,
        it will not create a duplicate. The shipment creation happens within
        the same transaction as the order status update, ensuring atomicity.

        顧客情報は Shipment から Order のリレーションを経由して取得します。

        Args:
            order: The order that was just marked as delivered.

        Raises:
            Exception: If shipment creation fails, the entire transaction
                       (including order status update) will be rolled back.
        """
        # Check if shipment already exists (prevent duplicates)
        if await self._shipment_repo.exists_for_order(order.id):
            return

        await self._shipment_repo.create(order_ids=[order.id])

    async def _to_response(
        self, order: Order, shipment: Shipment | None = None
    ) -> OrderResponse:
        """Convert order model to response schema.

        Args:
            order: Order model to convert.
            shipment: Optional shipment info. If None, will be fetched from DB.
                      Pass explicitly for batch operations to avoid N+1.
        """
        # Legacy manufacturing data (for backward compatibility)
        manufacturing_data = None
        if order.manufacturing_data_path:
            manufacturing_data = ManufacturingDataInfo(
                filename=order.manufacturing_data_filename,
                path=order.manufacturing_data_path,
                size=order.manufacturing_data_size,
                download_url=f"/orders/{order.id}/manufacturing-data",
            )

        # Convert order items
        items = [
            OrderItemResponse(
                id=item.id,
                uid=item.uid or "",
                product_name=item.product_name,
                product_type=item.product_type,
                price=item.price,
                quantity=item.quantity,
                size=item.size,
                position=item.position,
                color=item.color,
                design_image_url=item.design_image_url,
                thumbnail_image_url=item.thumbnail_image_url,
                expected_delivery_date=item.expected_delivery_date,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in order.items
        ]

        # Fetch shipment if not provided (for single order operations)
        if shipment is None:
            shipment_map = await self._shipment_repo.find_by_order_ids([order.id])
            shipment = shipment_map.get(order.id)

        # Convert shipment info
        shipment_info = None
        if shipment:
            shipment_info = OrderShipmentInfo(
                id=shipment.id,
                status=shipment.status,
                tracking_number=shipment.tracking_number,
                carrier=shipment.carrier,
            )

        return OrderResponse(
            id=order.id,
            order_number=order.order_number,
            status=OrderStatus(order.status),
            source=order.order_source.code if order.order_source else None,
            order_source_id=order.order_source_id,
            customer_name=order.customer_name,
            customer_postal_code=order.customer_postal_code,
            customer_address_prefecture=order.customer_address_prefecture,
            customer_address_city=order.customer_address_city,
            customer_address_building=order.customer_address_building,
            customer_phone=order.customer_phone,
            customer_email=order.customer_email,
            ordered_at=order.ordered_at,
            total_price=order.total_price,
            items=items,
            shipment=shipment_info,
            # Legacy fields (for backward compatibility)
            product_id=order.product_id,
            product_name=order.product_name,
            price=order.price,
            quantity=order.quantity,
            manufacturing_data=manufacturing_data,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )

    def _validate_tshirt_attributes(self, item_data) -> None:
        """Tシャツ受注時の属性バリデーション."""
        # サイズ必須・値検証
        if not item_data.size:
            raise ValidationError(
                f"size is required for T-shirt (uid: {item_data.uid})"
            )
        try:
            TshirtSize(item_data.size)
        except ValueError:
            valid_sizes = [s.value for s in TshirtSize]
            raise ValidationError(
                f"Invalid size '{item_data.size}'. Valid: {valid_sizes} (uid: {item_data.uid})"
            )

        # 色必須・値検証
        if not item_data.color:
            raise ValidationError(
                f"color is required for T-shirt (uid: {item_data.uid})"
            )
        try:
            TshirtColor(item_data.color)
        except ValueError:
            valid_colors = [c.value for c in TshirtColor]
            raise ValidationError(
                f"Invalid color '{item_data.color}'. Valid: {valid_colors} (uid: {item_data.uid})"
            )

        # 位置必須・値検証
        if not item_data.position:
            raise ValidationError(
                f"position is required for T-shirt (uid: {item_data.uid})"
            )
        try:
            TshirtPosition(item_data.position)
        except ValueError:
            valid_positions = [p.value for p in TshirtPosition]
            raise ValidationError(
                f"Invalid position '{item_data.position}'. Valid: {valid_positions} (uid: {item_data.uid})"
            )

    def _validate_acrylic_keychain_attributes(self, item_data) -> None:
        """アクリルキーホルダー受注時の属性バリデーション."""
        # サイズ必須・値検証
        if not item_data.size:
            raise ValidationError(
                f"size is required for acrylic keychain (uid: {item_data.uid})"
            )
        try:
            AcrylicKeychainSize(item_data.size)
        except ValueError:
            valid_sizes = [s.value for s in AcrylicKeychainSize]
            raise ValidationError(
                f"Invalid size '{item_data.size}'. Valid: {valid_sizes} (uid: {item_data.uid})"
            )

    def _validate_acrylic_stand_attributes(self, item_data) -> None:
        """アクリルスタンド受注時の属性バリデーション."""
        # サイズ必須・値検証
        if not item_data.size:
            raise ValidationError(
                f"size is required for acrylic stand (uid: {item_data.uid})"
            )
        try:
            AcrylicStandSize(item_data.size)
        except ValueError:
            valid_sizes = [s.value for s in AcrylicStandSize]
            raise ValidationError(
                f"Invalid size '{item_data.size}'. Valid: {valid_sizes} (uid: {item_data.uid})"
            )

    def _validate_sticker_attributes(self, item_data) -> None:
        """ステッカー受注時の属性バリデーション."""
        # サイズ必須・値検証
        if not item_data.size:
            raise ValidationError(
                f"size is required for sticker (uid: {item_data.uid})"
            )
        try:
            StickerSize(item_data.size)
        except ValueError:
            valid_sizes = [s.value for s in StickerSize]
            raise ValidationError(
                f"Invalid size '{item_data.size}'. Valid: {valid_sizes} (uid: {item_data.uid})"
            )

        # 色必須・値検証
        if not item_data.color:
            raise ValidationError(
                f"color is required for sticker (uid: {item_data.uid})"
            )
        try:
            StickerColor(item_data.color)
        except ValueError:
            valid_colors = [c.value for c in StickerColor]
            raise ValidationError(
                f"Invalid color '{item_data.color}'. Valid: {valid_colors} (uid: {item_data.uid})"
            )

    def _validate_tote_bag_attributes(self, item_data) -> None:
        """トートバッグ受注時の属性バリデーション."""
        # サイズ必須・値検証
        if not item_data.size:
            raise ValidationError(
                f"size is required for tote bag (uid: {item_data.uid})"
            )
        try:
            ToteBagSize(item_data.size)
        except ValueError:
            valid_sizes = [s.value for s in ToteBagSize]
            raise ValidationError(
                f"Invalid size '{item_data.size}'. Valid: {valid_sizes} (uid: {item_data.uid})"
            )

        # 色必須・値検証
        if not item_data.color:
            raise ValidationError(
                f"color is required for tote bag (uid: {item_data.uid})"
            )
        try:
            ToteBagColor(item_data.color)
        except ValueError:
            valid_colors = [c.value for c in ToteBagColor]
            raise ValidationError(
                f"Invalid color '{item_data.color}'. Valid: {valid_colors} (uid: {item_data.uid})"
            )

        # 位置必須・値検証
        if not item_data.position:
            raise ValidationError(
                f"position is required for tote bag (uid: {item_data.uid})"
            )
        try:
            ToteBagPosition(item_data.position)
        except ValueError:
            valid_positions = [p.value for p in ToteBagPosition]
            raise ValidationError(
                f"Invalid position '{item_data.position}'. Valid: {valid_positions} (uid: {item_data.uid})"
            )

    async def bulk_update_status(
        self,
        order_ids: list[str],
        status: OrderStatus,
    ) -> OrderBulkStatusUpdateResponse:
        """Bulk update order status.

        Args:
            order_ids: List of order IDs to update.
            status: Target status to update to.

        Returns:
            OrderBulkStatusUpdateResponse with updated_count, failed_count, failed_ids.

        Raises:
            ValidationError: If order_ids is empty or status is shipped.
        """
        # Validate empty order_ids
        if not order_ids:
            raise ValidationError("order_ids cannot be empty")

        # Reject direct transition to shipped
        if status == OrderStatus.SHIPPED:
            raise ValidationError(
                "Cannot bulk update to shipped status. Use shipment workflow instead."
            )

        updated_count = 0
        failed_count = 0
        failed_ids: list[str] = []

        # Pre-fetch all shipments for efficiency
        shipment_map = await self._shipment_repo.find_by_order_ids(order_ids)

        for order_id in order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if not order:
                failed_ids.append(order_id)
                failed_count += 1
                continue

            current_status = OrderStatus(order.status)

            # Reject transition from shipped status
            if current_status == OrderStatus.SHIPPED:
                failed_ids.append(order_id)
                failed_count += 1
                continue

            # Handle delivered -> ordered/manufacturing transition
            if current_status == OrderStatus.DELIVERED and status in (
                OrderStatus.ORDERED,
                OrderStatus.MANUFACTURING,
            ):
                shipment = shipment_map.get(order_id)
                if shipment:
                    # If shipment is shipped, reject the transition
                    if shipment.status == ShipmentStatus.SHIPPED.value:
                        failed_ids.append(order_id)
                        failed_count += 1
                        continue
                    # Delete the shipment
                    await self._shipment_repo.delete_by_order_id(order_id)

            # Update order status
            order.status = status.value
            await self._order_repo.update(order)

            # Create shipment if transitioning to delivered
            if status == OrderStatus.DELIVERED:
                await self._create_shipment_for_order(order)

            updated_count += 1

        return OrderBulkStatusUpdateResponse(
            updated_count=updated_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
        )

    async def export_csv(self, order_ids: list[str]) -> tuple[bytes, str]:
        """Export orders to CSV for delivery.

        Generates a CSV file with 18 columns for delivery company import.
        Each row represents one order item (not one order).

        This is similar to ShipmentService.export_csv but works with order_ids
        instead of shipment_ids (for pending orders that don't have shipments yet).

        Args:
            order_ids: List of order IDs to export.

        Returns:
            Tuple of (CSV content as bytes with BOM, filename)

        Raises:
            NotFoundError: If an order is not found.
            ValidationError: If OrderSourceRepository is not configured.
        """
        if not self._order_source_repo:
            raise ValidationError("OrderSourceRepository is not configured")

        # Collect CSV rows (one row per order item)
        rows = []

        for order_id in order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if not order:
                raise NotFoundError("Order", order_id)

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
        filename = f"orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return csv_bytes, filename

    async def download_thumbnails(
        self, order_ids: list[str]
    ) -> tuple[bytes, str]:
        """Download thumbnail images from orders and build a ZIP file.

        This is similar to ShipmentService.download_thumbnails but works with order_ids
        instead of shipment_ids (for pending orders that don't have shipments yet).

        Args:
            order_ids: List of order IDs to collect thumbnails from.

        Returns:
            Tuple of (ZIP file bytes, filename).

        Raises:
            HTTPException: 404 if no thumbnail images could be collected.
        """
        # Collect image tasks from orders
        image_tasks: list[dict] = []

        for order_id in order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if order is None:
                logger.warning(f"Order not found: {order_id}")
                continue

            for order_item in order.items:
                if order_item.thumbnail_image_url is None:
                    continue
                image_tasks.append({
                    "order_number": order.order_number,
                    "uid": order_item.uid or "",
                    "thumbnail_image_url": order_item.thumbnail_image_url,
                })

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
        filename = f"注文サムネイル_{timestamp}.zip"

        return zip_bytes, filename

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
