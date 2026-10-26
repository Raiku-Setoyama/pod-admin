"""印刷画像を切り抜くマスクの元画像（app/generator/art_mask.py、BUG-0004）."""

import io

import numpy as np
import pytest
from PIL import Image

from app.generator.art_mask import art_mask_png


def _png(alpha: np.ndarray) -> bytes:
    rgba = np.zeros((*alpha.shape, 4), dtype=np.uint8)
    rgba[..., 0] = 200
    rgba[..., 3] = alpha
    out = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(out, format="PNG")
    return out.getvalue()


def _mask(png: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(png)) as im:
        return np.array(im.getchannel("A")) > 0


def test_mask_follows_the_half_opaque_outline() -> None:
    """絵の外形は不透明度 50% の境で取る。ほぼ透明な画素（ゴミ・ぼかしの裾）はマスクに入れない.

    入れると、その範囲は旧形式ではインキ 0% の白として見え、背景が透過されていないように見える。
    """
    alpha = np.zeros((100, 100), dtype=np.uint8)
    alpha[20:80, 20:80] = 255  # 絵
    alpha[20:80, 80] = 128  # 縁の半透明（境の内側）
    alpha[20:80, 81] = 127  # 縁の半透明（境の外側）
    alpha[5:8, 5:8] = 30  # ほぼ透明なゴミ
    png = art_mask_png(_png(alpha))
    assert png is not None
    mask = _mask(png)
    assert mask[20:80, 20:81].all()
    assert not mask[:, 81:].any()
    assert not mask[5:8, 5:8].any()


@pytest.mark.parametrize("value", [255, 0])
def test_no_mask_without_anything_to_cut_out(value: int) -> None:
    """全面が不透明（背景まで塗られた画像）または全面が透明なら、切り抜かない."""
    assert art_mask_png(_png(np.full((10, 10), value, dtype=np.uint8))) is None
