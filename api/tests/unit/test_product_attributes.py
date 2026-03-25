"""Tests for product attribute registry module."""

import pytest

from app.models.product import ProductType
from app.models.product_attributes import (
    PRODUCT_ATTRIBUTES,
    AcrylicKeychainColor,
    AcrylicKeychainSize,
    AcrylicStandColor,
    AcrylicStandSize,
    ProductAttributeSpec,
    StickerColor,
    StickerSize,
    ToteBagColor,
    ToteBagPosition,
    ToteBagSize,
    TshirtColor,
    TshirtPosition,
    TshirtSize,
    get_attribute_spec,
    validate_product_attributes,
)
from app.utils.exceptions import ValidationError


class TestEnumValues:
    """ENUM values match existing definitions in order.py."""

    def test_tshirt_size_values(self):
        assert [e.value for e in TshirtSize] == ["S", "M", "L", "XL"]

    def test_tshirt_color_values(self):
        assert [e.value for e in TshirtColor] == ["白"]

    def test_tshirt_position_values(self):
        assert [e.value for e in TshirtPosition] == ["正面"]

    def test_acrylic_keychain_size_values(self):
        assert [e.value for e in AcrylicKeychainSize] == ["50x50mm", "70x70mm", "100x100mm"]

    def test_acrylic_keychain_color_values(self):
        assert [e.value for e in AcrylicKeychainColor] == ["アクリル"]

    def test_acrylic_stand_size_values(self):
        assert [e.value for e in AcrylicStandSize] == ["50x50mm", "70x70mm", "100x100mm"]

    def test_acrylic_stand_color_values(self):
        assert [e.value for e in AcrylicStandColor] == ["アクリル"]

    def test_sticker_size_values(self):
        assert [e.value for e in StickerSize] == ["50x50mm", "70x70mm", "100x100mm"]

    def test_sticker_color_values(self):
        assert [e.value for e in StickerColor] == ["ホワイト"]

    def test_tote_bag_size_values(self):
        assert [e.value for e in ToteBagSize] == ["M"]

    def test_tote_bag_color_values(self):
        assert [e.value for e in ToteBagColor] == ["ナチュラル"]

    def test_tote_bag_position_values(self):
        assert [e.value for e in ToteBagPosition] == ["正面"]


class TestProductAttributeSpec:
    """ProductAttributeSpec dataclass."""

    def test_creation(self):
        spec = ProductAttributeSpec(
            sizes=("S", "M"),
            colors=("白",),
            positions=("正面",),
            required_size=True,
            required_color=True,
            required_position=False,
        )
        assert spec.sizes == ("S", "M")
        assert spec.colors == ("白",)
        assert spec.positions == ("正面",)
        assert spec.required_size is True
        assert spec.required_color is True
        assert spec.required_position is False


class TestProductAttributes:
    """PRODUCT_ATTRIBUTES registry covers all product types."""

    def test_all_product_types_covered(self):
        for pt in ProductType:
            assert pt in PRODUCT_ATTRIBUTES, f"{pt} not in PRODUCT_ATTRIBUTES"

    def test_tshirt_spec(self):
        spec = PRODUCT_ATTRIBUTES[ProductType.TSHIRT]
        assert spec.sizes == ("S", "M", "L", "XL")
        assert spec.colors == ("白",)
        assert spec.positions == ("正面",)
        assert spec.required_size is True
        assert spec.required_color is True
        assert spec.required_position is True

    def test_acrylic_keychain_spec(self):
        spec = PRODUCT_ATTRIBUTES[ProductType.ACRYLIC_KEYCHAIN]
        assert spec.sizes == ("50x50mm", "70x70mm", "100x100mm")
        assert spec.colors == ("アクリル",)
        assert spec.required_size is True
        assert spec.required_color is False
        assert spec.required_position is False

    def test_acrylic_stand_spec(self):
        spec = PRODUCT_ATTRIBUTES[ProductType.ACRYLIC_STAND]
        assert spec.sizes == ("50x50mm", "70x70mm", "100x100mm")
        assert spec.colors == ("アクリル",)
        assert spec.required_size is True
        assert spec.required_color is False
        assert spec.required_position is False

    def test_sticker_spec(self):
        spec = PRODUCT_ATTRIBUTES[ProductType.STICKER]
        assert spec.sizes == ("50x50mm", "70x70mm", "100x100mm")
        assert spec.colors == ("ホワイト",)
        assert spec.required_size is True
        assert spec.required_color is True
        assert spec.required_position is False

    def test_tote_bag_spec(self):
        spec = PRODUCT_ATTRIBUTES[ProductType.TOTE_BAG]
        assert spec.sizes == ("M",)
        assert spec.colors == ("ナチュラル",)
        assert spec.positions == ("正面",)
        assert spec.required_size is True
        assert spec.required_color is True
        assert spec.required_position is True


class TestGetAttributeSpec:
    """get_attribute_spec function."""

    def test_returns_spec_for_valid_type(self):
        spec = get_attribute_spec(ProductType.TSHIRT)
        assert isinstance(spec, ProductAttributeSpec)
        assert spec.sizes == ("S", "M", "L", "XL")

    def test_returns_spec_for_all_types(self):
        for pt in ProductType:
            spec = get_attribute_spec(pt)
            assert isinstance(spec, ProductAttributeSpec)


class TestValidateProductAttributes:
    """validate_product_attributes function."""

    # --- Valid cases ---

    def test_valid_tshirt(self):
        # Should not raise
        validate_product_attributes(ProductType.TSHIRT, size="S", color="白", position="正面")

    def test_valid_acrylic_keychain_all_attrs(self):
        validate_product_attributes(
            ProductType.ACRYLIC_KEYCHAIN, size="50x50mm", color="アクリル", position=None
        )

    def test_valid_acrylic_keychain_optional_omitted(self):
        validate_product_attributes(
            ProductType.ACRYLIC_KEYCHAIN, size="70x70mm", color=None, position=None
        )

    def test_valid_sticker(self):
        validate_product_attributes(
            ProductType.STICKER, size="100x100mm", color="ホワイト", position=None
        )

    def test_valid_tote_bag(self):
        validate_product_attributes(
            ProductType.TOTE_BAG, size="M", color="ナチュラル", position="正面"
        )

    # --- Required attribute missing ---

    def test_missing_required_size(self):
        with pytest.raises(ValidationError, match="size is required for tshirt"):
            validate_product_attributes(ProductType.TSHIRT, size=None, color="白", position="正面")

    def test_missing_required_size_empty_string(self):
        with pytest.raises(ValidationError, match="size is required for tshirt"):
            validate_product_attributes(ProductType.TSHIRT, size="", color="白", position="正面")

    def test_missing_required_color(self):
        with pytest.raises(ValidationError, match="color is required for tshirt"):
            validate_product_attributes(ProductType.TSHIRT, size="S", color=None, position="正面")

    def test_missing_required_position(self):
        with pytest.raises(ValidationError, match="position is required for tshirt"):
            validate_product_attributes(ProductType.TSHIRT, size="S", color="白", position=None)

    # --- Invalid attribute values ---

    def test_invalid_size(self):
        with pytest.raises(ValidationError, match="Invalid size 'XXL'"):
            validate_product_attributes(ProductType.TSHIRT, size="XXL", color="白", position="正面")

    def test_invalid_size_shows_valid_values(self):
        with pytest.raises(ValidationError, match=r"Valid: \('S', 'M', 'L', 'XL'\)"):
            validate_product_attributes(ProductType.TSHIRT, size="XXL", color="白", position="正面")

    def test_invalid_color(self):
        with pytest.raises(ValidationError, match="Invalid color '黒'"):
            validate_product_attributes(ProductType.TSHIRT, size="S", color="黒", position="正面")

    def test_invalid_position(self):
        with pytest.raises(ValidationError, match="Invalid position '背面'"):
            validate_product_attributes(ProductType.TSHIRT, size="S", color="白", position="背面")

    # --- Optional attribute provided but invalid ---

    def test_optional_color_invalid(self):
        with pytest.raises(ValidationError, match="Invalid color '赤'"):
            validate_product_attributes(
                ProductType.ACRYLIC_KEYCHAIN, size="50x50mm", color="赤", position=None
            )

    # --- uid parameter ---

    def test_uid_appended_to_required_error(self):
        with pytest.raises(ValidationError, match=r"size is required for tshirt \(uid: abc-123\)"):
            validate_product_attributes(
                ProductType.TSHIRT, size=None, color="白", position="正面", uid="abc-123"
            )

    def test_uid_appended_to_invalid_error(self):
        with pytest.raises(ValidationError, match=r"\(uid: abc-123\)"):
            validate_product_attributes(
                ProductType.TSHIRT, size="XXL", color="白", position="正面", uid="abc-123"
            )
