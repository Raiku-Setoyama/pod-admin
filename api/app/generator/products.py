"""商品ごとの決まりごと（大きさ・テンプレート・出力ファイル名）.

illustrator-vm の `config/products.yaml` から、pod-admin が使う 5 商品の分を移したもの。
サイズの値は ``app.utils.mfg_product_mapping`` が正規化したもの（"50x50" / "50mm" / "M" など）。
"""

from __future__ import annotations

from dataclasses import dataclass
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

# --- DTF（T シャツ・トート。#187） ----------------------------------------------------
# 大きさと配置はインクジェットのとき（テンプレートに 1mm の余白で収めて上下左右中央）と同じ。
# 印刷位置の値は、メーカー回答「261106_DTF用印刷データに関する回答」（2026-11-06）による。

# 画像を枠に収めるときの余白（インクジェットの ``pipelines.TEMPLATE_IMAGE_MARGIN_PT`` と同じ 1mm）
DTF_IMAGE_MARGIN_MM = 1.0
# T シャツの枠（テンプレート「Tシャツ_正面_ALLsize_297x406」のアートボード。全サイズ共通）
TSHIRT_FRAME_MM = (297.0, 406.0)
# T シャツの標準位置: リブ下から枠の上端まで。正面・背面共通（メーカー回答）
TSHIRT_FRAME_TOP_BELOW_RIB_MM: dict[str, float] = {"S": 60.0, "M": 60.0, "L": 80.0, "XL": 80.0}
# トートの水色のガイド（DTF テンプレート「キャンバストート(M)_36x37x11」のパス「W300xH270」）。
# 上端＝リブ下 3cm（メーカー回答「リブ下から 3cm が印刷可能開始位置（水色のガイド内）」）
TOTE_GUIDE_MM = (300.0, 270.0)
TOTE_GUIDE_TOP_BELOW_RIB_MM = 30.0
# トートの印刷範囲（インクジェットと同じ 280×250）。ガイドの中央に置く（#191「決めたこと 2」）
TOTE_PRINT_AREA_MM = (280.0, 250.0)
_TOTE_SIZES = frozenset({"M"})


@dataclass(frozen=True)
class DtfPlacement:
    """DTF で画像を収める枠（mm）. 画像は余白 ``DTF_IMAGE_MARGIN_MM`` で縦横比を保って収め、中央に置く."""

    width_mm: float
    height_mm: float
    # リブ下から枠の上端まで
    top_below_rib_mm: float


def dtf_placement(product_type: str, size: str) -> DtfPlacement:
    """DTF の製造データで、画像を収める枠."""
    if product_type == "tshirt" and size in TSHIRT_FRAME_TOP_BELOW_RIB_MM:
        w, h = TSHIRT_FRAME_MM
        return DtfPlacement(w, h, TSHIRT_FRAME_TOP_BELOW_RIB_MM[size])
    if product_type == "tote_bag" and size in _TOTE_SIZES:
        w, h = TOTE_PRINT_AREA_MM
        top = TOTE_GUIDE_TOP_BELOW_RIB_MM + (TOTE_GUIDE_MM[1] - h) / 2
        return DtfPlacement(w, h, top)
    raise GenerationError(f"unsupported size '{size}' for DTF {product_type}")


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
