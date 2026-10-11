"""製造データを 1 件作る本体.

**このモジュールは numpy / scipy / pypdf を読み込む。** 直接 import せず、``app.generator`` の
``generate`` / ``check_available`` を通して使う（モジュール docstring を参照）。
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.generator import GeneratedFile, pipelines
from app.generator.errors import GenerationError
from app.generator.legacy_ai import to_illustrator8
from app.generator.pdf_finish import finish_pdf
from app.generator.products import ICC_SRGB, acrylic_mm, output_filename
from app.generator.vectorcraft import VectorCraft
from app.generator.white_plate import fill_white_plate
from app.utils.mfg_product_mapping import GenerationSpec

logger = logging.getLogger(__name__)

_ACRYLIC = {
    "acrylic_keychain": pipelines.acrylic_keychain,
    "acrylic_stand": pipelines.acrylic_stand,
    "sticker": pipelines.sticker,
}
_ON_TEMPLATE = {"tshirt": pipelines.tshirt, "tote_bag": pipelines.tote_bag}


def generate(
    spec: GenerationSpec,
    images: dict[str, bytes],
    order_id: str,
    *,
    cli: str,
    timeout_seconds: float,
) -> GeneratedFile:
    """製造データを 1 件作る（引数と例外は ``app.generator.generate`` を参照）.

    ``cli`` は VectorCraft の実行ファイル、``timeout_seconds`` は 1 件の生成にかけてよい時間の上限。
    """
    filename = output_filename(spec.product_type, spec.size, spec.variant, order_id)
    with tempfile.TemporaryDirectory(prefix="mfg-") as tmp:
        workdir = Path(tmp)
        paths = {}
        for layer, png in images.items():
            paths[layer] = workdir / f"{layer}.png"
            paths[layer].write_bytes(png)

        if spec.product_type in _ACRYLIC:
            mm = acrylic_mm(spec.product_type, spec.size)
            white = paths.get("white")
            # 白版画像を受け取るのは白版を使う商品だけ（GenerationSpec の optional_layers）
            if white is not None:
                fix = fill_white_plate(images["white"], images["color"], mm)
                white.write_bytes(fix.png)
                logger.info(
                    "white plate fixed: holes=%d notches=%d specks=%d",
                    fix.holes_filled,
                    fix.notches_filled,
                    fix.specks_removed,
                )
            acrylic = pipelines.AcrylicImages(paths["color"], paths["cutline"], white)
            with VectorCraft(cli, timeout_seconds=timeout_seconds) as vc:
                saved = _ACRYLIC[spec.product_type](pipelines.Job(vc, workdir), acrylic, mm, "out.ai")
                raw = saved.read_bytes()
            # VectorCraft を閉じてから書き直す（子プロセスの文書と、書き直しのメモリを重ねない）
            return GeneratedFile(filename, to_illustrator8(raw, filename))

        if spec.product_type in _ON_TEMPLATE:
            image = paths[spec.required_layers[0]]
            with VectorCraft(cli, timeout_seconds=timeout_seconds) as vc:
                saved = _ON_TEMPLATE[spec.product_type](pipelines.Job(vc, workdir), image, "out.pdf")
                raw = saved.read_bytes()
            return GeneratedFile(filename, finish_pdf(raw, ICC_SRGB.read_bytes()))

    raise GenerationError(f"unsupported product_type: {spec.product_type}")

