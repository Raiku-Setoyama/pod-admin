"""白版画像の抜けを埋める（REQ-0067）.

販売サイトの白版画像は、デザインのうち半透明でほぼ白の部分（白い羽の模様など）を白版から外している
ことがある。透明アクリルではそこが透けるため、製造委託先から「White が抜けている」と指摘された
（2026-10-09）。デザインの外形と、画像生成側が外周に付けている内寄せはそのまま残し、次の 3 つだけを直す。

1. 白版の内側に閉じた穴のうち、下の印刷画像に絵があるものを埋める。完全に透明な穴（本当の抜き）は残す
2. 外周の切れ込みのうち、下の絵が半透明のもの（1 と同じ原因でできたもの）を埋める。
   埋めるのは印刷画像に絵がある範囲だけで、外周の内寄せ分は空けておく
3. 白版の 0.1mm の内寄せでつぶれてしまう小さな孤立点を消す（残すと面積ほぼ 0 のパスになる）

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

# 切れ込みとみなす幅の半分（この 2 倍より狭い切れ込みを埋める対象にする）
NOTCH_HALF_WIDTH_MM = 0.75
# 下の絵の不透明度の平均がこれ未満なら、半透明が原因の切れ込みとして埋める（0〜255）
NOTCH_MAX_MEAN_ALPHA = 150
# 切れ込みを埋めるときに、絵の外周から空けておく幅
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

    # 1. 絵のある穴
    holes, n_holes = ndimage.label(ndimage.binary_fill_holes(white) & ~white)
    hole_ids = np.arange(1, n_holes + 1)
    has_ink = ndimage.maximum(color, holes, hole_ids) > 0 if n_holes else np.array([], dtype=bool)
    filled = white | np.isin(holes, hole_ids[has_ink])

    # 2. 半透明が原因の外周の切れ込み
    r = max(1, round(NOTCH_HALF_WIDTH_MM * px_per_mm))
    pad = r + 2
    closed = ndimage.binary_closing(np.pad(filled, pad), structure=_disk(r))[pad:-pad, pad:-pad]
    inside_art = ndimage.binary_erosion(color > 0, structure=_disk(max(1, round(CHOKE_MM * px_per_mm))))
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

    # 3. 内寄せでつぶれる小さな孤立点
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
        holes_filled=int(has_ink.sum()),
        notches_filled=notches_filled,
        specks_removed=specks_removed,
    )
