"""商品ごとの決まりごと（大きさ・テンプレート・出力ファイル名）.

illustrator-vm の `config/products.yaml` から、pod-admin が使う 5 商品の分を移したもの。
サイズの値は ``app.utils.mfg_product_mapping`` が正規化したもの（"50x50" / "50mm" / "M" など）。
"""

from __future__ import annotations

from pathlib import Path

from app.generator.errors import GenerationError

ASSETS = Path(__file__).resolve().parent / "assets"
TEMPLATES = ASSETS / "templates"
ICC_JAPAN_COLOR_2001_COATED = ASSETS / "icc" / "JapanColor2001Coated.icc"
ICC_SRGB = ASSETS / "icc" / "sRGB_IEC61966-2.1.icc"

TSHIRT_TEMPLATE = TEMPLATES / "Tシャツ_正面_ALLsize_297x406.ai"
TOTE_TEMPLATE = TEMPLATES / "キャンバストート_M_280x250.ai"

# アクリル系の、絵柄の一辺（mm）
_ACRYLIC_MM: dict[str, dict[str, int]] = {
    "acrylic_keychain": {"50x50": 50, "70x70": 70, "100x100": 100},
    "sticker": {"50x50": 50, "70x70": 70, "100x100": 100},
    "acrylic_stand": {"50mm": 50, "70mm": 70, "100mm": 100},
}

# 出力ファイル名（拡張子なし）。illustrator-vm の filename_pattern と同じ
_FILENAME_PATTERNS: dict[str, str] = {
    "tshirt": "{order_id}_Tshirts_front_{size}_297x406",
    "tote_bag": "【{order_id}】キャンバストート_{size}_280x250",
    "acrylic_keychain": "{order_id}_AcrylicKeychain_{variant}_{size}",
    "acrylic_stand": "【{order_id}】アクリルフィギュアスタンド_{size}_本体",
    "sticker": "{order_id}_Sticker_{variant}_{size}",
}

_PDF_PRODUCTS = frozenset({"tshirt", "tote_bag"})


def output_filename(product_type: str, size: str, variant: str | None, order_id: str) -> str:
    pattern = _FILENAME_PATTERNS.get(product_type)
    if pattern is None:
        raise GenerationError(f"unsupported product_type: {product_type}")
    ext = ".pdf" if product_type in _PDF_PRODUCTS else ".ai"
    return pattern.format(order_id=order_id, size=size, variant=variant or "") + ext


def acrylic_mm(product_type: str, size: str) -> int:
    """アクリル系の絵柄の一辺（mm）."""
    try:
        return _ACRYLIC_MM[product_type][size]
    except KeyError:
        raise GenerationError(f"unsupported size '{size}' for {product_type}") from None


def keyhole_template(mm: int) -> Path:
    return TEMPLATES / f"アクリルキーホルダー_キー穴_{mm}x{mm}.ai"


def stand_tab_template(mm: int) -> Path:
    return TEMPLATES / f"アクリルスタンド_{mm}mm.ai"
