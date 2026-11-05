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
from typing import cast

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader
from pypdf.generic import DictionaryObject

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
        if base == "legs":
            # 土台の左右に約 2.5mm（50mm のとき）のすき間を空けて、脚が土台と同じ高さの床に着く
            # （椅子やピアノの脚、#154）。土台の幅はどのサイズのタブも収まる 220px
            d.rectangle((190, 470, 410, 560), fill=fill)
            d.rectangle((125, 400, 160, 560), fill=fill)
            d.rectangle((440, 400, 475, 560), fill=fill)
        if keyhole:
            d.ellipse((290, 75, 310, 95), fill=(0, 0, 0, 0))  # キー穴（直径 ≈1.7mm）

    color = _layer(lambda d, f: _body(d, f, inset=12), fill=(40, 120, 200, 255))
    white = _layer(lambda d, f: _body(d, f, inset=18))
    if white_hole:
        # 白版の内側の穴。下の印刷画像は半透明（印刷される不透明度 50% 以上）の白（白い羽の模様など）
        ImageDraw.Draw(white).ellipse((280, 280, 320, 320), fill=(0, 0, 0, 0))
        ImageDraw.Draw(color).ellipse((280, 280, 320, 320), fill=(250, 250, 250, 200))
    return {"color": _png(color), "cutline": _png(_layer(cutline)), "white": _png(white)}


def _run(product_type: str, size: str, images: dict[str, bytes]) -> GeneratedFile:
    """ワーカーと同じ経路で生成する（pod-admin の商品属性 → 生成のパラメータ → 生成）."""
    spec = build_generation_spec(product_type, size, images.keys())
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


def _layer_body(layer: str) -> str:
    return layer.split("\n0 A\n", 1)[1]


def _is_clipped(layer: str) -> bool:
    """レイヤーの中身がクリッピングマスク（``q`` 〜 ``Q``）で始まり、それで終わるか."""
    body = _layer_body(layer)
    return body.startswith("q\n") and body.rstrip().endswith("Q\nLB")


def _clip_size(layer: str) -> tuple[float, float]:
    """レイヤーの先頭のクリッピングマスクの、マスクのパス（``q`` 〜 ``W n``）の幅と高さ（pt）."""
    body = _layer_body(layer)
    clip = body[: body.index("%AI5_BeginRaster")]
    clip = clip[: clip.rindex("W\nn\n")]
    pts: list[tuple[float, float]] = []
    for line in clip.splitlines():
        if not line.endswith((" m", " L", " C")):
            continue
        v = [float(n) for n in line.split()[:-1]]
        if line.endswith(" C"):
            # 曲線の上の点で測る（方向線は外へはみ出し、アンカーだけでは内側に寄る）
            (x0, y0), (x1, y1, x2, y2, x3, y3) = pts[-1], v
            for k in range(1, 17):
                t = k / 16
                a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t**3
                pts.append((a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3))
        else:
            pts.append((v[0], v[1]))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def _anchor_height(layer: str) -> float:
    """レイヤーのパスのアンカーの上下の幅（pt）."""
    ys = [float(line.split()[-2]) for line in layer.splitlines() if line.endswith((" m", " L", " C"))]
    return max(ys) - min(ys)


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
    # 入力の印刷画像は背景が透明。旧形式は透明を持てないので、絵の外形で切り抜く（#153）
    assert _is_clipped(ai.layers["ColorPrint"])
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


@pytest.mark.parametrize("mm", [50, 100])
def test_color_image_is_clipped_to_the_art(mm: int) -> None:
    """#153: 印刷画像の透明な背景は、絵の外形のクリッピングマスクで切り抜かれる.

    印刷画像の絵は 376×436px（600px 四方の中）の楕円。
    """
    out = _run("acrylic_keychain", f"{mm}x{mm}mm", _acrylic_inputs(base="round", keyhole=True))
    size = _clip_size(_parse_ai8(out.content).layers["ColorPrint"])
    art = (376 / PX * mm * MM, 436 / PX * mm * MM)
    assert size[0] == pytest.approx(art[0], abs=0.5 * MM)
    assert size[1] == pytest.approx(art[1], abs=0.5 * MM)


def test_small_pieces_of_art_are_not_clipped_out() -> None:
    """絵の小さな島（きらめき・点など）もマスクに入る。捨てると、その絵が印刷から消える.

    VectorCraft 0.4.0 のトレースは noise の値によらず小さな島を捨てない（1px 四方でも残る）。
    更新でトレースが島を捨てるようになったときに気づくためのテスト。
    """
    images = _acrylic_inputs(base="round", keyhole=True)
    with Image.open(io.BytesIO(images["color"])) as im:
        color = im.copy()
    ImageDraw.Draw(color).ellipse((40, 40, 43, 43), fill=(250, 200, 0, 255))  # 直径 4px（50mm で約 0.3mm）
    images["color"] = _png(color)
    out = _run("acrylic_keychain", "50x50mm", images)
    color_layer = _parse_ai8(out.content).layers["ColorPrint"]
    mask = color_layer[: color_layer.index("%AI5_BeginRaster")]
    assert mask.count("h\nW\nn") == 2  # 本体と小さな点


def test_opaque_color_image_is_not_clipped() -> None:
    """背景まで塗られた印刷画像（透明な画素が無い）は、切り抜かずにそのまま置く."""
    images = _acrylic_inputs(base="round", keyhole=True)
    images["color"] = _png(Image.new("RGBA", (PX, PX), (40, 120, 200, 255)))
    out = _run("acrylic_keychain", "50x50mm", images)
    color = _parse_ai8(out.content).layers["ColorPrint"]
    assert not _is_clipped(color) and "%AI5_BeginRaster" in color


def test_white_plate_holes_under_printed_art_are_filled() -> None:
    """REQ-0067: 白版の、印刷される絵がある穴は埋まる（透明アクリルで透けない）."""
    images = _acrylic_inputs(base="round", keyhole=True, white_hole=True)
    out = _run("acrylic_keychain", "50x50mm", images)
    assert _subpath_count(_parse_ai8(out.content).layers["White"]) == 1  # 穴の無い外形だけ


@pytest.mark.parametrize(("size", "mm"), [("50mm", 50), ("70mm", 70), ("100mm", 100)])
@pytest.mark.parametrize("base", ["flat", "protruding", "legs"])
def test_acrylic_stand_merges_the_tab(size: str, mm: int, base: str) -> None:
    """ADR-0038: 絵柄が土台より下に出ていても、土台を延ばしてタブを付ける.

    #154: 脚が土台と同じ高さで床に着いていても、本体の輪郭を失わない。
    """
    out = _run("acrylic_stand", f"{mm}x{mm}mm", _acrylic_inputs(base=base))

    assert out.filename == f"【md-1】アクリルフィギュアスタンド_{size}_本体.ai"
    ai = _parse_ai8(out.content)
    _assert_acrylic_structure(ai, stroke_pt=0.5, white="plate")
    # アートボードは台座テンプレートと同じ高さ（本体＋タブ）
    assert ai.art_size == pytest.approx((mm * MM, (mm + 5) * MM), abs=0.6)
    assert _subpath_count(ai.layers["CutLine"]) == 1  # タブを合成した 1 本のパス
    # カットラインは本体全体を囲む。入力の輪郭は画像の高さの 5/6（y=60〜560）で、下にタブ（3mm）が付く。
    # #154 では下端付近だけが残り、高さが 3 割ほどになった
    assert _anchor_height(ai.layers["CutLine"]) > 0.8 * mm * MM


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
