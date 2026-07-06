"""Unit tests for mfg_product_mapping (pure attribute mapping for illustrator-vm)."""

import pytest

from app.utils.exceptions import ValidationError
from app.utils.mfg_product_mapping import (
    SUPPORTED_PRODUCT_TYPES,
    is_supported,
    normalize_variant,
    resolve_vm_mapping,
    select_layers,
    validate_v2_item,
)


class TestSupportedTypes:
    def test_supported_set_is_five_types(self):
        assert SUPPORTED_PRODUCT_TYPES == {
            "tshirt",
            "tote_bag",
            "acrylic_keychain",
            "acrylic_stand",
            "sticker",
        }

    def test_mug_cup_out_of_scope(self):
        assert not is_supported("mug_cup")
        assert is_supported("acrylic_keychain")


class TestResolveVmMapping:
    @pytest.mark.parametrize(
        ("product_type", "size", "expected_vm_size"),
        [
            ("acrylic_keychain", "50x50mm", "50x50"),
            ("acrylic_keychain", "70x70mm", "70x70"),
            ("acrylic_keychain", "100x100mm", "100x100"),
            ("sticker", "50x50mm", "50x50"),
            ("sticker", "100x100mm", "100x100"),
            # acrylic_stand uses a DIFFERENT size id mapping
            ("acrylic_stand", "50x50mm", "50mm"),
            ("acrylic_stand", "70x70mm", "70mm"),
            ("acrylic_stand", "100x100mm", "100mm"),
            ("tshirt", "M", "M"),
            ("tshirt", "XL", "XL"),
            ("tote_bag", "M", "M"),
        ],
    )
    def test_size_mapping(self, product_type, size, expected_vm_size):
        variant = "clear" if product_type in ("acrylic_keychain", "sticker") else None
        mapping = resolve_vm_mapping(product_type, size, variant)
        assert mapping.vm_size == expected_vm_size

    def test_keychain_variant_and_layers(self):
        mapping = resolve_vm_mapping("acrylic_keychain", "50x50mm", "color")
        assert mapping.variant == "color"
        assert mapping.input_mode == "multi"
        assert mapping.required_layers == ("color", "cutline")
        assert mapping.optional_layers == ("white",)
        assert mapping.output_format == "ai"

    def test_sticker_has_no_white_layer(self):
        mapping = resolve_vm_mapping("sticker", "70x70mm", "clear")
        assert mapping.required_layers == ("color", "cutline")
        assert mapping.optional_layers == ()
        assert mapping.variant == "clear"

    def test_tshirt_is_single_pdf(self):
        mapping = resolve_vm_mapping("tshirt", "L", None)
        assert mapping.input_mode == "single"
        assert mapping.required_layers == ("design",)
        assert mapping.output_format == "pdf"
        assert mapping.variant is None

    def test_stand_variant_is_ignored(self):
        # acrylic_stand はバリアントなし → 送られても None に正規化
        mapping = resolve_vm_mapping("acrylic_stand", "70x70mm", "clear")
        assert mapping.variant is None

    def test_unsupported_product_type_raises(self):
        with pytest.raises(ValidationError):
            resolve_vm_mapping("mug_cup", "normal", None)

    @pytest.mark.parametrize(
        ("product_type", "size"),
        [
            ("tshirt", "XXL"),
            ("acrylic_keychain", "60x60mm"),
            ("acrylic_stand", "M"),
            ("tote_bag", "L"),
        ],
    )
    def test_invalid_size_raises(self, product_type, size):
        variant = "clear" if product_type == "acrylic_keychain" else None
        with pytest.raises(ValidationError):
            resolve_vm_mapping(product_type, size, variant)

    def test_keychain_missing_variant_raises(self):
        with pytest.raises(ValidationError):
            resolve_vm_mapping("acrylic_keychain", "50x50mm", None)

    def test_keychain_invalid_variant_raises(self):
        with pytest.raises(ValidationError):
            resolve_vm_mapping("acrylic_keychain", "50x50mm", "blue")

    def test_sticker_missing_variant_raises(self):
        with pytest.raises(ValidationError):
            resolve_vm_mapping("sticker", "50x50mm", None)


class TestNormalizeVariant:
    def test_required_variant_ok(self):
        assert normalize_variant("acrylic_keychain", "clear") == "clear"
        assert normalize_variant("sticker", "clear") == "clear"

    def test_non_variant_type_forces_none(self):
        assert normalize_variant("acrylic_stand", "clear") is None
        assert normalize_variant("tshirt", None) is None
        assert normalize_variant("tote_bag", "anything") is None


class TestSelectLayers:
    def test_keychain_color_cutline(self):
        layers = select_layers(
            "acrylic_keychain",
            [
                {"layer_type": "color", "url": "http://x/c.png"},
                {"layer_type": "cutline", "url": "http://x/l.png"},
            ],
        )
        assert layers == {"color": "http://x/c.png", "cutline": "http://x/l.png"}

    def test_keychain_with_optional_white(self):
        layers = select_layers(
            "acrylic_keychain",
            [
                {"layer_type": "color", "url": "http://x/c.png"},
                {"layer_type": "cutline", "url": "http://x/l.png"},
                {"layer_type": "white", "url": "http://x/w.png"},
            ],
        )
        assert layers["white"] == "http://x/w.png"

    def test_keychain_missing_cutline_raises(self):
        with pytest.raises(ValidationError):
            select_layers(
                "acrylic_keychain",
                [{"layer_type": "color", "url": "http://x/c.png"}],
            )

    def test_sticker_white_is_unknown_layer(self):
        # sticker は white レイヤーを持たない → 未対応レイヤーとして拒否
        with pytest.raises(ValidationError):
            select_layers(
                "sticker",
                [
                    {"layer_type": "color", "url": "http://x/c.png"},
                    {"layer_type": "cutline", "url": "http://x/l.png"},
                    {"layer_type": "white", "url": "http://x/w.png"},
                ],
            )

    def test_tshirt_design(self):
        layers = select_layers("tshirt", [{"layer_type": "design", "url": "http://x/d.png"}])
        assert layers == {"design": "http://x/d.png"}

    def test_tshirt_accepts_color_as_design_alias(self):
        layers = select_layers("tshirt", [{"layer_type": "color", "url": "http://x/c.png"}])
        assert layers == {"design": "http://x/c.png"}

    def test_single_missing_image_raises(self):
        with pytest.raises(ValidationError):
            select_layers("tote_bag", [])

    def test_multi_unknown_layer_raises(self):
        with pytest.raises(ValidationError):
            select_layers(
                "acrylic_stand",
                [
                    {"layer_type": "color", "url": "http://x/c.png"},
                    {"layer_type": "cutline", "url": "http://x/l.png"},
                    {"layer_type": "bogus", "url": "http://x/b.png"},
                ],
            )


class TestValidateV2Item:
    def test_valid_item_returns_mapping(self):
        mapping = validate_v2_item(
            "acrylic_keychain",
            "50x50mm",
            "clear",
            [
                {"layer_type": "color", "url": "http://x/c.png"},
                {"layer_type": "cutline", "url": "http://x/l.png"},
            ],
        )
        assert mapping.vm_size == "50x50"
        assert mapping.variant == "clear"

    def test_invalid_layers_raise(self):
        with pytest.raises(ValidationError):
            validate_v2_item("acrylic_keychain", "50x50mm", "clear", [])
