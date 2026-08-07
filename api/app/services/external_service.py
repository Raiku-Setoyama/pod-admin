"""External service for external sales site APIs."""

from app.models.order import (
    AcrylicKeychainColor,
    AcrylicKeychainSize,
    AcrylicStandColor,
    AcrylicStandSize,
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
from app.schemas.external import (
    OrderCancelResponse,
    OrderStatusResponse,
    PriceCalculationRequest,
    PriceCalculationResponse,
    ProductOptionsResponse,
)
from app.utils.exceptions import ConflictError, NotFoundError, ValidationError

# 価格マッピング
ACRYLIC_KEYCHAIN_PRICES = {
    AcrylicKeychainSize.MM50X50.value: 285,
    AcrylicKeychainSize.MM70X70.value: 350,
    AcrylicKeychainSize.MM100X100.value: 475,
}

ACRYLIC_STAND_PRICES = {
    AcrylicStandSize.MM50X50.value: 310,
    AcrylicStandSize.MM70X70.value: 345,
    AcrylicStandSize.MM100X100.value: 735,
}

STICKER_PRICES = {
    StickerSize.MM50X50.value: 50,
    StickerSize.MM70X70.value: 59,
    StickerSize.MM100X100.value: 79,
}


class ExternalService:
    """Service for external sales site operations."""

    def __init__(self, product_repo: ProductRepository, order_repo: OrderRepository):
        self._product_repo = product_repo
        self._order_repo = order_repo

    def get_product_options(self, product_type: ProductType) -> ProductOptionsResponse:
        """Get available options for a product type."""
        if product_type == ProductType.TSHIRT:
            return ProductOptionsResponse(
                product_type=product_type,
                size=[s.value for s in TshirtSize],
                color=[c.value for c in TshirtColor],
                position=[p.value for p in TshirtPosition],
            )

        if product_type == ProductType.ACRYLIC_KEYCHAIN:
            return ProductOptionsResponse(
                product_type=product_type,
                size=[s.value for s in AcrylicKeychainSize],
                color=[c.value for c in AcrylicKeychainColor],
                position=[],
            )

        if product_type == ProductType.ACRYLIC_STAND:
            return ProductOptionsResponse(
                product_type=product_type,
                size=[s.value for s in AcrylicStandSize],
                color=[c.value for c in AcrylicStandColor],
                position=[],
            )

        if product_type == ProductType.STICKER:
            return ProductOptionsResponse(
                product_type=product_type,
                size=[s.value for s in StickerSize],
                color=[c.value for c in StickerColor],
                position=[],
            )

        if product_type == ProductType.TOTE_BAG:
            return ProductOptionsResponse(
                product_type=product_type,
                size=[s.value for s in ToteBagSize],
                color=[c.value for c in ToteBagColor],
                position=[p.value for p in ToteBagPosition],
            )

        raise ValidationError(
            f"Product type '{product_type.value}' is not yet supported"
        )

    async def calculate_price(
        self, data: PriceCalculationRequest
    ) -> PriceCalculationResponse:
        """Calculate price for a product with given attributes."""
        if data.product_type == ProductType.TSHIRT:
            return await self._calculate_tshirt_price(data)

        if data.product_type == ProductType.ACRYLIC_KEYCHAIN:
            return self._calculate_acrylic_keychain_price(data)

        if data.product_type == ProductType.ACRYLIC_STAND:
            return self._calculate_acrylic_stand_price(data)

        if data.product_type == ProductType.STICKER:
            return self._calculate_sticker_price(data)

        if data.product_type == ProductType.TOTE_BAG:
            return self._calculate_tote_bag_price(data)

        # Other product types not yet supported
        raise ValidationError(
            f"Product type '{data.product_type.value}' is not yet supported"
        )

    async def _calculate_tshirt_price(
        self, data: PriceCalculationRequest
    ) -> PriceCalculationResponse:
        """Calculate price for T-shirt."""
        # Validate size
        try:
            TshirtSize(data.size)
        except ValueError:
            valid_sizes = [s.value for s in TshirtSize]
            raise ValidationError(
                f"Invalid size '{data.size}'. Valid sizes: {valid_sizes}"
            ) from None

        # Validate color (required for tshirt)
        if not data.color:
            raise ValidationError("color is required for T-shirt")
        try:
            TshirtColor(data.color)
        except ValueError:
            valid_colors = [c.value for c in TshirtColor]
            raise ValidationError(
                f"Invalid color '{data.color}'. Valid colors: {valid_colors}"
            ) from None

        # Validate position (required for tshirt)
        if not data.position:
            raise ValidationError("position is required for T-shirt")
        try:
            TshirtPosition(data.position)
        except ValueError:
            valid_positions = [p.value for p in TshirtPosition]
            raise ValidationError(
                f"Invalid position '{data.position}'. Valid positions: {valid_positions}"
            ) from None

        # Calculate price
        unit_price = 870

        total_price = unit_price * data.quantity

        return PriceCalculationResponse(
            product_type=data.product_type,
            size=data.size,
            color=data.color,
            position=data.position,
            quantity=data.quantity,
            unit_price=unit_price,
            total_price=total_price,
        )

    def _calculate_acrylic_keychain_price(
        self, data: PriceCalculationRequest
    ) -> PriceCalculationResponse:
        """Calculate price for acrylic keychain."""
        # Validate size
        try:
            AcrylicKeychainSize(data.size)
        except ValueError:
            valid_sizes = [s.value for s in AcrylicKeychainSize]
            raise ValidationError(
                f"Invalid size '{data.size}'. Valid sizes: {valid_sizes}"
            ) from None

        # Calculate price based on size
        unit_price = ACRYLIC_KEYCHAIN_PRICES.get(data.size, 285)
        total_price = unit_price * data.quantity

        return PriceCalculationResponse(
            product_type=data.product_type,
            size=data.size,
            color=data.color,  # optional, pass through
            position=None,  # position not used for acrylic keychain
            quantity=data.quantity,
            unit_price=unit_price,
            total_price=total_price,
        )

    def _calculate_acrylic_stand_price(
        self, data: PriceCalculationRequest
    ) -> PriceCalculationResponse:
        """Calculate price for acrylic stand."""
        # Validate size
        try:
            AcrylicStandSize(data.size)
        except ValueError:
            valid_sizes = [s.value for s in AcrylicStandSize]
            raise ValidationError(
                f"Invalid size '{data.size}'. Valid sizes: {valid_sizes}"
            ) from None

        # Calculate price based on size
        unit_price = ACRYLIC_STAND_PRICES.get(data.size, 310)
        total_price = unit_price * data.quantity

        return PriceCalculationResponse(
            product_type=data.product_type,
            size=data.size,
            color=data.color,  # optional, pass through
            position=None,  # position not used for acrylic stand
            quantity=data.quantity,
            unit_price=unit_price,
            total_price=total_price,
        )

    def _calculate_sticker_price(
        self, data: PriceCalculationRequest
    ) -> PriceCalculationResponse:
        """Calculate price for sticker."""
        # Validate size
        try:
            StickerSize(data.size)
        except ValueError:
            valid_sizes = [s.value for s in StickerSize]
            raise ValidationError(
                f"Invalid size '{data.size}'. Valid sizes: {valid_sizes}"
            ) from None

        # Validate color (required for sticker)
        if not data.color:
            raise ValidationError("color is required for sticker")
        try:
            StickerColor(data.color)
        except ValueError:
            valid_colors = [c.value for c in StickerColor]
            raise ValidationError(
                f"Invalid color '{data.color}'. Valid colors: {valid_colors}"
            ) from None

        # Calculate price based on size
        unit_price = STICKER_PRICES.get(data.size, 79)
        total_price = unit_price * data.quantity

        return PriceCalculationResponse(
            product_type=data.product_type,
            size=data.size,
            color=data.color,
            position=None,  # position not used for sticker
            quantity=data.quantity,
            unit_price=unit_price,
            total_price=total_price,
        )

    def _calculate_tote_bag_price(
        self, data: PriceCalculationRequest
    ) -> PriceCalculationResponse:
        """Calculate price for tote bag."""
        # Validate size
        try:
            ToteBagSize(data.size)
        except ValueError:
            valid_sizes = [s.value for s in ToteBagSize]
            raise ValidationError(
                f"Invalid size '{data.size}'. Valid sizes: {valid_sizes}"
            ) from None

        # Validate color (required for tote bag)
        if not data.color:
            raise ValidationError("color is required for tote bag")
        try:
            ToteBagColor(data.color)
        except ValueError:
            valid_colors = [c.value for c in ToteBagColor]
            raise ValidationError(
                f"Invalid color '{data.color}'. Valid colors: {valid_colors}"
            ) from None

        # Validate position (required for tote bag)
        if not data.position:
            raise ValidationError("position is required for tote bag")
        try:
            ToteBagPosition(data.position)
        except ValueError:
            valid_positions = [p.value for p in ToteBagPosition]
            raise ValidationError(
                f"Invalid position '{data.position}'. Valid positions: {valid_positions}"
            ) from None

        # Calculate price (fixed price for tote bag)
        unit_price = 780
        total_price = unit_price * data.quantity

        return PriceCalculationResponse(
            product_type=data.product_type,
            size=data.size,
            color=data.color,
            position=data.position,
            quantity=data.quantity,
            unit_price=unit_price,
            total_price=total_price,
        )

    async def get_order_status_by_order_number(
        self, order_number: str
    ) -> OrderStatusResponse:
        """Get order status by order number."""
        order = await self._order_repo.find_by_order_number(order_number)
        if not order:
            raise NotFoundError(f"Order with order_number '{order_number}' not found")

        return OrderStatusResponse(
            order_number=order.order_number,
            status=OrderStatus(order.status),
            ordered_at=order.ordered_at,
            updated_at=order.updated_at,
        )

    async def cancel_order(self, order_number: str) -> OrderCancelResponse:
        """Cancel an order by order number.

        Only orders in 'ordered' status can be cancelled.

        Args:
            order_number: The order number to cancel.

        Returns:
            OrderCancelResponse with cancellation details.

        Raises:
            NotFoundError: If the order does not exist.
            ConflictError: If the order is not in 'ordered' status.
        """
        order = await self._order_repo.find_by_order_number(order_number)
        if not order:
            raise NotFoundError("order", order_number)

        if order.status != OrderStatus.ORDERED.value:
            raise ConflictError("発注中の注文のみ取り消せます")

        # 明細も「キャンセル済み」にする（メーカー画面/ポータルは明細ステータスを表示）。
        # 注文と同じ flush で永続化されるよう update_status の前に反映する。
        self._order_repo.apply_cancellation_to_items(order, cancelled=True)
        updated_order = await self._order_repo.update_status(
            order.id, OrderStatus.CANCELLED
        )

        return OrderCancelResponse(
            order_number=updated_order.order_number,
            status=OrderStatus.CANCELLED,
            cancelled_at=updated_order.updated_at,
        )
