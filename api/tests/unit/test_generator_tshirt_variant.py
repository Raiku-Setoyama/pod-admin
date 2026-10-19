"""T シャツの印刷位置（variant）による箱の選択（REQ-0070）。VectorCraft は要らない."""

import pytest

from app.generator import pipelines
from app.generator.errors import GenerationError
from app.generator.runner import generate
from app.utils.mfg_product_mapping import GenerationSpec

MM = 72 / 25.4


def test_left_chest_box_touches_the_top_right_of_the_artboard() -> None:
    artboard = {"x": 10.0, "y": 20.0, "width": 297 * MM, "height": 406 * MM}
    x, y, w, h = pipelines.tshirt_left_chest_box(artboard)
    assert w == pytest.approx(283.46, abs=0.01)
    assert h == w
    assert x + w == pytest.approx(artboard["x"] + artboard["width"])  # 右端に接する
    assert y == artboard["y"]  # 上端に接する（左上原点・y 下向き。TOTE_PRINT_AREA と同じ）


@pytest.mark.parametrize("variant", ["pocket", "front"])
def test_unknown_tshirt_variant_is_rejected_before_generation(variant: str) -> None:
    spec = GenerationSpec("tshirt", "M", variant, ("design",))
    with pytest.raises(GenerationError, match=variant):
        generate(spec, {"design": b"png"}, "md-1", cli="/nonexistent", timeout_seconds=1)


def test_tote_bag_has_no_variant() -> None:
    spec = GenerationSpec("tote_bag", "M", "left_chest", ("design",))
    with pytest.raises(GenerationError, match="left_chest"):
        generate(spec, {"design": b"png"}, "md-1", cli="/nonexistent", timeout_seconds=1)
