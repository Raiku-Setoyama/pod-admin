"""Unit tests for pod-admin -> manufacturing data generation parameter mapping."""

import pytest

from app.utils.mfg_product_mapping import (
    VARIANT_DTF,
    MfgMappingError,
    build_generation_spec,
    dtf_variant,
)


class TestSingleImageProducts:
    def test_tshirt_maps_size_and_pdf(self) -> None:
        m = build_generation_spec("tshirt", "M", {"design"})
        assert m.product_type == "tshirt"
        assert m.size == "M"
        assert m.variant is None
        assert m.required_layers == ("design",)

    def test_tshirt_accepts_color_as_design(self) -> None:
        m = build_generation_spec("tshirt", "L", {"color"})
        assert m.required_layers == ("color",)

    def test_tshirt_rejects_missing_design_layer(self) -> None:
        with pytest.raises(MfgMappingError):
            build_generation_spec("tshirt", "M", {"cutline"})

    def test_tote_bag_only_M(self) -> None:
        m = build_generation_spec("tote_bag", "M", {"design"})
        assert m.size == "M"

    def test_tshirt_invalid_size(self) -> None:
        with pytest.raises(MfgMappingError):
            build_generation_spec("tshirt", "XXL", {"design"})


class TestAcrylicKeychain:
    def test_variant_clear_without_white(self) -> None:
        m = build_generation_spec("acrylic_keychain", "50x50mm", {"color", "cutline"})
        assert m.size == "50x50"
        assert m.variant == "clear"

    def test_variant_color_with_white(self) -> None:
        m = build_generation_spec("acrylic_keychain", "100x100mm", {"color", "cutline", "white"})
        assert m.size == "100x100"
        assert m.variant == "color"
        assert "white" in m.usable_layers

    def test_requires_color_and_cutline(self) -> None:
        with pytest.raises(MfgMappingError):
            build_generation_spec("acrylic_keychain", "50x50mm", {"color"})


class TestAcrylicStand:
    def test_size_normalization_to_mm(self) -> None:
        m = build_generation_spec("acrylic_stand", "70x70mm", {"color", "cutline"})
        assert m.size == "70mm"
        assert m.variant is None

    def test_white_is_optional(self) -> None:
        m = build_generation_spec("acrylic_stand", "50x50mm", {"color", "cutline", "white"})
        assert m.size == "50mm"
        assert "white" in m.usable_layers


class TestSticker:
    def test_variant_is_always_clear_no_white(self) -> None:
        m = build_generation_spec("sticker", "50x50mm", {"color", "cutline"})
        assert m.size == "50x50"
        assert m.variant == "clear"
        assert "white" not in m.usable_layers

    def test_requires_color_and_cutline(self) -> None:
        with pytest.raises(MfgMappingError):
            build_generation_spec("sticker", "50x50mm", {"cutline"})


class TestUnsupported:
    def test_unknown_product_type(self) -> None:
        with pytest.raises(MfgMappingError):
            build_generation_spec("mug_cup", "normal", {"design"})

    def test_missing_size(self) -> None:
        with pytest.raises(MfgMappingError):
            build_generation_spec("acrylic_keychain", None, {"color", "cutline"})


class TestDtfVariant:
    """T シャツ・トートの DTF 版（#188）は variant を dtf にしてキャッシュを分ける."""

    @pytest.mark.parametrize(("product_type", "size"), [("tshirt", "M"), ("tote_bag", "M")])
    def test_dtf_sets_variant_for_tshirt_and_tote(self, product_type: str, size: str) -> None:
        m = build_generation_spec(product_type, size, {"design"}, dtf=True)
        assert m.variant == VARIANT_DTF == "dtf"
        # レイヤーとサイズの決め方は変わらない
        assert m.required_layers == ("design",)
        assert m.size == size

    @pytest.mark.parametrize("product_type", ["tshirt", "tote_bag"])
    def test_without_dtf_tshirt_and_tote_have_no_variant(self, product_type: str) -> None:
        assert build_generation_spec(product_type, "M", {"color"}).variant is None
        assert build_generation_spec(product_type, "M", {"color"}, dtf=False).variant is None

    @pytest.mark.parametrize(
        ("product_type", "size", "layers", "variant"),
        [
            ("acrylic_keychain", "50x50mm", {"color", "cutline"}, "clear"),
            ("acrylic_keychain", "50x50mm", {"color", "cutline", "white"}, "color"),
            ("acrylic_stand", "50x50mm", {"color", "cutline"}, None),
            ("sticker", "50x50mm", {"color", "cutline"}, "clear"),
        ],
    )
    def test_dtf_does_not_change_acrylic_products(
        self, product_type: str, size: str, layers: set[str], variant: str | None
    ) -> None:
        for dtf in (False, True):
            assert build_generation_spec(product_type, size, layers, dtf=dtf).variant == variant

    def test_dtf_variant_helper(self) -> None:
        assert dtf_variant("tshirt", True) == "dtf"
        assert dtf_variant("tote_bag", True) == "dtf"
        assert dtf_variant("tshirt", False) is None
        assert dtf_variant("acrylic_stand", True) is None
        assert dtf_variant("mug_cup", True) is None
