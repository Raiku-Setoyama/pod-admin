"""Unit tests for pod-admin -> manufacturing data generation parameter mapping."""

import pytest

from app.utils.mfg_product_mapping import (
    MfgMappingError,
    build_generation_spec,
    position_from_variant,
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


class TestTshirtPosition:
    """REQ-0070: 印刷位置は variant に載せる（manufacturing_data に position 列は無い）."""

    def test_left_chest_becomes_variant(self) -> None:
        m = build_generation_spec("tshirt", "M", {"design"}, position="左胸")
        assert m.variant == "left_chest"
        assert m.required_layers == ("design",)

    @pytest.mark.parametrize("position", ["正面", None])
    def test_front_keeps_variant_none(self, position: str | None) -> None:
        # 既存の製造データ行（variant NULL）と同じキャッシュキーに当たる
        m = build_generation_spec("tshirt", "M", {"design"}, position=position)
        assert m.variant is None

    def test_unknown_position_fails_closed(self) -> None:
        with pytest.raises(MfgMappingError, match="背面"):
            build_generation_spec("tshirt", "M", {"design"}, position="背面")

    def test_tote_bag_has_no_left_chest(self) -> None:
        with pytest.raises(MfgMappingError, match="左胸"):
            build_generation_spec("tote_bag", "M", {"design"}, position="左胸")

    def test_position_is_ignored_for_other_products(self) -> None:
        m = build_generation_spec("sticker", "50x50mm", {"color", "cutline"}, position="左胸")
        assert m.variant == "clear"

    @pytest.mark.parametrize(("variant", "position"), [(None, None), ("left_chest", "左胸")])
    def test_position_from_variant_round_trips(self, variant: str | None, position: str | None) -> None:
        # 行からの再生成は variant しか持たないので、position に戻してから spec を作る
        assert position_from_variant("tshirt", variant) == position
        assert build_generation_spec("tshirt", "M", {"design"}, position=position).variant == variant

    def test_position_from_variant_rejects_unknown_tshirt_variant(self) -> None:
        with pytest.raises(MfgMappingError, match="pocket"):
            position_from_variant("tshirt", "pocket")

    def test_position_from_variant_is_none_for_other_products(self) -> None:
        assert position_from_variant("acrylic_keychain", "color") is None
