"""製造データ生成の入口（``generate`` と ``check_available``）.

**このモジュールは numpy / scipy / pypdf を読み込む。** これらはワーカー用のイメージにだけ入っているので、
呼び出し側は関数の中で import すること（``app.generator`` のモジュール docstring を参照）。

生成は CPU を使う同期処理なので、非同期のコードからは ``asyncio.to_thread`` で呼ぶ。
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

from PIL import Image

from app.generator import pipelines
from app.generator.errors import GenerationError, GeneratorUnavailableError
from app.generator.legacy_ai import to_illustrator8
from app.generator.pdf_finish import finish_pdf
from app.generator.products import ICC_SRGB, acrylic_mm, output_filename
from app.generator.result import GeneratedFile
from app.generator.vectorcraft import VectorCraft
from app.generator.white_plate import fill_white_plate

logger = logging.getLogger(__name__)

_ACRYLIC = {
    "acrylic_keychain": pipelines.acrylic_keychain,
    "acrylic_stand": pipelines.acrylic_stand,
    "sticker": pipelines.sticker,
}
_ON_TEMPLATE = {"tshirt": pipelines.tshirt, "tote_bag": pipelines.tote_bag}
# 白版の抜けを埋める商品（白版を使うもの）
_WITH_WHITE_PLATE = frozenset({"acrylic_keychain", "acrylic_stand"})


def generate(
    *,
    product_type: str,
    size: str,
    variant: str | None,
    images: dict[str, bytes],
    order_id: str,
    cli: str,
    timeout_seconds: float,
) -> GeneratedFile:
    """製造データを 1 件作る.

    Args:
        product_type / size / variant: ``app.utils.mfg_product_mapping`` が正規化した値。
        images: レイヤー種別（color / cutline / white / design）→ PNG のバイト列。
            T シャツ・トートは 1 枚だけ渡す（design、無ければ color）。
        order_id: 出力ファイル名に入れる ID（製造データの ID）。
        cli: VectorCraft の実行ファイル。
        timeout_seconds: 1 件の生成にかけてよい時間の上限。

    Raises:
        GenerationError: この入力からは作れない。
        GeneratorUnavailableError: VectorCraft を起動できない。
    """
    filename = output_filename(product_type, size, variant, order_id)
    with tempfile.TemporaryDirectory(prefix="mfg-") as tmp:
        workdir = Path(tmp)
        paths = {}
        for layer, png in images.items():
            paths[layer] = workdir / f"{layer}.png"
            paths[layer].write_bytes(png)

        if product_type in _ACRYLIC:
            mm = acrylic_mm(product_type, size)
            white = paths.get("white")
            if white is not None and product_type in _WITH_WHITE_PLATE:
                fix = fill_white_plate(images["white"], images["color"], _px_per_mm(images, mm))
                white.write_bytes(fix.png)
                logger.info(
                    "white plate fixed: holes=%d notches=%d specks=%d",
                    fix.holes_filled,
                    fix.notches_filled,
                    fix.specks_removed,
                )
            acrylic = pipelines.AcrylicImages(paths["color"], paths["cutline"], white)
            with VectorCraft(cli, timeout_seconds=timeout_seconds) as vc:
                saved = _ACRYLIC[product_type](pipelines.Job(vc, workdir), acrylic, mm, "out.ai")
                return GeneratedFile(filename, to_illustrator8(saved.read_bytes(), filename))

        if product_type in _ON_TEMPLATE:
            if len(paths) != 1:
                raise GenerationError(f"{product_type} takes exactly one image, got {sorted(paths)}")
            (image,) = paths.values()
            with VectorCraft(cli, timeout_seconds=timeout_seconds) as vc:
                saved = _ON_TEMPLATE[product_type](pipelines.Job(vc, workdir), image, "out.pdf")
                return GeneratedFile(filename, finish_pdf(saved.read_bytes(), ICC_SRGB.read_bytes()))

    raise GenerationError(f"unsupported product_type: {product_type}")


def _px_per_mm(images: dict[str, bytes], mm: int) -> float:
    """白版画像の解像度。どの画像も絵柄の一辺（mm）に引き伸ばして置くので、幅 ÷ mm になる."""
    with Image.open(io.BytesIO(images["white"])) as im:
        return im.width / mm


def check_available(*, cli: str, timeout_seconds: float) -> None:
    """VectorCraft を起動してコマンドが通ることを確かめる（ワーカーの死活確認）.

    Raises:
        GeneratorUnavailableError: 起動できない、または応答しない。
    """
    try:
        with VectorCraft(cli, timeout_seconds=timeout_seconds) as vc:
            vc.cmd("edit.colorSettings")
    except GenerationError as exc:
        raise GeneratorUnavailableError(str(exc)) from exc
