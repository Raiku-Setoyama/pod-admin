"""Order service."""

from datetime import date

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
from app.models.product import ProductType
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import (
    ManufacturingDataInfo,
    OrderCreate,
    OrderItemCreate,
    OrderItemResponse,
    OrderListResponse,
    OrderResponse,
)
from app.utils.exceptions import (
    DuplicateError,
    OrderNotFoundError,
    ProductNotFoundError,
    ValidationError,
)


class OrderService:
    """Service for order operations."""

    def __init__(
        self,
        order_repo: OrderRepository,
        product_repo: ProductRepository,
    ):
        self._order_repo = order_repo
        self._product_repo = product_repo

    async def create(
        self,
        data: OrderCreate,
        source: str | None = None,
    ) -> OrderResponse:
        """Create a new order from external sales site."""
        # Check for duplicate order number
        existing = await self._order_repo.find_by_order_number(data.order_number)
        if existing:
            raise DuplicateError("Order", "order_number", data.order_number)

        # Validate items and find product_ids
        product_ids: dict[int, str] = {}  # index -> product_id
        for idx, item_data in enumerate(data.items):
            # Validate attributes based on product_type
            self._validate_item_attributes(item_data)

            # Find product by product_type and get product_id
            product = await self._product_repo.find_by_product_type(
                product_type=item_data.product_type,
            )
            if not product:
                raise ProductNotFoundError(item_data.product_type.value)
            product_ids[idx] = product.id

        # Calculate total price
        total_price = sum(item.price * item.quantity for item in data.items)

        # Create order
        order = Order(
            order_number=data.order_number,
            source=source,
            customer_name=data.customer.name,
            customer_postal_code=data.customer.postal_code,
            customer_address=data.customer.address,
            customer_phone=data.customer.phone,
            customer_email=data.customer.email,
            ordered_at=data.ordered_at,
            total_price=total_price,
        )

        # Create order items
        for idx, item_data in enumerate(data.items):
            order_item = OrderItem(
                uid=item_data.uid,
                product_id=product_ids[idx],
                product_name=item_data.product_name,
                product_type=item_data.product_type.value,
                price=item_data.price,
                quantity=item_data.quantity,
                size=item_data.size,
                position=item_data.position,
                color=item_data.color,
                design_image_url=item_data.design_image_url,
                thumbnail_image_url=item_data.thumbnail_image_url,
            )
            order.items.append(order_item)

        order = await self._order_repo.create(order)
        return self._to_response(order)

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
        return self._to_response(order)

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

        return OrderListResponse(
            items=[self._to_response(o) for o in orders],
            total=total,
            page=page,
            limit=limit,
        )

    async def update_status(self, order_id: str, status: OrderStatus) -> OrderResponse:
        """Update order status."""
        order = await self._order_repo.find_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        order.status = status.value
        order = await self._order_repo.update(order)
        return self._to_response(order)

    def _to_response(self, order: Order) -> OrderResponse:
        """Convert order model to response schema."""
        # Legacy manufacturing data (for backward compatibility)
        manufacturing_data = None
        if order.manufacturing_data_path:
            manufacturing_data = ManufacturingDataInfo(
                filename=order.manufacturing_data_filename,
                path=order.manufacturing_data_path,
                size=order.manufacturing_data_size,
                download_url=f"/api/v1/orders/{order.id}/manufacturing-data",
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
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in order.items
        ]

        return OrderResponse(
            id=order.id,
            order_number=order.order_number,
            status=OrderStatus(order.status),
            source=order.source,
            customer_name=order.customer_name,
            customer_postal_code=order.customer_postal_code,
            customer_address=order.customer_address,
            customer_phone=order.customer_phone,
            customer_email=order.customer_email,
            ordered_at=order.ordered_at,
            total_price=order.total_price,
            items=items,
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
