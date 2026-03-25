"""Product attribute registry module.

Centralised definitions for product-specific ENUMs, attribute specs,
and validation helpers.
"""

from dataclasses import dataclass
from enum import Enum

from app.models.product import ProductType
from app.utils.exceptions import ValidationError


# ---------------------------------------------------------------------------
# ENUMs – same values that were originally in order.py
# ---------------------------------------------------------------------------

class TshirtSize(str, Enum):
    """Tシャツサイズ."""

    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class TshirtColor(str, Enum):
    """Tシャツカラー."""

    WHITE = "白"


class TshirtPosition(str, Enum):
    """Tシャツプリント位置."""

    FRONT = "正面"


class AcrylicKeychainSize(str, Enum):
    """アクリルキーホルダーサイズ."""

    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class AcrylicKeychainColor(str, Enum):
    """アクリルキーホルダーカラー."""

    ACRYLIC = "アクリル"


class AcrylicStandSize(str, Enum):
    """アクリルスタンドサイズ."""

    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class AcrylicStandColor(str, Enum):
    """アクリルスタンドカラー."""

    ACRYLIC = "アクリル"


class StickerSize(str, Enum):
    """ステッカーサイズ."""

    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class StickerColor(str, Enum):
    """ステッカーカラー."""

    WHITE = "ホワイト"


class ToteBagSize(str, Enum):
    """トートバッグサイズ."""

    M = "M"


class ToteBagColor(str, Enum):
    """トートバッグカラー."""

    NATURAL = "ナチュラル"


class ToteBagPosition(str, Enum):
    """トートバッグプリント位置."""

    FRONT = "正面"


# ---------------------------------------------------------------------------
# Attribute spec dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductAttributeSpec:
    """Specification of valid attributes for a product type."""

    sizes: list[str]
    colors: list[str]
    positions: list[str]
    required_size: bool
    required_color: bool
    required_position: bool


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PRODUCT_ATTRIBUTES: dict[ProductType, ProductAttributeSpec] = {
    ProductType.TSHIRT: ProductAttributeSpec(
        sizes=[e.value for e in TshirtSize],
        colors=[e.value for e in TshirtColor],
        positions=[e.value for e in TshirtPosition],
        required_size=True,
        required_color=True,
        required_position=True,
    ),
    ProductType.ACRYLIC_KEYCHAIN: ProductAttributeSpec(
        sizes=[e.value for e in AcrylicKeychainSize],
        colors=[e.value for e in AcrylicKeychainColor],
        positions=[],
        required_size=True,
        required_color=False,
        required_position=False,
    ),
    ProductType.ACRYLIC_STAND: ProductAttributeSpec(
        sizes=[e.value for e in AcrylicStandSize],
        colors=[e.value for e in AcrylicStandColor],
        positions=[],
        required_size=True,
        required_color=False,
        required_position=False,
    ),
    ProductType.STICKER: ProductAttributeSpec(
        sizes=[e.value for e in StickerSize],
        colors=[e.value for e in StickerColor],
        positions=[],
        required_size=True,
        required_color=True,
        required_position=False,
    ),
    ProductType.TOTE_BAG: ProductAttributeSpec(
        sizes=[e.value for e in ToteBagSize],
        colors=[e.value for e in ToteBagColor],
        positions=[e.value for e in ToteBagPosition],
        required_size=True,
        required_color=True,
        required_position=True,
    ),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_attribute_spec(product_type: ProductType) -> ProductAttributeSpec:
    """Return the attribute spec for a product type."""
    return PRODUCT_ATTRIBUTES[product_type]


def validate_product_attributes(
    product_type: ProductType,
    *,
    size: str | None,
    color: str | None,
    position: str | None,
    uid: str | None = None,
) -> None:
    """Validate product attributes against the registry.

    Raises ``ValidationError`` when a required attribute is missing or
    an attribute value is not in the allowed list.
    """
    spec = get_attribute_spec(product_type)
    suffix = f" (uid: {uid})" if uid else ""
    type_label = product_type.value

    # --- size ---
    if spec.required_size and not size:
        raise ValidationError(f"size is required for {type_label}{suffix}")
    if size:
        if size not in spec.sizes:
            raise ValidationError(
                f"Invalid size '{size}'. Valid: {spec.sizes}{suffix}"
            )

    # --- color ---
    if spec.required_color and not color:
        raise ValidationError(f"color is required for {type_label}{suffix}")
    if color:
        if color not in spec.colors:
            raise ValidationError(
                f"Invalid color '{color}'. Valid: {spec.colors}{suffix}"
            )

    # --- position ---
    if spec.required_position and not position:
        raise ValidationError(f"position is required for {type_label}{suffix}")
    if position:
        if position not in spec.positions:
            raise ValidationError(
                f"Invalid position '{position}'. Valid: {spec.positions}{suffix}"
            )
