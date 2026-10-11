"""製造データの出力ファイル名と同梱物（app/generator/products.py、REQ-0067）."""

import pytest

from app.generator.errors import GenerationError
from app.generator.pdf_finish import icc_description
from app.generator.products import (
    ICC_JAPAN_COLOR_2001_COATED,
    ICC_SRGB,
    TOTE_TEMPLATE,
    TSHIRT_TEMPLATE,
    acrylic_mm,
    keyhole_template,
    output_filename,
    stand_tab_template,
)


@pytest.mark.parametrize(
    ("product_type", "size", "variant", "expected"),
    [
        # illustrator-vm（config/products.yaml の filename_pattern）と同じ規則
        ("tshirt", "M", None, "md-1_Tshirts_front_M_297x406.pdf"),
        ("tote_bag", "M", None, "【md-1】キャンバストート_M_280x250.pdf"),
        ("acrylic_keychain", "50x50", "color", "md-1_AcrylicKeychain_color_50x50.ai"),
        ("acrylic_keychain", "70x70", "clear", "md-1_AcrylicKeychain_clear_70x70.ai"),
        ("acrylic_stand", "100mm", None, "【md-1】アクリルフィギュアスタンド_100mm_本体.ai"),
        ("sticker", "100x100", "clear", "md-1_Sticker_clear_100x100.ai"),
    ],
)
def test_output_filename_follows_the_vm_rules(
    product_type: str, size: str, variant: str | None, expected: str
) -> None:
    assert output_filename(product_type, size, variant, "md-1") == expected


def test_unknown_product_is_rejected() -> None:
    with pytest.raises(GenerationError):
        output_filename("mug_cup", "normal", None, "md-1")


@pytest.mark.parametrize(
    ("product_type", "size", "mm"),
    [("acrylic_keychain", "70x70", 70), ("sticker", "50x50", 50), ("acrylic_stand", "100mm", 100)],
)
def test_acrylic_sizes(product_type: str, size: str, mm: int) -> None:
    assert acrylic_mm(product_type, size) == mm


def test_templates_for_every_size_are_bundled() -> None:
    for mm in (50, 70, 100):
        assert keyhole_template(mm).is_file()
        assert stand_tab_template(mm).is_file()
    assert TSHIRT_TEMPLATE.is_file()
    assert TOTE_TEMPLATE.is_file()


def test_bundled_icc_profiles_are_the_expected_ones() -> None:
    """製造委託先が見るプロファイル名（Illustrator のドキュメント情報に出る名前）."""
    assert icc_description(ICC_SRGB.read_bytes()) == "sRGB IEC61966-2.1"
    assert icc_description(ICC_JAPAN_COLOR_2001_COATED.read_bytes()) == "Japan Color 2001 Coated"
