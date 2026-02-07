"""External service for external sales site APIs."""

from app.models.order import (
    AcrylicKeychainColor,
    AcrylicKeychainSize,
    AcrylicStandColor,
    AcrylicStandSize,
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
from app.repositories.product_repository import ProductRepository
from app.schemas.external import (
    PriceCalculationRequest,
    PriceCalculationResponse,
    ProductOptionsResponse,
)
from app.utils.exceptions import ValidationError

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
    StickerColor.CLEAR.value: 105,
    StickerColor.WHITE.value: 79,
}


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
            )

        # Validate color (required for tshirt)
        if not data.color:
            raise ValidationError("color is required for T-shirt")
        try:
            TshirtColor(data.color)
        except ValueError:
            valid_colors = [c.value for c in TshirtColor]
            raise ValidationError(
                f"Invalid color '{data.color}'. Valid colors: {valid_colors}"
            )

        # Validate position (required for tshirt)
        if not data.position:
            raise ValidationError("position is required for T-shirt")
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
        # Validate size
        try:
            AcrylicStandSize(data.size)
        except ValueError:
            valid_sizes = [s.value for s in AcrylicStandSize]
            raise ValidationError(
                f"Invalid size '{data.size}'. Valid sizes: {valid_sizes}"
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
        # Validate size
        try:
            StickerSize(data.size)
        except ValueError:
            valid_sizes = [s.value for s in StickerSize]
            raise ValidationError(
                f"Invalid size '{data.size}'. Valid sizes: {valid_sizes}"
            )

        # Validate color (required for sticker)
        if not data.color:
            raise ValidationError("color is required for sticker")
        try:
            StickerColor(data.color)
        except ValueError:
            valid_colors = [c.value for c in StickerColor]
            raise ValidationError(
                f"Invalid color '{data.color}'. Valid colors: {valid_colors}"
            )

        # Calculate price based on color
        unit_price = STICKER_PRICES.get(data.color, 79)
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
            )

        # Validate color (required for tote bag)
        if not data.color:
            raise ValidationError("color is required for tote bag")
        try:
            ToteBagColor(data.color)
        except ValueError:
            valid_colors = [c.value for c in ToteBagColor]
            raise ValidationError(
                f"Invalid color '{data.color}'. Valid colors: {valid_colors}"
            )

        # Validate position (required for tote bag)
        if not data.position:
            raise ValidationError("position is required for tote bag")
        try:
            ToteBagPosition(data.position)
        except ValueError:
            valid_positions = [p.value for p in ToteBagPosition]
            raise ValidationError(
                f"Invalid position '{data.position}'. Valid positions: {valid_positions}"
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
