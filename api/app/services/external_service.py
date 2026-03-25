"""External service for external sales site APIs."""

from app.models.order import OrderStatus
from app.models.product_attributes import (
    AcrylicKeychainSize,
    AcrylicStandSize,
    StickerSize,
    get_attribute_spec,
    validate_product_attributes,
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
        spec = get_attribute_spec(product_type)
        return ProductOptionsResponse(
            product_type=product_type,
            size=spec.sizes,
            color=spec.colors,
            position=spec.positions,
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
        validate_product_attributes(
            product_type=data.product_type,
            size=data.size,
            color=data.color,
            position=data.position,
        )

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
        validate_product_attributes(
            product_type=data.product_type,
            size=data.size,
            color=data.color,
            position=data.position,
        )

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
        validate_product_attributes(
            product_type=data.product_type,
            size=data.size,
            color=data.color,
            position=data.position,
        )

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
        validate_product_attributes(
            product_type=data.product_type,
            size=data.size,
            color=data.color,
            position=data.position,
        )

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
        validate_product_attributes(
            product_type=data.product_type,
            size=data.size,
            color=data.color,
            position=data.position,
        )

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

        updated_order = await self._order_repo.update_status(
            order.id, OrderStatus.CANCELLED
        )

        return OrderCancelResponse(
            order_number=updated_order.order_number,
            status=OrderStatus.CANCELLED,
            cancelled_at=updated_order.updated_at,
        )
