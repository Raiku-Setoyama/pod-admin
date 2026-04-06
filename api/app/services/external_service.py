"""External service for external sales site APIs."""

from app.models.order import OrderStatus
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
from app.services.product_attribute_service import ProductAttributeService
from app.utils.exceptions import ConflictError, NotFoundError, ValidationError


class ExternalService:
    """Service for external sales site operations."""

    def __init__(
        self,
        product_repo: ProductRepository,
        order_repo: OrderRepository,
        attribute_service: ProductAttributeService | None = None,
    ):
        self._product_repo = product_repo
        self._order_repo = order_repo
        self._attribute_service = attribute_service

    async def get_product_options(self, product_type: ProductType) -> ProductOptionsResponse:
        """Get available options for a product type."""
        if not self._attribute_service:
            raise ValidationError("Attribute service is not configured")

        spec = await self._attribute_service.get_attribute_spec(product_type.value)
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
        # Validate attributes via DB
        if self._attribute_service:
            await self._attribute_service.validate_attributes(
                product_type=data.product_type.value,
                size=data.size,
                color=data.color,
                position=data.position,
            )

        # Look up price from product master
        product = await self._product_repo.find_duplicate(
            product_type=data.product_type.value,
            size=data.size,
            position=data.position,
            color=data.color,
        )
        if not product:
            raise NotFoundError("Product", f"{data.product_type.value}/{data.size}")

        unit_price = product.cost
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
