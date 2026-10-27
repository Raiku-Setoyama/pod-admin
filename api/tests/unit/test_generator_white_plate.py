"""白版画像の抜けを埋める処理（app/generator/white_plate.py、REQ-0067・#155）."""

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


def test_fills_a_hole_under_printed_art() -> None:
    white, color = _plate_and_art()
    hole = _disk_mask(200, 200, 20)
    white[hole] = 0
    color[hole] = 200  # 白版から外れているが、印刷される絵（不透明度 50% 以上）

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    assert fix.holes_filled == 1
    assert (_alpha(fix.png)[hole] == 255).all()


def test_keeps_a_hole_under_art_that_is_not_printed() -> None:
    """印刷画像は不透明度 50% 以上で切り抜くので、それ未満の所に白版を置くと白い面だけが見える（#155）."""
    white, color = _plate_and_art()
    hole = _disk_mask(200, 200, 20)
    white[hole] = 0
    color[hole] = 100

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    assert fix.holes_filled == 0
    assert (_alpha(fix.png)[hole] == 0).all()


def test_keeps_a_transparent_gap_whose_rim_has_art() -> None:
    """白版の内寄せで穴の縁には絵がかかる。縁の絵の所だけ埋め、絵に囲まれた透明なすき間は残す（#155）."""
    white, color = _plate_and_art()
    hole = _disk_mask(200, 200, 40)
    gap = _disk_mask(200, 200, 30)  # 印刷画像のすき間。白版の穴はこれより 10px 大きい
    white[hole] = 0
    color[gap] = 0

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    out = _alpha(fix.png)
    assert fix.holes_filled == 1
    assert (out[_disk_mask(200, 200, 32)] == 0).all()  # すき間＋縁から空ける幅は透明のまま
    assert (out[hole & ~_disk_mask(200, 200, 36)] == 255).all()  # 縁の絵の所は白版


def test_fills_only_the_art_inside_a_transparent_gap() -> None:
    """すき間の中を通る棒（ピアノのペダルの棒など）には白版を敷き、両脇のすき間は残す（#155）."""
    white, color = _plate_and_art()
    hole = np.zeros((SIZE, SIZE), dtype=bool)
    hole[150:250, 160:240] = True
    rod = np.zeros((SIZE, SIZE), dtype=bool)
    rod[150:250, 190:210] = True  # 幅 20px ≈ 0.85mm
    white[hole] = 0
    color[hole & ~rod] = 0

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    out = _alpha(fix.png)
    assert fix.holes_filled == 1
    assert (out[155:245, 195:205] == 255).all()
    assert (out[155:245, 165:185] == 0).all()
    assert (out[155:245, 215:235] == 0).all()


def test_trims_the_plate_where_the_art_is_not_printed() -> None:
    """販売サイトの白版が、印刷されない半透明の所にかかっていれば削る（かごの編み目のすき間など、#155）."""
    white, color = _plate_and_art()
    faint = _disk_mask(200, 200, 15)
    color[faint] = 60

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    out = _alpha(fix.png)
    assert fix.trimmed_mm2 > 0
    assert (out[faint] == 0).all()
    assert (out[_disk_mask(200, 200, 100) & ~_disk_mask(200, 200, 25)] == 255).all()


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
    color[notch & (color > 0)] = 140  # 半透明だが印刷される

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
    color[4:19, 4:19] = 255  # 下の絵は白版より大きい（印刷される絵の内側にある孤立点）

    fix = fill_white_plate(_png(white), _png(color), ART_MM)

    assert fix.specks_removed == 1
    assert (_alpha(fix.png)[speck] == 0).all()


def test_outline_is_unchanged_without_holes_or_notches() -> None:
    white, color = _plate_and_art()
    fix = fill_white_plate(_png(white), _png(color), ART_MM)
    assert (fix.holes_filled, fix.notches_filled, fix.specks_removed) == (0, 0, 0)
    assert fix.trimmed_mm2 == 0
    assert (_alpha(fix.png) == white).all()


def test_compares_against_a_color_layer_of_a_different_size() -> None:
    """生成ではどの画像も同じ範囲に引き伸ばして重ねるので、大きさが違っても比べられる."""
    white, color = _plate_and_art()
    hole = _disk_mask(200, 200, 20)
    white[hole] = 0
    color[hole] = 200
    big_color = np.array(Image.fromarray(color).resize((SIZE * 2, SIZE * 2)))

    fix = fill_white_plate(_png(white), _png(big_color), ART_MM)

    assert fix.holes_filled == 1


def test_unreadable_image_is_an_input_error() -> None:
    white, _ = _plate_and_art()
    with pytest.raises(GenerationError, match="color layer is not a readable image"):
        fill_white_plate(_png(white), b"not a png", ART_MM)
