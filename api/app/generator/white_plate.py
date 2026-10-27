"""白版画像を、印刷される絵に合わせて直す（REQ-0067・#155）.

販売サイトの白版画像は、デザインのうち半透明でほぼ白の部分（白い羽の模様など）を白版から外している
ことがある。透明アクリルではそこが透けるため、製造委託先から「White が抜けている」と指摘された
（2026-10-09）。逆に、印刷されない所に白版があると白インキの面だけが見える。印刷画像は不透明度 50% 以上の
範囲で切り抜く（``art_mask``、#153）ので、白版もその内側に収める（2026-10-27 の指摘、#155）。
デザインの外形と、画像生成側が外周に付けている内寄せはそのまま残し、次の 4 つだけを直す。

1. 白版の内側に閉じた穴のうち、印刷される絵がある所を埋める。絵に囲まれた透明なすき間（本当の抜き）は残す
2. 外周の切れ込みのうち、下の絵が半透明のもの（1 と同じ原因でできたもの）を埋める。
   埋めるのは印刷される絵がある範囲だけで、外周の内寄せ分は空けておく
3. 印刷されない所（下の絵の不透明度が 50% 未満）にかかる白版を削る
4. 白版の 0.1mm の内寄せでつぶれてしまう小さな孤立点を消す（残すと面積ほぼ 0 のパスになる）

白版は、印刷される絵の外形から ``CHOKE_MM`` 内側までに収める（版ずれで白がはみ出さないように）。
しきい値は mm で持ち、画像の解像度（px/mm）で換算する。値は 600dpi（23.6px/mm）の実データで
製造委託先の確認を通した版（illustrator-vm `research/vectorcraft/fix_white.py`）に合わせてある。
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from PIL import Image
from scipy import ndimage

from app.generator.errors import GenerationError

# 印刷される絵とみなす不透明度（0〜255）。印刷画像を切り抜く境（``art_mask``）と同じ
ART_ALPHA_THRESHOLD = 128
# 切れ込みとみなす幅の半分（この 2 倍より狭い切れ込みを埋める対象にする）
NOTCH_HALF_WIDTH_MM = 0.75
# 下の絵の不透明度の平均がこれ未満なら、半透明が原因の切れ込みとして埋める（0〜255）
NOTCH_MAX_MEAN_ALPHA = 150
# 白版を、印刷される絵の外形から空けておく幅
CHOKE_MM = 0.127
# これより小さい孤立した白は消す
SPECK_AREA_MM2 = 0.179

Mask = npt.NDArray[np.bool_]


@dataclass(frozen=True)
class WhitePlateFix:
    """直した白版画像と、直した箇所の数."""

    png: bytes
    holes_filled: int
    notches_filled: int
    specks_removed: int
    trimmed_mm2: float


def _disk(radius: int) -> Mask:
    y, x = np.ogrid[-radius : radius + 1, -radius : radius + 1]
    disk: Mask = x * x + y * y <= radius * radius
    return disk


def read_alpha(png: bytes, name: str, size: tuple[int, int] | None = None) -> npt.NDArray[np.uint8]:
    """画像の不透明度。``size`` を渡すとその大きさ（幅, 高さ）に合わせる."""
    try:
        with Image.open(io.BytesIO(png)) as im:
            alpha = im.convert("RGBA").getchannel("A")
            if size is not None and alpha.size != size:
                # 生成ではどの画像も同じ範囲に引き伸ばして重ねるので、白版の大きさに合わせて比べる
                alpha = alpha.resize(size, Image.Resampling.BILINEAR)
            arr: npt.NDArray[np.uint8] = np.array(alpha)
    except (OSError, ValueError) as exc:
        raise GenerationError(f"{name} layer is not a readable image: {exc}") from exc
    return arr


def mask_png(mask: Mask) -> bytes:
    """``mask`` の真の画素を黒（不透明）、それ以外を透明にした PNG（トレースの入力にする形）."""
    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[mask, 3] = 255
    out = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(out, format="PNG")
    return out.getvalue()


def fill_white_plate(white_png: bytes, color_png: bytes, art_mm: float) -> WhitePlateFix:
    """白版画像（不透明な部分が白版）の抜けを埋めた PNG を返す.

    ``art_mm`` は絵柄の一辺（mm）。どの画像もこの大きさに引き伸ばして置くので、
    白版画像の解像度（px/mm）は「幅 ÷ art_mm」になる。
    """
    white = read_alpha(white_png, "white") > 127
    px_per_mm = white.shape[1] / art_mm
    color = read_alpha(color_png, "color", size=(white.shape[1], white.shape[0]))
    # 白版を置いてよい範囲。画像の端で切れている絵は、その先にも続いているものとして扱う
    inside_art = ndimage.binary_erosion(
        color >= ART_ALPHA_THRESHOLD,
        structure=_disk(max(1, round(CHOKE_MM * px_per_mm))),
        border_value=1,
    )

    # 1. 絵のある穴（穴の中の、印刷される絵の所だけ）
    holes, _ = ndimage.label(ndimage.binary_fill_holes(white) & ~white)
    hole_fill = (holes > 0) & inside_art
    holes_filled = len(np.unique(holes[hole_fill]))
    filled = white | hole_fill

    # 2. 半透明が原因の外周の切れ込み
    r = max(1, round(NOTCH_HALF_WIDTH_MM * px_per_mm))
    pad = r + 2
    closed = ndimage.binary_closing(np.pad(filled, pad), structure=_disk(r))[pad:-pad, pad:-pad]
    notches, n_notches = ndimage.label(closed & ~filled & inside_art)
    speck_px = SPECK_AREA_MM2 * px_per_mm * px_per_mm
    notches_filled = 0
    if n_notches:
        notch_ids = np.arange(1, n_notches + 1)
        sizes = ndimage.sum_labels(np.ones_like(color), notches, notch_ids)
        mean_alpha = ndimage.mean(color, notches, notch_ids)
        fill_ids = notch_ids[(sizes >= speck_px) & (mean_alpha < NOTCH_MAX_MEAN_ALPHA)]
        filled |= np.isin(notches, fill_ids)
        notches_filled = len(fill_ids)

    # 3. 印刷されない所にかかる白版
    trimmed = filled & ~inside_art
    filled &= inside_art

    # 4. 内寄せでつぶれる小さな孤立点
    islands, n_islands = ndimage.label(filled)
    specks_removed = 0
    if n_islands:
        island_ids = np.arange(1, n_islands + 1)
        sizes = ndimage.sum_labels(np.ones_like(color), islands, island_ids)
        specks = island_ids[sizes < speck_px]
        filled &= ~np.isin(islands, specks)
        specks_removed = len(specks)

    return WhitePlateFix(
        png=mask_png(filled),
        holes_filled=holes_filled,
        notches_filled=notches_filled,
        specks_removed=specks_removed,
        trimmed_mm2=float(trimmed.sum() / (px_per_mm * px_per_mm)),
    )
