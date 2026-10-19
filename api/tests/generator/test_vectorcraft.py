"""製造データ生成を VectorCraft で実際に動かす（REQ-0067 の受入基準）.

VectorCraft の実行ファイルが無い環境ではスキップする。ワーカー用のイメージ
（`docker build --target worker`）と、GENERATOR_VECTORCRAFT_CLI に CLI を指定した手元の環境で動く。

入力は合成した画像。販売サイトの画像と同じく 1 枚の画像が絵柄の一辺（mm）に引き伸ばされる。
Illustrator 版との比較（形のずれ・色の差）は移行時の検証で行っている（REQ-0067 の背景）。
"""

from __future__ import annotations

import io
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from PIL import Image, ImageDraw
from pypdf import PageObject, PdfReader
from pypdf.generic import ArrayObject, ContentStream, DictionaryObject

from app.config import settings
from app.generator import GeneratedFile, GenerationError, check_available, generate
from app.generator.pdf_finish import icc_description
from app.utils.mfg_product_mapping import build_generation_spec

CLI = shutil.which(settings.GENERATOR_VECTORCRAFT_CLI)
pytestmark = pytest.mark.skipif(CLI is None, reason="VectorCraft CLI is not installed")

MM = 72 / 25.4
PX = 600  # 画像の一辺（px）

# --- 合成画像 -------------------------------------------------------------------


def _png(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


Rgba = tuple[int, int, int, int]


def _layer(draw_fn: Callable[[ImageDraw.ImageDraw, Rgba], None], fill: Rgba = (0, 0, 0, 255)) -> Image.Image:
    im = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), fill)
    return im


def _body(d: ImageDraw.ImageDraw, fill: Rgba, inset: int = 0) -> None:
    d.ellipse((100 + inset, 60 + inset, 500 - inset, 520 - inset), fill=fill)


def _acrylic_inputs(*, base: str = "flat", keyhole: bool = False, white_hole: bool = False) -> dict[str, bytes]:
    """アクリル系の入力（color / cutline / white）."""

    def cutline(d: ImageDraw.ImageDraw, fill: Rgba) -> None:
        if base == "none":
            d.ellipse((60, 60, 540, 540), fill=fill)
            return
        _body(d, fill)
        if base in ("flat", "protruding"):
            d.rectangle((120, 470, 480, 560), fill=fill)  # 土台（下辺 y=560）
        if base == "protruding":
            d.ellipse((400, 540, 440, 580), fill=fill)  # 土台の下へ約 1.7mm はみ出す足先
        if keyhole:
            d.ellipse((290, 75, 310, 95), fill=(0, 0, 0, 0))  # キー穴（直径 ≈1.7mm）

    color = _layer(lambda d, f: _body(d, f, inset=12), fill=(40, 120, 200, 255))
    white = _layer(lambda d, f: _body(d, f, inset=18))
    if white_hole:
        # 白版の内側の穴。下の印刷画像は半透明の白（白い羽の模様など）
        ImageDraw.Draw(white).ellipse((280, 280, 320, 320), fill=(0, 0, 0, 0))
        ImageDraw.Draw(color).ellipse((280, 280, 320, 320), fill=(250, 250, 250, 100))
    return {"color": _png(color), "cutline": _png(_layer(cutline)), "white": _png(white)}


def _run(
    product_type: str, size: str, images: dict[str, bytes], position: str | None = None
) -> GeneratedFile:
    """ワーカーと同じ経路で生成する（pod-admin の商品属性 → 生成のパラメータ → 生成）."""
    spec = build_generation_spec(product_type, size, images.keys(), position=position)
    return generate(spec, images, "md-1")


# --- 旧形式 .ai（Illustrator 8 形式）の読み取り -----------------------------------


@dataclass
class Ai8:
    art_size: tuple[float, float]
    layers: dict[str, str]  # レイヤー名 → 中身（背面から順に並ぶ）


def _parse_ai8(content: bytes) -> Ai8:
    text = content.decode("shift_jis")
    assert text.startswith("%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator(R) 8.0")
    size = re.search(r"%AI5_ArtSize: ([\d.]+) ([\d.]+)", text)
    assert size is not None
    layers = {}
    for block in text.split("%AI5_BeginLayer")[1:]:
        name = re.search(r"\((.*?)\) Ln", block)
        assert name is not None
        layers[name.group(1)] = block.split("%AI5_EndLayer--")[0]
    return Ai8((float(size.group(1)), float(size.group(2))), layers)


def _subpath_count(layer: str) -> int:
    return len(re.findall(r"^[-\d.]+ [-\d.]+ m$", layer, re.MULTILINE))


def _assert_acrylic_structure(ai: Ai8, *, stroke_pt: float, white: str) -> None:
    """``white``: "plate"（白版あり）/ "empty"（空の White レイヤー）/ "none"（レイヤー無し）.

    レイヤーの有無は illustrator-vm と同じ。キーホルダー・スタンドは白版画像が無ければ White を作らず、
    ステッカーは常に空の White を持つ。
    """
    # Illustrator で開いたとき、上から CutLine / ColorPrint / White（ファイル上は背面から）
    expected = ["ColorPrint", "CutLine"] if white == "none" else ["White", "ColorPrint", "CutLine"]
    assert list(ai.layers) == expected
    cut = ai.layers["CutLine"]
    assert "0 0 0 1 K" in cut and " k\n" not in cut  # K100 の線、塗りなし
    assert f" {stroke_pt:g} w " in cut
    assert "%AI5_BeginRaster" in ai.layers["ColorPrint"]
    assert " 8 4 0 0 0 0" in ai.layers["ColorPrint"]  # 8bit・4 チャンネル（CMYK）
    if white == "plate":
        plate = ai.layers["White"]
        assert plate.count("*u") == 1 and "0 0 0 1 k" in plate  # K100 の複合パス 1 つ
    elif white == "empty":
        assert _subpath_count(ai.layers["White"]) == 0


# --- テスト ---------------------------------------------------------------------


def test_check_available() -> None:
    check_available()


@pytest.mark.parametrize(("size", "mm"), [("50x50", 50), ("70x70", 70), ("100x100", 100)])
def test_acrylic_keychain(size: str, mm: int) -> None:
    out = _run("acrylic_keychain", f"{size}mm", _acrylic_inputs(base="round", keyhole=True))

    assert out.filename == f"md-1_AcrylicKeychain_color_{size}.ai"
    ai = _parse_ai8(out.content)
    assert ai.art_size == pytest.approx((mm * MM, mm * MM), abs=0.01)
    _assert_acrylic_structure(ai, stroke_pt=0.5, white="plate")
    assert _subpath_count(ai.layers["CutLine"]) == 2  # 外形とキー穴


def test_acrylic_keychain_without_white_plate() -> None:
    images = _acrylic_inputs(base="round", keyhole=True)
    del images["white"]
    out = _run("acrylic_keychain", "50x50mm", images)
    assert out.filename == "md-1_AcrylicKeychain_clear_50x50.ai"
    _assert_acrylic_structure(_parse_ai8(out.content), stroke_pt=0.5, white="none")


def test_white_plate_holes_under_semi_transparent_art_are_filled() -> None:
    """REQ-0067: 白版の、絵がある穴は埋まる（透明アクリルで透けない）."""
    images = _acrylic_inputs(base="round", keyhole=True, white_hole=True)
    out = _run("acrylic_keychain", "50x50mm", images)
    assert _subpath_count(_parse_ai8(out.content).layers["White"]) == 1  # 穴の無い外形だけ


@pytest.mark.parametrize(("size", "mm"), [("50mm", 50), ("70mm", 70), ("100mm", 100)])
@pytest.mark.parametrize("base", ["flat", "protruding"])
def test_acrylic_stand_merges_the_tab(size: str, mm: int, base: str) -> None:
    """ADR-0038: 絵柄が土台より下に出ていても、土台を延ばしてタブを付ける."""
    out = _run("acrylic_stand", f"{mm}x{mm}mm", _acrylic_inputs(base=base))

    assert out.filename == f"【md-1】アクリルフィギュアスタンド_{size}_本体.ai"
    ai = _parse_ai8(out.content)
    _assert_acrylic_structure(ai, stroke_pt=0.5, white="plate")
    # アートボードは台座テンプレートと同じ高さ（本体＋タブ）
    assert ai.art_size == pytest.approx((mm * MM, (mm + 5) * MM), abs=0.6)
    assert _subpath_count(ai.layers["CutLine"]) == 1  # タブを合成した 1 本のパス


def test_acrylic_stand_without_a_base_fails() -> None:
    """ADR-0038: 土台が見つからない入力は、タブの無いデータを作らずに失敗させる."""
    with pytest.raises(GenerationError, match="flat base edge not found"):
        _run("acrylic_stand", "70x70mm", _acrylic_inputs(base="none"))


@pytest.mark.parametrize("size", ["50x50", "70x70", "100x100"])
def test_sticker(size: str) -> None:
    images = _acrylic_inputs(base="round")
    del images["white"]
    out = _run("sticker", f"{size}mm", images)
    assert out.filename == f"md-1_Sticker_clear_{size}.ai"
    _assert_acrylic_structure(_parse_ai8(out.content), stroke_pt=1, white="empty")


@pytest.mark.parametrize(
    ("product_type", "size", "filename", "page_mm"),
    [
        ("tshirt", "M", "md-1_Tshirts_front_M_297x406.pdf", (297.0, 405.9)),
        ("tshirt", "XL", "md-1_Tshirts_front_XL_297x406.pdf", (297.0, 405.9)),
        ("tote_bag", "M", "【md-1】キャンバストート_M_280x250.pdf", (350.0, 405.9)),
    ],
)
def test_pdf_products(product_type: str, size: str, filename: str, page_mm: tuple[float, float]) -> None:
    design = _png(Image.new("RGBA", (PX, PX), (220, 60, 60, 255)))
    out = _run(product_type, size, {"design": design})

    assert out.filename == filename
    reader = PdfReader(io.BytesIO(out.content))
    page = reader.pages[0]
    assert (float(page.trimbox.width) / MM, float(page.trimbox.height) / MM) == pytest.approx(page_mm, abs=0.5)
    assert b"-32000" not in out.content  # VectorCraft の目印は取り除いてある
    # 製造委託先の指摘（2026-10-09）: プロファイル名は「sRGB IEC61966-2.1」
    assert _icc_descriptions(reader) == {"sRGB IEC61966-2.1"}


Matrix = tuple[float, float, float, float, float, float]
FIXTURES = Path(__file__).parent / "fixtures"
# 製造委託先が Illustrator で作ったワンポイント版のサンプル（L）。位置合わせの基準
LEFT_CHEST_SAMPLE = FIXTURES / "tshirt_left_chest_sample_L.pdf"


def _mul(a: Matrix, b: Matrix) -> Matrix:
    """a のあとに b を掛ける（PDF の cm と同じ向き）."""
    return (
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    )


def _image_boxes(
    stream: Any, resources: DictionaryObject, ctm: Matrix, out: list[tuple[float, float, float, float]]
) -> None:
    """コンテンツストリームを辿り、描かれた画像の (x, y, 幅, 高さ) をページ座標で集める."""
    stack: list[Matrix] = []
    m = ctm
    for operands, op in ContentStream(stream, None).operations:
        if op == b"q":
            stack.append(m)
        elif op == b"Q":
            m = stack.pop()
        elif op == b"cm":
            m = _mul(cast(Matrix, tuple(float(v) for v in operands)), m)
        elif op == b"Do":
            xobjects = cast(DictionaryObject, resources["/XObject"].get_object())
            xo = cast(DictionaryObject, xobjects[operands[0]].get_object())
            if xo.get("/Subtype") == "/Image":
                # 画像は単位正方形に描かれる
                pts = [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]) for x in (0, 1) for y in (0, 1)]
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                out.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
            elif xo.get("/Subtype") == "/Form":
                inner = m
                if "/Matrix" in xo:
                    inner = _mul(cast(Matrix, tuple(float(v) for v in cast(ArrayObject, xo["/Matrix"]))), m)
                res = cast(DictionaryObject, xo.get("/Resources", resources).get_object())
                _image_boxes(xo, res, inner, out)


def _placed_image(page: PageObject) -> tuple[float, float, float, float]:
    """ページに置かれた唯一の画像の (x, y, 幅, 高さ)。PDF 座標（左下原点・y 上向き）."""
    boxes: list[tuple[float, float, float, float]] = []
    _image_boxes(page.get_contents(), cast(DictionaryObject, page["/Resources"].get_object()), (1, 0, 0, 1, 0, 0), boxes)
    assert len(boxes) == 1, boxes
    return boxes[0]


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, w, h = box
    return (x + w / 2, y + h / 2)


def test_tshirt_left_chest_fits_the_top_right_100mm_square() -> None:
    """REQ-0070: 左胸はアートボード右上に接する 100×100mm の枠に、1mm の余白で中央に置く."""
    design = _png(Image.new("RGBA", (PX, PX), (220, 60, 60, 255)))
    out = _run("tshirt", "L", {"design": design}, position="左胸")

    assert out.filename == "md-1_Tshirts_front_L_297x406.pdf"  # ファイル名は正面と同じ
    reader = PdfReader(io.BytesIO(out.content))
    page = reader.pages[0]
    page_w, page_h = float(page.trimbox.width), float(page.trimbox.height)
    assert (page_w / MM, page_h / MM) == pytest.approx((297.0, 405.9), abs=0.5)
    assert _icc_descriptions(reader) == {"sRGB IEC61966-2.1"}

    placed = _placed_image(page)
    x, y, w, h = placed
    box = 100 * MM
    margin = 1 * MM
    # 正方形の画像なので 98×98mm に収まる
    assert (w / MM, h / MM) == pytest.approx((98.0, 98.0), abs=0.1)
    # 枠の中央 = ページ右端から 50mm、上端から 50mm
    assert _center(placed) == pytest.approx((page_w - box / 2, page_h - box / 2), abs=0.5)
    assert x + w <= page_w - margin + 0.1 and y + h <= page_h - margin + 0.1
    # 製造委託先のサンプル（Illustrator で手作業。余白なしで 100mm 角いっぱい）と中心が一致する
    sample = _placed_image(PdfReader(str(LEFT_CHEST_SAMPLE)).pages[0])
    assert _center(placed) == pytest.approx(_center(sample), abs=0.5)
    assert sample[3] / MM == pytest.approx(100.0, abs=0.1)


def test_tshirt_front_still_fills_the_artboard() -> None:
    design = _png(Image.new("RGBA", (PX, PX), (220, 60, 60, 255)))
    out = _run("tshirt", "L", {"design": design}, position="正面")
    page = PdfReader(io.BytesIO(out.content)).pages[0]
    x, y, w, h = _placed_image(page)
    assert w / MM == pytest.approx(295.0, abs=0.1)  # 297mm − 余白 1mm × 2
    assert x + w / 2 == pytest.approx(float(page.trimbox.width) / 2, abs=0.5)


def _icc_descriptions(reader: PdfReader) -> set[str]:
    descs = set()
    for page in reader.pages:
        stack = [cast(DictionaryObject, page["/Resources"].get_object())]
        while stack:
            res = stack.pop()
            for ref in res.get("/XObject", {}).values():
                obj = ref.get_object()
                if obj.get("/Subtype") == "/Image":
                    cs = obj["/ColorSpace"].get_object()
                    if cs[0] == "/ICCBased":
                        desc = icc_description(cs[1].get_object().get_data())
                        if desc:
                            descs.add(desc)
                elif "/Resources" in obj:
                    stack.append(obj["/Resources"].get_object())
    return descs
