"""白版画像の抜けを埋める処理（app/generator/white_plate.py、REQ-0067）."""

import io

import numpy as np
import numpy.typing as npt
import pytest
from PIL import Image

from app.generator.errors import GenerationError
from app.generator.white_plate import fill_white_plate

# 600dpi（販売サイトの実データと同じ解像度）。SIZE px の画像が ART_MM の絵柄になる
PX_PER_MM = 1181 / 50
SIZE = 400
ART_MM = SIZE / PX_PER_MM


def _png(alpha: npt.NDArray[np.uint8]) -> bytes:
    rgba = np.zeros((*alpha.shape, 4), dtype=np.uint8)
    rgba[..., 3] = alpha
    out = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(out, format="PNG")
    return out.getvalue()


def _alpha(png: bytes) -> npt.NDArray[np.uint8]:
    return np.array(Image.open(io.BytesIO(png)).convert("RGBA"))[..., 3]


def _disk_mask(cx: int, cy: int, r: int) -> npt.NDArray[np.bool_]:
    y, x = np.ogrid[:SIZE, :SIZE]
    mask: npt.NDArray[np.bool_] = (x - cx) ** 2 + (y - cy) ** 2 <= r * r
    return mask


def _plate_and_art() -> tuple[npt.NDArray[np.uint8], npt.NDArray[np.uint8]]:
    """白版は大きな円。印刷画像は白版より 5px 大きい円（外周の内寄せ分）."""
    white = np.where(_disk_mask(200, 200, 150), 255, 0).astype(np.uint8)
    color = np.where(_disk_mask(200, 200, 155), 255, 0).astype(np.uint8)
    return white, color


def test_fills_a_hole_where_the_art_is_semi_transparent() -> None:
    white, color = _plate_and_art()
    hole = _disk_mask(200, 200, 20)
    white[hole] = 0
    color[hole] = 100  # 半透明でほぼ白の模様（白い羽など）

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    assert fix.holes_filled == 1
    assert (_alpha(fix.png)[hole] == 255).all()


def test_keeps_a_fully_transparent_hole() -> None:
    """絵の無い穴は本当の抜きなので残す."""
    white, color = _plate_and_art()
    hole = _disk_mask(200, 200, 20)
    white[hole] = 0
    color[hole] = 0

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    assert fix.holes_filled == 0
    assert (_alpha(fix.png)[hole] == 0).all()


def test_fills_a_notch_caused_by_semi_transparent_art() -> None:
    white, color = _plate_and_art()
    notch = np.zeros((SIZE, SIZE), dtype=bool)
    notch[185:215, 330:351] = True  # 外周から内側へ 20px の切れ込み（幅 30px ≈ 1.3mm）
    white[notch] = 0
    color[notch & (color > 0)] = 100

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    assert fix.notches_filled == 1
    # 奥は埋まる。入口は外周の形に沿って少し空く（外周の内寄せを崩さない）
    deep = notch & _disk_mask(200, 200, 138)
    assert (_alpha(fix.png)[deep] == 255).all()


def test_keeps_a_notch_under_opaque_art() -> None:
    """下の絵が不透明な切れ込みは、画像生成側が意図して外したものとして残す."""
    white, color = _plate_and_art()
    notch = np.zeros((SIZE, SIZE), dtype=bool)
    notch[185:215, 330:351] = True
    white[notch] = 0

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    assert fix.notches_filled == 0
    assert (_alpha(fix.png)[notch & _disk_mask(200, 200, 145)] == 0).all()


def test_removes_specks_that_the_inward_offset_would_crush() -> None:
    white, color = _plate_and_art()
    speck = np.zeros((SIZE, SIZE), dtype=bool)
    speck[10:13, 10:13] = True  # 9px ≈ 0.016mm²
    white[speck] = 255
    color[speck] = 255

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    assert fix.specks_removed == 1
    assert (_alpha(fix.png)[speck] == 0).all()


def test_outline_is_unchanged_without_holes_or_notches() -> None:
    white, color = _plate_and_art()
    fix = fill_white_plate(_png(white), _png(color), ART_MM)
    assert (fix.holes_filled, fix.notches_filled, fix.specks_removed) == (0, 0, 0)
    assert (_alpha(fix.png) == white).all()


def test_compares_against_a_color_layer_of_a_different_size() -> None:
    """生成ではどの画像も同じ範囲に引き伸ばして重ねるので、大きさが違っても比べられる."""
    white, color = _plate_and_art()
    hole = _disk_mask(200, 200, 20)
    white[hole] = 0
    color[hole] = 100
    big_color = np.array(Image.fromarray(color).resize((SIZE * 2, SIZE * 2)))

    fix = fill_white_plate(_png(white), _png(big_color), ART_MM)

    assert fix.holes_filled == 1


def test_unreadable_image_is_an_input_error() -> None:
    white, _ = _plate_and_art()
    with pytest.raises(GenerationError, match="color layer is not a readable image"):
        fill_white_plate(_png(white), b"not a png", ART_MM)
