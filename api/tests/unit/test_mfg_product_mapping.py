"""Unit tests for pod-admin -> illustrator-vm product attribute mapping."""

import pytest

from app.utils.mfg_product_mapping import (
    INPUT_MODE_MULTI,
    INPUT_MODE_SINGLE,
    MfgMappingError,
    build_vm_mapping,
)


class TestSingleImageProducts:
    def test_tshirt_maps_size_and_pdf(self):
        m = build_vm_mapping("tshirt", "M", {"design"})
        assert m.product_type == "tshirt"
        assert m.size == "M"
        assert m.variant is None
        assert m.input_mode == INPUT_MODE_SINGLE
        assert m.output_ext == ".pdf"
        assert m.required_layers == ("design",)

    def test_tshirt_accepts_color_as_design(self):
        m = build_vm_mapping("tshirt", "L", {"color"})
        assert m.required_layers == ("color",)

    def test_tshirt_rejects_missing_design_layer(self):
        with pytest.raises(MfgMappingError):
            build_vm_mapping("tshirt", "M", {"cutline"})

    def test_tote_bag_only_M(self):
        m = build_vm_mapping("tote_bag", "M", {"design"})
        assert m.size == "M"
        assert m.output_ext == ".pdf"

    def test_tshirt_invalid_size(self):
        with pytest.raises(MfgMappingError):
            build_vm_mapping("tshirt", "XXL", {"design"})


class TestAcrylicKeychain:
    def test_variant_clear_without_white(self):
        m = build_vm_mapping("acrylic_keychain", "50x50mm", {"color", "cutline"})
        assert m.size == "50x50"
        assert m.variant == "clear"
        assert m.input_mode == INPUT_MODE_MULTI
        assert m.output_ext == ".ai"

    def test_variant_color_with_white(self):
        m = build_vm_mapping("acrylic_keychain", "100x100mm", {"color", "cutline", "white"})
        assert m.size == "100x100"
        assert m.variant == "color"
        assert "white" in m.usable_layers

    def test_requires_color_and_cutline(self):
        with pytest.raises(MfgMappingError):
            build_vm_mapping("acrylic_keychain", "50x50mm", {"color"})


class TestAcrylicStand:
    def test_size_normalization_to_mm(self):
        m = build_vm_mapping("acrylic_stand", "70x70mm", {"color", "cutline"})
        assert m.size == "70mm"
        assert m.variant is None
        assert m.input_mode == INPUT_MODE_MULTI

    def test_white_is_optional(self):
        m = build_vm_mapping("acrylic_stand", "50x50mm", {"color", "cutline", "white"})
        assert m.size == "50mm"
        assert "white" in m.usable_layers


class TestSticker:
    def test_variant_is_always_clear_no_white(self):
        m = build_vm_mapping("sticker", "50x50mm", {"color", "cutline"})
        assert m.size == "50x50"
        assert m.variant == "clear"
        assert "white" not in m.usable_layers

    def test_requires_color_and_cutline(self):
        with pytest.raises(MfgMappingError):
            build_vm_mapping("sticker", "50x50mm", {"cutline"})


class TestUnsupported:
    def test_unknown_product_type(self):
        with pytest.raises(MfgMappingError):
            build_vm_mapping("mug_cup", "normal", {"design"})

    def test_missing_size(self):
        with pytest.raises(MfgMappingError):
            build_vm_mapping("acrylic_keychain", None, {"color", "cutline"})
