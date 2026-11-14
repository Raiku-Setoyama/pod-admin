"""DTF 用の製造データ（app/generator/dtf.py、#187）."""

from __future__ import annotations

import io
import struct
import zlib
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
from PIL import Image, ImageCms
from pypdf import PdfReader
from scipy import ndimage

from app.generator import dtf
from app.generator.dtf import PAD_PX, PX_PER_MM, DtfOptions, generate_dtf, make_white_plate
from app.generator.errors import GenerationError
from app.generator.pdf_finish import icc_description
from app.generator.products import ICC_SRGB, dtf_placement
from app.generator.runner import generate as run_generate
from app.utils.mfg_product_mapping import GenerationSpec

U8 = npt.NDArray[np.uint8]
Mask = npt.NDArray[np.bool_]

# 本番の元画像はすべて 1181px 四方
CANVAS = 1181


def _rgba(
    h: int = CANVAS, w: int = CANVAS, rgb: tuple[int, int, int] = (200, 40, 40), alpha: int = 255
) -> U8:
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., :3] = rgb
    out[..., 3] = alpha
    return out


def _png(rgba: U8, icc: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", icc_profile=icc)
    return buf.getvalue()


def _png16(arr: npt.NDArray[np.uint16], color_type: int) -> bytes:
    """16bit の PNG（Pillow は 16bit のカラーを書けないので自前で書く）."""
    h, w = arr.shape[:2]
    raw = b"".join(b"\0" + arr[y].astype(">u2").tobytes() for y in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", w, h, 16, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _page(pdf: bytes) -> tuple[Any, Any]:
    """（トレーラー, 1 ページ目）. pypdf の型は辞書の中身を辿れないので Any にする."""
    reader = PdfReader(io.BytesIO(pdf))
    return reader.trailer, reader.pages[0]


def _image(page: Any, name: str) -> U8:
    obj = page["/Resources"]["/XObject"][name].get_object()
    data = np.frombuffer(obj.get_data(), dtype=np.uint8)
    channels = data.size // (obj["/Width"] * obj["/Height"])
    shape = (obj["/Height"], obj["/Width"], channels) if channels > 1 else (obj["/Height"], -1)
    return data.reshape(shape)


# --- PDF の構成 -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def tshirt_pdf() -> bytes:
    """横長の絵柄（上下に透明な余白）。左上に真っ白の領域があり、混在になる."""
    rgba = _rgba()
    rgba[:300, :, 3] = 0
    rgba[-300:, :, 3] = 0
    rgba[300:500, 100:400, :3] = 255
    return generate_dtf(_png(rgba), "tshirt", "L", "1000001_Tshirts_front_L_297x406").pdf


def test_pdf_has_pdfx4_output_intent(tshirt_pdf: bytes) -> None:
    trailer, _ = _page(tshirt_pdf)
    root = trailer["/Root"]
    intent = root["/OutputIntents"][0].get_object()
    assert intent["/S"] == "/GTS_PDFX"
    assert intent["/OutputConditionIdentifier"] == "Japan Color 2001 Coated"
    profile = intent["/DestOutputProfile"].get_object()
    assert profile["/N"] == 4
    xmp = root["/Metadata"].get_object().get_data()
    assert b"<pdfxid:GTS_PDFXVersion>PDF/X-4</pdfxid:GTS_PDFXVersion>" in xmp
    assert trailer["/Info"]["/GTS_PDFXVersion"] == "PDF/X-4"
    assert tshirt_pdf.startswith(b"%PDF-1.6")


def test_pdf_has_two_spot_separations_with_the_same_plate(tshirt_pdf: bytes) -> None:
    _, page = _page(tshirt_pdf)
    xobj = page["/Resources"]["/XObject"]
    names = []
    for im in ("/Im0", "/Im1"):
        cs = xobj[im].get_object()["/ColorSpace"].get_object()
        assert cs[0] == "/Indexed"
        sep = cs[1].get_object()
        assert sep[0] == "/Separation"
        names.append(sep[1])
        # 表の並びは 255 → 0（画素値 0 ＝インキ 100%）
        assert cs[3].get_object().get_data() == bytes(range(255, -1, -1))
    assert names == ["/spot_1", "/spot_2"]
    spot1, spot2 = _image(page, "/Im0"), _image(page, "/Im1")
    assert np.array_equal(spot1, spot2)
    # 絵柄の中はインキ 100%（画素値 0）、ページの余白はインキ 0%（255）
    assert spot1[spot1.shape[0] // 2, spot1.shape[1] // 2] == 0
    assert spot1[0, 0] == 255
    content = page.get_contents().get_data()
    assert content.index(b"/Im0 Do") < content.index(b"/Im1 Do") < content.index(b"/Im2 Do")
    assert bool(page["/Resources"]["/ExtGState"]["/GS0"]["/op"])


def test_pdf_images_are_lossless(tshirt_pdf: bytes) -> None:
    _, page = _page(tshirt_pdf)
    for im in ("/Im0", "/Im1", "/Im2"):
        assert page["/Resources"]["/XObject"][im].get_object()["/Filter"] == "/FlateDecode"
    rgb = _image(page, "/Im2")
    assert rgb.shape[2] == 3
    # 白版の無い所（ページの余白）は白
    assert (rgb[:PAD_PX] == 255).all()
    assert tuple(rgb[rgb.shape[0] // 2, rgb.shape[1] // 2]) == (200, 40, 40)


def test_pdf_has_zero_size_srgb_rectangle(tshirt_pdf: bytes) -> None:
    _, page = _page(tshirt_pdf)
    content = page.get_contents().get_data()
    assert content.startswith(b"q /CS2 cs 1 1 1 sc 0 0 0 0 re f Q")
    cs2 = page["/Resources"]["/ColorSpace"]["/CS2"].get_object()
    assert cs2[0] == "/ICCBased"
    icc = cs2[1].get_object()
    assert icc["/N"] == 3
    assert icc_description(icc.get_data()) == "sRGB IEC61966-2.1"


def test_page_is_art_bounds_plus_1_5mm(tshirt_pdf: bytes) -> None:
    _, page = _page(tshirt_pdf)
    rgb = _image(page, "/Im2")
    h, w = rgb.shape[:2]
    assert float(page.mediabox.width) == pytest.approx(w * 72 / 300, abs=1e-3)
    assert float(page.mediabox.height) == pytest.approx(h * 72 / 300, abs=1e-3)
    # 外形はカラーの帯の縁（白版は混在の縮小で縁が 2px 内側にあるので、合成画像で見る）
    ink = np.argwhere((rgb < 255).any(axis=2))
    # 絵柄の外形のまわりに 1.5mm（18px）ちょうど
    assert ink.min(axis=0).tolist() == [PAD_PX, PAD_PX]
    assert (np.array([h, w]) - ink.max(axis=0) - 1).tolist() == [PAD_PX, PAD_PX]


def test_japanese_title_is_written_as_unicode() -> None:
    result = generate_dtf(_png(_rgba(64, 64)), "tote_bag", "M", "【1000001】キャンバストート_M")
    trailer, _ = _page(result.pdf)
    assert trailer["/Info"]["/Title"] == "【1000001】キャンバストート_M"
    xmp = trailer["/Root"]["/Metadata"].get_object().get_data().decode()
    assert "【1000001】キャンバストート_M" in xmp


# --- 大きさ・印刷位置・解像度 -------------------------------------------------------------


@pytest.mark.parametrize(
    ("product_type", "size", "top_mm"),
    [
        ("tshirt", "S", 115.5),
        ("tshirt", "M", 115.5),
        ("tshirt", "L", 135.5),
        ("tshirt", "XL", 135.5),
        ("tote_bag", "M", 41.0),
    ],
)
def test_square_art_position_and_size(product_type: str, size: str, top_mm: float) -> None:
    """正方形・透明の余白なしの絵柄: 枠の上端＝標準位置。上下中央に置く."""
    result = generate_dtf(_png(_rgba()), product_type, size, "t")
    side = 295.0 if product_type == "tshirt" else 248.0
    assert result.art_top_below_rib_mm == pytest.approx(top_mm, abs=0.05)
    assert result.art_width_mm == pytest.approx(side, abs=0.1)
    assert result.art_height_mm == pytest.approx(side, abs=0.1)
    assert result.white_plate == "color_only"


@pytest.mark.parametrize(("product_type", "dpi"), [("tshirt", 101.7), ("tote_bag", 121.0)])
def test_source_dpi(product_type: str, dpi: float) -> None:
    size = "XL" if product_type == "tshirt" else "M"
    result = generate_dtf(_png(_rgba()), product_type, size, "t")
    assert result.source_dpi == pytest.approx(dpi, abs=0.05)


def test_wide_art_is_lowered_by_the_transparent_margin() -> None:
    """上下に 12.5% ずつ透明な余白がある横長の絵柄。プレビューと同じく余白の分だけ下がる."""
    canvas = 1184  # 12.5% がちょうど 148px
    rgba = _rgba(canvas, canvas)
    rgba[:148, :, 3] = 0
    rgba[-148:, :, 3] = 0
    result = generate_dtf(_png(rgba), "tshirt", "XL", "t")
    # 80 + 55.5 + 295 × 12.5%。拡大で縁が 0.1mm ほど広がる
    assert result.art_top_below_rib_mm == pytest.approx(172.4, abs=0.2)
    assert result.art_width_mm == pytest.approx(295.0, abs=0.1)
    assert result.art_height_mm == pytest.approx(295 * 0.75, abs=0.3)


def test_tall_art_fits_the_frame_height() -> None:
    """縦長は枠の高さ（406 − 2mm）で決まり、左右中央."""
    result = generate_dtf(_png(_rgba(1200, 600)), "tshirt", "M", "t")
    assert result.art_height_mm == pytest.approx(404.0, abs=0.1)
    assert result.art_width_mm == pytest.approx(202.0, abs=0.1)
    assert result.art_top_below_rib_mm == pytest.approx(61.0, abs=0.05)
    assert result.source_dpi == pytest.approx(1200 / (404 / 25.4), abs=0.05)


@pytest.mark.parametrize("canvas", [400, 4000])
def test_output_is_300dpi_for_low_and_high_resolution(canvas: int) -> None:
    """低解像度は拡大、高解像度は縮小して、置く大きさで 300dpi にする."""
    result = generate_dtf(_png(_rgba(canvas, canvas)), "tote_bag", "M", "t")
    _, page = _page(result.pdf)
    plate = _image(page, "/Im0")
    expected = round(248 * PX_PER_MM) + 2 * PAD_PX
    assert plate.shape == (expected, expected)


def test_single_pixel_dot() -> None:
    rgba = _rgba(alpha=0)
    rgba[590, 590, 3] = 255
    result = generate_dtf(_png(rgba), "tshirt", "M", "t")
    assert 0 < result.art_width_mm < 1.0
    _, page = _page(result.pdf)
    assert _image(page, "/Im0").shape[0] < 2 * PAD_PX + 12


def test_fully_transparent_image_is_rejected() -> None:
    with pytest.raises(GenerationError, match="no opaque"):
        generate_dtf(_png(_rgba(alpha=0)), "tshirt", "M", "t")


def test_unsupported_size_is_rejected() -> None:
    with pytest.raises(GenerationError):
        dtf_placement("tote_bag", "L")
    with pytest.raises(GenerationError):
        dtf_placement("sticker", "M")


# --- 白版 -----------------------------------------------------------------------------


def _layout() -> tuple[U8, Mask]:
    """透明の中に、左がホワイト（真っ白）・右がカラーの帯（300dpi）."""
    a8 = np.zeros((100, 200), dtype=np.uint8)
    a8[20:80, 20:180] = 255
    white = np.zeros_like(a8, dtype=np.bool_)
    white[20:80, 20:100] = True
    return a8, white


def test_mixed_chokes_only_color_edges_next_to_transparency() -> None:
    a8, white = _layout()
    plate, kind = make_white_plate(a8, white, DtfOptions())
    assert kind == "mixed"
    # 0.15mm ≈ 1.77px → 2px
    color = (a8 > 0) & ~white
    # カラーの、透明に接する縁（上・下・右）は 2px 縮む
    assert (plate[20:22, 100:180] == 0).all()
    assert (plate[78:80, 100:180] == 0).all()
    assert (plate[20:80, 178:180] == 0).all()
    assert (plate[22:78, 100:178] == 255).all()
    # カラーとホワイトの境目（x=100）は縮まない
    assert (plate[22:78, 100] == 255).all()
    # ホワイト部分は透明に接していても縮まない
    assert (plate[white] == 255).all()
    # 透明な所は 0 のまま、カラー部分は元より増えない
    assert (plate[a8 == 0] == 0).all()
    assert (plate[color] <= a8[color]).all()


def test_choke_does_not_pass_through_a_thin_white_outline() -> None:
    """カラーを 1px のホワイトの縁取りが囲むとき、縁取りの内側のカラーに白版の無い筋を作らない."""
    a8 = np.zeros((60, 60), dtype=np.uint8)
    a8[10:50, 10:50] = 255
    white = np.zeros_like(a8, dtype=np.bool_)
    white[10:50, 10:50] = True
    white[11:49, 11:49] = False
    # 縁取りは混在の判定で無視されない大きさにする（周の長さで 156px）
    plate, kind = make_white_plate(a8, white, DtfOptions(ignore_white_area_mm2=0.5))
    assert kind == "mixed"
    assert (plate[10:50, 10:50] == 255).all()


def test_color_only_and_white_only_are_not_choked() -> None:
    a8, _ = _layout()
    plate, kind = make_white_plate(a8, np.zeros_like(a8, dtype=np.bool_), DtfOptions())
    assert kind == "color_only"
    assert np.array_equal(plate, a8)
    plate, kind = make_white_plate(a8, a8 > 0, DtfOptions())
    assert kind == "white_only"
    assert np.array_equal(plate, a8)


def test_semi_transparent_white_is_white() -> None:
    """不透明度に関係なく、色が真っ白ならホワイト部分（白版＝不透明度）."""
    rgba = _rgba(64, 64, rgb=(255, 255, 255), alpha=128)
    result = generate_dtf(_png(rgba), "tote_bag", "M", "t")
    assert result.white_plate == "white_only"
    _, page = _page(result.pdf)
    plate = _image(page, "/Im0")
    assert plate[plate.shape[0] // 2, plate.shape[1] // 2] == 255 - 128


def test_mostly_white_image_with_color_is_mixed() -> None:
    rgba = _rgba(rgb=(255, 255, 255))
    rgba[500:700, 500:700, :3] = (10, 120, 200)
    rgba[:100, :, 3] = 0
    result = generate_dtf(_png(rgba), "tshirt", "M", "t")
    assert result.white_plate == "mixed"


def test_white_min_rgb_setting() -> None:
    """「真っ白」の下限を下げると、ほぼ白もホワイト部分になる."""
    rgba = _rgba(256, 256, rgb=(250, 250, 250))
    rgba[100:150, 100:150, :3] = (10, 120, 200)
    assert generate_dtf(_png(rgba), "tote_bag", "M", "t").white_plate == "color_only"
    opts = DtfOptions(white_min_rgb=250)
    assert generate_dtf(_png(rgba), "tote_bag", "M", "t", opts).white_plate == "mixed"


def _speck(area_px: int, diagonal: bool = False) -> tuple[U8, Mask]:
    """カラーの中に、真っ白の連結領域 1 つ（``area_px`` 画素）."""
    a8 = np.full((80, 80), 255, dtype=np.uint8)
    white = np.zeros_like(a8, dtype=np.bool_)
    if diagonal:
        # 半分ずつの 2 つの塊が、角だけで（斜めに）つながる
        half = area_px // 2
        white[10:20, 10 : 10 + half // 10] = True
        x = 10 + half // 10
        white[20:30, x : x + half // 10] = True
    else:
        rows, rest = divmod(area_px, 10)
        white[10 : 10 + rows, 10:20] = True
        white[10 + rows, 10 : 10 + rest] = True
    assert white.sum() == area_px
    return a8, white


# 連結領域がちょうど 100px になる設定
_100PX = DtfOptions(ignore_white_area_mm2=100 / PX_PER_MM**2)


@pytest.mark.parametrize(("area", "kind"), [(99, "color_only"), (100, "mixed"), (101, "mixed")])
def test_white_speck_threshold(area: int, kind: str) -> None:
    """閾値未満の真っ白の連結領域は無視する（ちょうどは無視しない）."""
    a8, white = _speck(area)
    assert make_white_plate(a8, white, _100PX)[1] == kind


def test_diagonal_neighbors_are_connected() -> None:
    """斜めにつながる真っ白も 1 つの連結領域として数える（8 近傍）."""
    a8, white = _speck(100, diagonal=True)
    _, n = ndimage.label(white)
    assert n == 2  # 4 近傍では 50px ずつの 2 つ
    assert make_white_plate(a8, white, _100PX)[1] == "mixed"


def test_small_white_specks_are_ignored_by_default() -> None:
    """1mm 四方（約 140px）未満の白い点だけのカラーの絵柄は「カラーのみ」。設定で判定が変わる."""
    rgba = _rgba()
    # トートでは元画像の 1px ＝ 0.21mm。3px 四方 ≈ 0.4mm²、2×4px ≈ 0.35mm²
    rgba[100:103, 100:103, :3] = 255
    rgba[900:902, 200:204, :3] = 255
    png = _png(rgba)
    assert generate_dtf(png, "tote_bag", "M", "t").white_plate == "color_only"
    small = DtfOptions(ignore_white_area_mm2=0.05)
    result = generate_dtf(png, "tote_bag", "M", "t", small)
    assert result.white_plate == "mixed"


# --- 入力 -----------------------------------------------------------------------------


def _with_profile(
    src: bytes, description: str, colorants: dict[bytes, tuple[float, float, float]]
) -> bytes:
    """ICC v2 の sRGB プロファイルの、説明名と原色だけを書き換える."""
    data = bytearray(src)
    count = struct.unpack(">I", data[128:132])[0]
    for i in range(count):
        sig, off, _ = struct.unpack(">4sII", data[132 + 12 * i : 144 + 12 * i])
        if sig in colorants:
            xyz = b"".join(struct.pack(">i", round(v * 65536)) for v in colorants[sig])
            data[off + 8 : off + 20] = xyz
        if sig == b"desc":
            n = struct.unpack(">I", data[off + 8 : off + 12])[0]
            name = description.encode().ljust(n - 1, b" ") + b"\0"
            data[off + 12 : off + 12 + n] = name[:n]
    return bytes(data)


# Display P3 の原色（D50 に順応させた値。Apple の Display P3 プロファイルと同じ）
_P3 = {
    b"rXYZ": (0.515102, 0.241182, -0.001050),
    b"gXYZ": (0.291965, 0.692236, 0.041882),
    b"bXYZ": (0.157153, 0.066574, 0.784073),
}


def _srgb_decode(v: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    out: npt.NDArray[np.float64] = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    return out


def _srgb_encode(v: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    v = np.clip(v, 0, 1)
    out: npt.NDArray[np.float64] = np.where(
        v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055
    )
    return out


def test_display_p3_is_converted_to_srgb() -> None:
    icc = _with_profile(ICC_SRGB.read_bytes(), "Display P3 (test)", _P3)
    assert ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).startswith(
        "Display P3"
    )
    p3 = np.array([200, 120, 80], dtype=np.float64)
    rgba = _rgba(8, 8, rgb=(200, 120, 80), alpha=255)
    rgba[0, 0, 3] = 100
    out = dtf._load_srgb_rgba(_png(rgba, icc), 10**6)
    # P3（D65）→ sRGB（D65）の線形の行列
    m = np.array(
        [
            [1.2249, -0.2247, 0.0],
            [-0.0420, 1.0419, 0.0],
            [-0.0197, -0.0786, 1.0979],
        ]
    )
    expected = _srgb_encode(m @ _srgb_decode(p3 / 255)) * 255
    assert np.abs(out[4, 4, :3].astype(float) - expected).max() <= 2
    assert np.abs(out[4, 4, :3].astype(float) - p3).max() >= 8  # 変換されている
    assert out[0, 0, 3] == 100  # 不透明度はそのまま


def test_srgb_and_untagged_are_unchanged() -> None:
    rgba = _rgba(8, 8, rgb=(200, 120, 80), alpha=77)
    for icc in (None, ICC_SRGB.read_bytes()):
        out = dtf._load_srgb_rgba(_png(rgba, icc), 10**6)
        assert np.array_equal(out, rgba)


def test_16bit_rgba_and_gray_become_8bit() -> None:
    rgba16 = np.zeros((4, 4, 4), dtype=np.uint16)
    rgba16[..., 0] = 0x8080
    rgba16[..., 3] = 0xFFFF
    rgba16[0, 0, 3] = 0x8000
    out = dtf._load_srgb_rgba(_png16(rgba16, 6), 10**6)
    assert out[1, 1].tolist() == [128, 0, 0, 255]
    assert out[0, 0, 3] == 128

    gray16 = np.full((4, 4), 0x8000, dtype=np.uint16)
    out = dtf._load_srgb_rgba(_png16(gray16, 0), 10**6)
    assert out[0, 0].tolist() == [128, 128, 128, 255]


def test_palette_and_grayscale_with_alpha() -> None:
    rgba = _rgba(8, 8, rgb=(10, 200, 30), alpha=255)
    rgba[:4, :, 3] = 0
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").quantize(colors=4).save(buf, format="PNG")
    out = dtf._load_srgb_rgba(buf.getvalue(), 10**6)
    assert out[6, 6].tolist() == [10, 200, 30, 255]
    assert out[0, 0, 3] == 0

    buf = io.BytesIO()
    la = np.dstack([np.full((8, 8), 90, np.uint8), np.full((8, 8), 60, np.uint8)])
    Image.fromarray(la, "LA").save(buf, format="PNG")
    assert dtf._load_srgb_rgba(buf.getvalue(), 10**6)[0, 0].tolist() == [90, 90, 90, 60]


def test_too_many_pixels_is_rejected() -> None:
    with pytest.raises(GenerationError, match="too large"):
        generate_dtf(_png(_rgba(100, 100)), "tshirt", "M", "t", DtfOptions(max_source_pixels=9999))


def test_decompression_bomb_warning_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 5000)
    with pytest.raises(GenerationError, match="too large"):
        dtf._load_srgb_rgba(_png(_rgba(80, 80)), 10**6)


def test_unreadable_image_is_rejected() -> None:
    with pytest.raises(GenerationError, match="cannot read"):
        generate_dtf(b"not an image", "tshirt", "M", "t")


# --- 組み込み -------------------------------------------------------------------------


def _spec(product_type: str, size: str, variant: str | None) -> GenerationSpec:
    return GenerationSpec(product_type, size, variant, required_layers=("design",))


@pytest.mark.parametrize(
    ("product_type", "size", "filename"),
    [
        ("tshirt", "S", "1000001_Tshirts_front_S_297x406.pdf"),
        ("tshirt", "M", "1000001_Tshirts_front_M_297x406.pdf"),
        ("tshirt", "L", "1000001_Tshirts_front_L_297x406.pdf"),
        ("tshirt", "XL", "1000001_Tshirts_front_XL_297x406.pdf"),
        ("tote_bag", "M", "【1000001】キャンバストート_M_280x250.pdf"),
    ],
)
def test_runner_generates_dtf_without_vectorcraft(
    product_type: str, size: str, filename: str
) -> None:
    """DTF 版は VectorCraft を起動しない（存在しない実行ファイルを渡しても作れる）."""
    rgba = _rgba(300, 300)
    rgba[:30, :, 3] = 0
    rgba[100:200, 100:200, :3] = 255
    out = run_generate(
        _spec(product_type, size, "dtf"),
        {"design": _png(rgba)},
        "1000001",
        cli="/nonexistent/vectorcraft-cli",
        timeout_seconds=1,
    )
    assert out.filename == filename
    assert out.content.startswith(b"%PDF-1.6")
    assert out.white_plate == "mixed"
    assert out.source_dpi is not None and out.source_dpi < 40
    assert out.art_width_mm is not None and out.art_height_mm is not None
    assert out.art_top_below_rib_mm is not None


def test_runner_passes_dtf_options() -> None:
    rgba = _rgba(300, 300)
    rgba[100:200, 100:200, :3] = 255
    out = run_generate(
        _spec("tote_bag", "M", "dtf"),
        {"design": _png(rgba)},
        "1",
        cli="/nonexistent/vectorcraft-cli",
        timeout_seconds=1,
        dtf_options=DtfOptions(ignore_white_area_mm2=10**6),
    )
    assert out.white_plate == "color_only"


def test_entry_point_uses_dtf_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """入口の ``app.generator.generate`` は設定（GENERATOR_DTF_*）を DTF の生成に渡す."""
    from app import generator
    from app.config import settings

    rgba = _rgba(300, 300)
    rgba[100:200, 100:200, :3] = 255
    images = {"design": _png(rgba)}
    spec = _spec("tote_bag", "M", "dtf")
    assert generator.generate(spec, images, "1").white_plate == "mixed"
    monkeypatch.setattr(settings, "GENERATOR_DTF_IGNORE_WHITE_AREA_MM2", 10.0**6)
    assert generator.generate(spec, images, "1").white_plate == "color_only"
    monkeypatch.setattr(settings, "GENERATOR_DTF_MAX_SOURCE_PIXELS", 1000)
    with pytest.raises(GenerationError, match="too large"):
        generator.generate(spec, images, "1")
