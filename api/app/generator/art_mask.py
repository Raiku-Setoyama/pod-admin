"""印刷画像を切り抜くクリッピングマスクの元画像を作る（#153）.

アクリル系の .ai は Illustrator 8 形式で書く（ADR-0039）。この形式は画像の透明（アルファ）を持てず、
透明な背景はインキ 0% の四角として残る。製造委託先は印刷画像の背景が透過されていることを求めるので、
**絵のある範囲の外形でクリッピングマスクをかけて切り抜く。** Illustrator 自身も、透明な画像を
Illustrator 8 形式で保存するときは同じ形（インキ 0% に合成した画像＋クリッピングマスク）になる。

絵の外形は、不透明度 50% の境（カットライン・白版の画像をトレースするときと同じ境）で取る。
マスクの内側の透明な画素はインキ 0% の白に見えるので、ほぼ透明な画素（ゴミ・ぼかしの裾）まで
含めると、絵のまわりに白い点や縁が出て「透過されていない」ように見える。
"""

from __future__ import annotations

from app.generator.white_plate import mask_png, read_alpha

# 絵とみなす不透明度（0〜255）
ALPHA_THRESHOLD = 128


def art_mask_png(color_png: bytes) -> bytes | None:
    """絵のある範囲を黒（不透明）にした PNG を返す.

    透明な画素が無い（または絵が無い）ときは切り抜くものが無いので None を返す。
    """
    art = read_alpha(color_png, "color") >= ALPHA_THRESHOLD
    if art.all() or not art.any():
        return None
    return mask_png(art)
