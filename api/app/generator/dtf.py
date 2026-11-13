"""DTF 用の製造データ（T シャツ・トート。#187 / 親 #191）.

T シャツ・トートの DTF 印刷では、メーカーの資料「DTF印刷用データ」の Photoshop 手順で作るデータと
同じ構成の PDF/X-4 を渡す。VectorCraft は使わず、元画像から numpy・Pillow だけで作る
（ユーザーの手元の試作 ``DTF_試作_20261102/tools/dtf_lib.py`` の移植。PSD の書き出しは不要なので持たない）。

- 大きさと配置はインクジェットのときと同じ: 元画像のキャンバス全体を枠に余白 1mm で縦横比を保って収め、
  上下左右中央に置く（``products.dtf_placement``）。そのうえで、置く大きさで 300dpi にする
- ページ＝絵柄の外形（不透明度 > 0 の範囲）＋上下左右 1.5mm（メーカーの面付け・端切れ防止のため必須）
- 中身は画像 3 枚: 白版 2 枚（特色 ``spot_1`` 表示色 C100%・``spot_2`` 表示色 M100%。中身は同じで、
  画素値 0＝インキ 100%）と、白地に合成した絵柄の RGB（sRGB IEC61966-2.1、可逆圧縮）
- 出力インテントは Japan Color 2001 Coated

白版は絵柄の不透明度そのもの。カラー部分とホワイト部分（真っ白の部分）が混在するときだけ、
カラー部分のうち透明な所（生地）に接する縁を ``choke_mm`` 縮める（当社方針。#187）。

ワーカーは 1 CPU・1GiB なので、拡大縮小は帯ごとに行い、大きな浮動小数の配列を持たない。
"""

from __future__ import annotations

import functools
import io
import logging
import math
import uuid
import warnings
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from xml.sax.saxutils import escape

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageCms
from scipy import ndimage

from app.generator.errors import GenerationError
from app.generator.products import (
    DTF_IMAGE_MARGIN_MM,
    ICC_JAPAN_COLOR_2001_COATED,
    ICC_SRGB,
    dtf_placement,
)

logger = logging.getLogger(__name__)

DPI = 300
PX_PER_MM = DPI / 25.4
# ページの、絵柄の外形の外側の余白
PAD_MM = 1.5
PAD_PX = round(PAD_MM * PX_PER_MM)  # 18px
# 拡大縮小を一度に行う出力の行数（メモリを抑えるため）
_BAND_ROWS = 256
# Pillow の BICUBIC の台の半径（出力 1 画素あたり、元画像の画素数。縮小ではこれに倍率を掛ける）
_BICUBIC_SUPPORT = 2.0

WhitePlateKind = Literal["color_only", "white_only", "mixed"]

U8 = npt.NDArray[np.uint8]
F32 = npt.NDArray[np.float32]
Mask = npt.NDArray[np.bool_]


@dataclass(frozen=True)
class DtfOptions:
    """DTF の生成の設定値."""

    # 「真っ白」とみなす RGB の下限（3 つとも、この値以上）
    white_min_rgb: int = 255
    # 混在かどうかの判定で無視する、真っ白の連結領域の大きさ（これ未満を無視し、カラー部分として扱う）
    ignore_white_area_mm2: float = 1.0
    # 混在のとき、カラー部分のうち透明な所に接する縁を縮める量
    choke_mm: float = 0.15
    # 元画像の画素数の上限（超えたら作らない）
    max_source_pixels: int = 25_000_000


@dataclass(frozen=True)
class DtfResult:
    """DTF の製造データと、記録用の数値."""

    pdf: bytes
    # 元画像の実寸解像度（元の画素数 ÷ 置く大きさ）
    source_dpi: float
    # 絵柄の外形の大きさ（ページの 1.5mm の余白を含まない）
    art_width_mm: float
    art_height_mm: float
    # リブ下から絵柄の最上部まで
    art_top_below_rib_mm: float
    white_plate: WhitePlateKind


def generate_dtf(
    image: bytes,
    product_type: str,
    size: str,
    title: str,
    options: DtfOptions | None = None,
) -> DtfResult:
    """元画像から DTF の製造データ（PDF/X-4）を作る.

    Args:
        image: 元画像（PNG など Pillow が読める形式）。
        product_type: ``tshirt`` / ``tote_bag``。
        size: 生成のサイズ（``app.utils.mfg_product_mapping`` が正規化したもの）。
        title: PDF の文書タイトル（ファイル名など）。
        options: 設定値。省略時は既定値。

    Raises:
        GenerationError: この入力からは作れない（読めない・大きすぎる・絵柄が無い・未対応のサイズ）。
    """
    opts = options or DtfOptions()
    place = dtf_placement(product_type, size)
    rgba = _load_srgb_rgba(image, opts.max_source_pixels)
    h0, w0 = rgba.shape[:2]

    # 元画像のキャンバス全体を、枠に余白 1mm で縦横比を保って収める（インクジェットと同じ）
    mm_per_src_px = min(
        (place.width_mm - 2 * DTF_IMAGE_MARGIN_MM) / w0,
        (place.height_mm - 2 * DTF_IMAGE_MARGIN_MM) / h0,
    )
    placed_w_mm, placed_h_mm = w0 * mm_per_src_px, h0 * mm_per_src_px
    out_w = max(1, round(placed_w_mm * PX_PER_MM))
    out_h = max(1, round(placed_h_mm * PX_PER_MM))
    canvas_top_below_rib = place.top_below_rib_mm + (place.height_mm - placed_h_mm) / 2

    comp, a8, white = _resample(rgba, out_w, out_h, opts.white_min_rgb)
    del rgba
    art = _bbox(a8)
    if art is None:
        raise GenerationError("the image has no opaque pixels")
    top, left, bottom, right = art
    # 1 つずつ切り抜いて元を捨てる（最大サイズでは合計 80MB ほどあり、全部を重ねて持たない）
    comp = _crop_pad(comp, art, 255)
    a8 = _crop_pad(a8, art, 0)
    white = _crop_pad(white, art, False)
    plate, kind = make_white_plate(a8, white, opts)
    del white, a8
    pdf = pdf_bytes(
        comp, plate, title, ICC_SRGB.read_bytes(), ICC_JAPAN_COLOR_2001_COATED.read_bytes()
    )
    result = DtfResult(
        pdf=pdf,
        source_dpi=25.4 / mm_per_src_px,
        art_width_mm=(right - left) / PX_PER_MM,
        art_height_mm=(bottom - top) / PX_PER_MM,
        art_top_below_rib_mm=canvas_top_below_rib + top / PX_PER_MM,
        white_plate=kind,
    )
    logger.info(
        "dtf generated: %dx%dpx source=%.1fdpi art=%.1fx%.1fmm top=%.1fmm white=%s",
        comp.shape[1],
        comp.shape[0],
        result.source_dpi,
        result.art_width_mm,
        result.art_height_mm,
        result.art_top_below_rib_mm,
        kind,
    )
    return result


# --- 入力 ---------------------------------------------------------------------------


def _load_srgb_rgba(data: bytes, max_pixels: int) -> U8:
    """元画像を読み、sRGB の RGBA 8bit（乗算前）にする.

    埋め込みのプロファイルは sRGB に変換する（タグなしは sRGB とみなす）。16bit・パレット・
    グレースケール・CMYK も RGBA 8bit にそろえる。
    """
    with warnings.catch_warnings():
        # 解凍爆弾の警告も例外にする（上限は自前で確かめるが、Pillow の判定も素通りさせない）
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            im: Image.Image = Image.open(io.BytesIO(data))
            if im.width * im.height > max_pixels:
                raise GenerationError(
                    f"source image is too large: {im.width}x{im.height}px (max {max_pixels}px)"
                )
            im.load()
        except GenerationError:
            raise
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise GenerationError(f"source image is too large: {exc}") from exc
        except (OSError, ValueError, SyntaxError) as exc:
            raise GenerationError(f"cannot read the source image: {exc}") from exc

    icc = im.info.get("icc_profile")
    if im.mode in ("I", "I;16", "I;16B", "I;16L", "I;16N"):
        # 16bit のグレースケール。Pillow の convert("L") は 255 で頭打ちになるので自前で 8bit にする
        wide = np.asarray(im, dtype=np.int64)
        im = Image.fromarray(((np.clip(wide, 0, 65535) * 255 + 32767) // 65535).astype(np.uint8))
        del wide
    elif im.mode not in ("1", "L", "LA", "La", "P", "PA", "RGB", "RGBA", "RGBa", "RGBX", "CMYK"):
        raise GenerationError(f"unsupported image mode: {im.mode}")
    if "transparency" in im.info and im.mode == "L":
        im = im.convert("LA")

    src = _embedded_profile(icc, im.mode)
    if im.mode == "CMYK" or (im.mode in ("L", "LA", "La") and src is not None):
        # 色の成分の数が変わる変換（CMYK・グレー → RGB）。不透明度は分けておいて戻す
        alpha = im.getchannel("A") if im.mode in ("LA", "La") else None
        base = im.getchannel("L") if alpha is not None else im
        rgb = _cms(base, src, "RGB") if src is not None else base.convert("RGB")
        del im, base
        rgb.putalpha(alpha if alpha is not None else 255)
        im = rgb
    else:
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        if src is not None:
            # RGB のプロファイル。不透明度はそのまま残る（ImageCms は余分なチャンネルを写す）
            ImageCms.profileToProfile(
                im,
                src,
                _srgb_profile(),
                renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                inPlace=True,
            )
    out: U8 = np.asarray(im)
    return out


# 画像のモード → ICC の色空間
_MODE_SPACE = {
    **dict.fromkeys(("RGB", "RGBA", "RGBa", "RGBX", "P", "PA"), "RGB"),
    **dict.fromkeys(("L", "LA", "La"), "GRAY"),
    "CMYK": "CMYK",
}


@functools.cache
def _srgb_profile() -> ImageCms.ImageCmsProfile:
    return ImageCms.ImageCmsProfile(str(ICC_SRGB))


def _embedded_profile(icc: bytes | None, mode: str) -> ImageCms.ImageCmsProfile | None:
    """sRGB への変換が必要な埋め込みのプロファイル. 無い・sRGB・画像と合わないときは None.

    画像の色空間と合わないプロファイル（グレーの画像に RGB のプロファイルなど）は読めないので、
    タグなしと同じく sRGB とみなす。
    """
    if not icc:
        return None
    try:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
    except (OSError, ImageCms.PyCMSError) as exc:
        raise GenerationError(f"cannot read the embedded ICC profile: {exc}") from exc
    space = src.profile.xcolor_space.strip()
    if _MODE_SPACE.get(mode) != space:
        logger.warning(
            "ignoring an ICC profile (%s) that does not match the image (%s)", space, mode
        )
        return None
    if ImageCms.getProfileDescription(src).strip() == "sRGB IEC61966-2.1":
        return None
    return src


def _cms(im: Image.Image, src: ImageCms.ImageCmsProfile, mode: str) -> Image.Image:
    out = ImageCms.profileToProfile(
        im,
        src,
        _srgb_profile(),
        renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
        outputMode=mode,
    )
    assert out is not None  # inPlace=False のときは必ず返る
    return out


# --- 拡大縮小 -----------------------------------------------------------------------


def _resize(ch: F32, size: tuple[int, int], box: tuple[float, float, float, float]) -> F32:
    im = Image.fromarray(ch, "F").resize(size, Image.Resampling.BICUBIC, box=box)
    return np.asarray(im, dtype=np.float32)


def _resample(rgba: U8, out_w: int, out_h: int, white_min_rgb: int) -> tuple[U8, U8, Mask]:
    """RGBA を ``out_w`` × ``out_h`` にし、白地に合成した RGB・不透明度・真っ白の範囲を返す.

    拡大縮小は乗算済みの色で行う（透明な所の色が縁に混ざらない）。白地への合成も線形なので、
    合成してから拡大縮小するのと同じ結果になる。

    メモリを抑えるため、出力を ``_BAND_ROWS`` 行ずつに分け、それぞれに必要な元画像の行だけを
    浮動小数にする。Pillow の拡大縮小は、``box`` の外でも画像の中なら台の範囲の画素を使うので、
    台の半径より広く元画像を切り出しておけば、全体を一度に拡大縮小するのと同じ結果になる。
    """
    h0, w0 = rgba.shape[:2]
    sy = h0 / out_h
    margin = math.ceil(_BICUBIC_SUPPORT * max(sy, 1.0)) + 2
    comp = np.empty((out_h, out_w, 3), dtype=np.uint8)
    a8 = np.empty((out_h, out_w), dtype=np.uint8)
    white = np.empty((out_h, out_w), dtype=np.bool_)
    # straight の色 × 255 を四捨五入して white_min_rgb 以上（乗算済みの値 pm と不透明度 a で比べる）
    white_ratio = np.float32((white_min_rgb - 0.5) / 255)
    for y0 in range(0, out_h, _BAND_ROWS):
        y1 = min(out_h, y0 + _BAND_ROWS)
        top, bottom = y0 * sy, y1 * sy
        r0 = max(0, math.floor(top) - margin)
        r1 = min(h0, math.ceil(bottom) + margin)
        src = rgba[r0:r1]
        box = (0.0, top - r0, float(w0), bottom - r0)
        size = (out_w, y1 - y0)
        src_a = src[..., 3].astype(np.float32) / np.float32(255)
        a = np.clip(_resize(src_a, size, box), 0.0, 1.0)
        a8[y0:y1] = np.rint(a * 255)
        band_white = a8[y0:y1] > 0
        for c in range(3):
            pm = _resize(src[..., c].astype(np.float32) / np.float32(255) * src_a, size, box)
            pm = np.clip(pm, 0.0, a)
            comp[y0:y1, :, c] = np.rint((pm + (1.0 - a)) * 255)
            band_white &= pm >= white_ratio * a
        white[y0:y1] = band_white
    comp[a8 == 0] = 255
    return comp, a8, white


def _bbox(a8: U8) -> tuple[int, int, int, int] | None:
    """不透明度 > 0 の範囲 (top, left, bottom, right). 無ければ None."""
    rows = np.flatnonzero(a8.any(axis=1))
    if rows.size == 0:
        return None
    cols = np.flatnonzero(a8.any(axis=0))
    return int(rows[0]), int(cols[0]), int(rows[-1]) + 1, int(cols[-1]) + 1


def _crop_pad[T: np.generic](
    x: npt.NDArray[T], art: tuple[int, int, int, int], fill: int | bool
) -> npt.NDArray[T]:
    """絵柄の外形で切り抜き、上下左右に ``PAD_PX`` の余白を付ける."""
    t, left, b, r = art
    p = PAD_PX
    out = np.full((b - t + 2 * p, r - left + 2 * p, *x.shape[2:]), fill, dtype=x.dtype)
    out[p : p + b - t, p : p + r - left] = x[t:b, left:r]
    return out


# --- 白版 ---------------------------------------------------------------------------


def make_white_plate(a8: U8, white: Mask, opts: DtfOptions) -> tuple[U8, WhitePlateKind]:
    """白版のインキ量（255＝100%）と、白版の種類を返す.

    白版＝不透明度。ホワイト部分＝真っ白の部分（``white``）のうち、``ignore_white_area_mm2`` 以上の
    連結領域（8 近傍。斜めのつながりも連結とみなす）。それより小さい真っ白（写真のハイライトや白い点）は
    カラー部分として扱う。

    カラー部分とホワイト部分が両方あるとき（混在）だけ、カラー部分のうち透明な所に接する縁を
    ``choke_mm`` 縮める。ホワイト部分は縮めず、縮める処理はホワイト部分を通り抜けない
    （カラーとホワイトの境目には白版の無い筋を作らない。細いホワイトの縁取りの内側も縮めない）。
    """
    opaque = a8 > 0
    white = white & opaque
    labels, n = ndimage.label(white, structure=np.ones((3, 3), dtype=np.bool_))
    if n:
        # 数えるのも置き換えるのも帯ごとに行う（bincount は int32 のラベルを 64bit に写し直すので、
        # 全体を一度に渡すとラベルの 2 倍のメモリを使う）
        sizes = np.zeros(n + 1, dtype=np.int64)
        for y in range(0, labels.shape[0], _BAND_ROWS):
            sizes += np.bincount(labels[y : y + _BAND_ROWS].ravel(), minlength=n + 1)
        keep = sizes >= opts.ignore_white_area_mm2 * PX_PER_MM**2 - 1e-6
        keep[0] = False
        for y in range(0, labels.shape[0], _BAND_ROWS):
            white[y : y + _BAND_ROWS] = keep[labels[y : y + _BAND_ROWS]]
    del labels
    has_white = bool(white.any())
    color = opaque & ~white
    has_color = bool(color.any())

    kind: WhitePlateKind
    if has_white and has_color:
        kind = "mixed"
    elif has_white:
        kind = "white_only"
    else:
        kind = "color_only"

    choke_px = round(opts.choke_mm * PX_PER_MM)
    if kind != "mixed" or choke_px <= 0:
        return a8, kind
    # 4 近傍の最小値を choke_px 回とる（半径 choke_px のひし形。2px までは円と同じ）。
    # 毎回ホワイト部分を元の値に戻し、ホワイト部分の向こうの透明な所からは縮めない
    cross = ndimage.generate_binary_structure(2, 1)
    plate = a8
    for _ in range(choke_px):
        plate = ndimage.grey_erosion(plate, footprint=cross, mode="nearest")
        plate[white] = a8[white]
    plate[~color] = a8[~color]
    return plate, kind


# --- PDF/X-4（Photoshop が「PDF/X-4:2008」で書く PDF と同じ構成） -------------------------


def _stream(d: bytes, data: bytes) -> bytes:
    return b"<<" + d + b" /Length %d>>\nstream\n" % len(data) + data + b"\nendstream"


def _png_idat(rgb: U8) -> bytes:
    """PNG の IDAT（行ごとのフィルター付きの zlib）. PDF では /Predictor 15 でそのまま読める."""
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, format="PNG", compress_level=6)
    png, pos, out = buf.getvalue(), 8, bytearray()
    while pos < len(png):
        n = int.from_bytes(png[pos : pos + 4], "big")
        if png[pos + 4 : pos + 8] == b"IDAT":
            out += png[pos + 8 : pos + 8 + n]
        pos += 12 + n
    return bytes(out)


def _pdf_string(raw: bytes) -> bytes:
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _text(s: str) -> bytes:
    """PDF のテキスト文字列（BOM 付き UTF-16BE）."""
    return _pdf_string(("﻿" + s).encode("utf-16-be"))


def _ink(name: str) -> bytes:
    """Photoshop がマーク付きコンテンツに書くインキ名（BOM 付き UTF-16BE、末尾 NUL）."""
    return _pdf_string(("﻿" + name + "\0").encode("utf-16-be"))


def _tint(rgb: tuple[int, int, int]) -> bytes:
    a, b, c = (-(255 - v) / 255 for v in reversed(rgb))
    body = "".join(["{dup dup ", *(f"{k:.6f} mul 1.0 add 3 1 roll " for k in (a, b, c))])
    body = body.rstrip() + "}"
    return _stream(b"/FunctionType 4 /Domain [0 1] /Range [0 1 0 1 0 1]", body.encode())


_CALRGB = (
    b"[/CalRGB << /WhitePoint [0.950455 1 1.08905] /BlackPoint [0 0 0] /Gamma [2.2 2.2 2.2] "
    b"/Matrix [0.412384 0.212631 0.0193329 0.35759 0.715164 0.119186 "
    b"0.180481 0.0721893 0.950516] >>]"
)
# 白版の表示色（Photoshop の C100% / M100% を sRGB にしたもの）
_SPOT_DISPLAY_RGB = {"spot_1": (0, 160, 233), "spot_2": (228, 0, 127)}
_JST = timezone(timedelta(hours=9))


def pdf_bytes(
    comp: U8,
    plate: U8,
    title: str,
    srgb_icc: bytes,
    cmyk_icc: bytes,
    now: datetime | None = None,
) -> bytes:
    """白地に合成した絵柄（RGB）と白版から PDF/X-4 を書く（300dpi）."""
    h, w = plate.shape
    w_pt, h_pt = w * 72 / DPI, h * 72 / DPI
    now = now or datetime.now(_JST)
    pdf_date = now.strftime("D:%Y%m%d%H%M%S+09'00'").encode()
    xmp_date = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    doc_id = uuid.uuid4()
    xmp = f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
    xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/"
    xmlns:pdfx="http://ns.adobe.com/pdfx/1.3/">
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{escape(title)}</rdf:li></rdf:Alt></dc:title>
   <xmp:CreateDate>{xmp_date}</xmp:CreateDate>
   <xmp:ModifyDate>{xmp_date}</xmp:ModifyDate>
   <xmp:MetadataDate>{xmp_date}</xmp:MetadataDate>
   <xmp:CreatorTool>pod-admin</xmp:CreatorTool>
   <xmpMM:DocumentID>uuid:{doc_id}</xmpMM:DocumentID>
   <xmpMM:InstanceID>uuid:{doc_id}</xmpMM:InstanceID>
   <xmpMM:RenditionClass>default</xmpMM:RenditionClass>
   <xmpMM:VersionID>1</xmpMM:VersionID>
   <pdf:Producer>pod-admin</pdf:Producer>
   <pdf:Trapped>False</pdf:Trapped>
   <pdfxid:GTS_PDFXVersion>PDF/X-4</pdfxid:GTS_PDFXVersion>
   <pdfx:GTS_PDFXVersion>PDF/X-4</pdfx:GTS_PDFXVersion>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>""".encode()

    # 0 = インキ 100%（Indexed の表で反転する）。TIFF 予測子 2（左の画素との差）で圧縮する
    spot = 255 - plate
    spot_data = zlib.compress(np.diff(spot, axis=1, prepend=np.uint8(0)).tobytes(), 6)
    del spot

    def spot_image(cs: int) -> bytes:
        return _stream(
            b"/Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %d 0 R "
            b"/BitsPerComponent 8 /Filter /FlateDecode "
            b"/DecodeParms << /Predictor 2 /Colors 1 /BitsPerComponent 8 /Columns %d >>"
            % (w, h, cs, w),
            spot_data,
        )

    m = b"q /GS0 gs /RelativeColorimetric ri %.4f 0 0 %.4f 0 0 cm %s Do Q"
    content = (
        b"\n".join(
            [
                # Illustrator は画像ではなく図形の色から文書のプロファイルを決める。画像だけだと
                # ドキュメント情報が「RGB Display Profile」になるので、sRGB で塗った大きさ 0 の四角を置く
                b"q /CS2 cs 1 1 1 sc 0 0 0 0 re f Q",
                b"/MultiChannelImage <</MainChannel /RGBColorMode /Spot ["
                + _ink("spot_1")
                + _ink("spot_2")
                + b"]>>BDC",
                b"/SeparationImages BMC",
                b"/SpotImage <</Ink " + _ink("spot_1") + b">>BDC",
                m % (w_pt, h_pt, b"/Im0"),
                b"EMC",
                b"/SpotImage <</Ink " + _ink("spot_2") + b">>BDC",
                m % (w_pt, h_pt, b"/Im1"),
                b"EMC",
                b"/MainChannelImage BMC",
                m % (w_pt, h_pt, b"/Im2"),
                b"EMC",
                b"EMC",
                b"EMC",
            ]
        )
        + b"\n"
    )

    objs = {
        1: b"<< /Type /Catalog /Pages 3 0 R /Metadata 2 0 R /OutputIntents [4 0 R] >>",
        2: _stream(b"/Type /Metadata /Subtype /XML", xmp),
        3: b"<< /Type /Pages /Kids [5 0 R] /Count 1 >>",
        4: b"<< /Type /OutputIntent /S /GTS_PDFX "
        b"/OutputConditionIdentifier (Japan Color 2001 Coated) "
        b"/Info (Japan Color 2001 Coated) /DestOutputProfile 6 0 R >>",
        5: b"<< /Type /Page /Parent 3 0 R /MediaBox [0 0 %.4f %.4f] /ArtBox [0 0 %.4f %.4f] "
        b"/Contents 7 0 R /Resources << /ColorSpace << /CS0 8 0 R /CS1 9 0 R /CS2 10 0 R "
        b"/DefaultRGB 10 0 R >> /ExtGState << /GS0 11 0 R >> /ProcSet [/PDF /ImageC /ImageI] "
        b"/XObject << /Im0 12 0 R /Im1 13 0 R /Im2 14 0 R >> >> >>" % (w_pt, h_pt, w_pt, h_pt),
        6: _stream(b"/N 4 /Filter /FlateDecode", zlib.compress(cmyk_icc, 9)),
        7: _stream(b"", content),
        8: b"[/Indexed 15 0 R 255 17 0 R]",
        9: b"[/Indexed 16 0 R 255 17 0 R]",
        10: b"[/ICCBased 18 0 R]",
        11: b"<< /Type /ExtGState /op true >>",
        12: spot_image(8),
        13: spot_image(9),
        14: _stream(
            b"/Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
            b"/BitsPerComponent 8 /Intent /Perceptual /Filter /FlateDecode "
            b"/DecodeParms << /Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns %d >>"
            % (w, h, w),
            _png_idat(comp),
        ),
        15: b"[/Separation /spot_1 " + _CALRGB + b" 19 0 R]",
        16: b"[/Separation /spot_2 " + _CALRGB + b" 20 0 R]",
        17: _stream(b"", bytes(range(255, -1, -1))),
        18: _stream(b"/N 3 /Filter /FlateDecode", zlib.compress(srgb_icc, 9)),
        19: _tint(_SPOT_DISPLAY_RGB["spot_1"]),
        20: _tint(_SPOT_DISPLAY_RGB["spot_2"]),
        21: b"<< /Title %s /Creator (pod-admin) /Producer (pod-admin) /CreationDate (%s) "
        b"/ModDate (%s) /GTS_PDFXVersion (PDF/X-4) /Trapped /False >>"
        % (_text(title), pdf_date, pdf_date),
    }
    buf = io.BytesIO()
    buf.write(b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for n in sorted(objs):
        offsets[n] = buf.tell()
        buf.write(b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n")
    xref = buf.tell()
    size = max(objs) + 1
    buf.write(b"xref\n0 %d\n0000000000 65535 f \n" % size)
    for n in range(1, size):
        buf.write(b"%010d 00000 n \n" % offsets[n])
    idhex = doc_id.hex.upper().encode()
    buf.write(
        b"trailer\n<< /Size %d /Root 1 0 R /Info 21 0 R /ID [<%s> <%s>] >>\nstartxref\n%d\n%%%%EOF\n"
        % (size, idhex, idhex, xref)
    )
    return buf.getvalue()
