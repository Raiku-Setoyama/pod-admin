"""External service for external sales site APIs."""

from app.models.order import TshirtColor, TshirtPosition, TshirtSize
from app.models.product import ProductType
from app.repositories.product_repository import ProductRepository
from app.schemas.external import (
    PriceCalculationRequest,
    PriceCalculationResponse,
    ProductOptionsResponse,
)
from app.utils.exceptions import ProductNotFoundError, ValidationError


class ExternalService:
    """Service for external sales site operations."""

    def __init__(self, product_repo: ProductRepository):
        self._product_repo = product_repo

    def get_product_options(self, product_type: ProductType) -> ProductOptionsResponse:
        """Get available options for a product type."""
        if product_type == ProductType.TSHIRT:
            return ProductOptionsResponse(
                product_type=product_type,
                size=[s.value for s in TshirtSize],
                color=[c.value for c in TshirtColor],
                position=[p.value for p in TshirtPosition],
            )

        # Other product types not yet supported
        raise ValidationError(
            f"Product type '{product_type.value}' is not yet supported"
        )

    async def calculate_price(
        self, data: PriceCalculationRequest
    ) -> PriceCalculationResponse:
        """Calculate price for a product with given attributes."""
        if data.product_type == ProductType.TSHIRT:
            return await self._calculate_tshirt_price(data)

        # Other product types not yet supported
        raise ValidationError(
            f"Product type '{data.product_type.value}' is not yet supported"
        )

    async def _calculate_tshirt_price(
        self, data: PriceCalculationRequest
    ) -> PriceCalculationResponse:
        """Calculate price for T-shirt."""
        # Validate attributes
        try:
            TshirtSize(data.size)
        except ValueError:
            valid_sizes = [s.value for s in TshirtSize]
            raise ValidationError(
                f"Invalid size '{data.size}'. Valid sizes: {valid_sizes}"
            )

        try:
            TshirtColor(data.color)
        except ValueError:
            valid_colors = [c.value for c in TshirtColor]
            raise ValidationError(
                f"Invalid color '{data.color}'. Valid colors: {valid_colors}"
            )

        try:
            TshirtPosition(data.position)
        except ValueError:
            valid_positions = [p.value for p in TshirtPosition]
            raise ValidationError(
                f"Invalid position '{data.position}'. Valid positions: {valid_positions}"
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
