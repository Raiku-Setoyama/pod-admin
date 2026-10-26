"""製造データ生成のパス計算（app/generator/geometry.py）.

座標は y 上向き（pt）。VectorCraft を使わずに確かめられる規則だけをここで見る。
VectorCraft を通した結果は tests/integration/test_generator_vectorcraft.py が見る。
"""

import math

import pytest

from app.generator import geometry as G
from app.generator.errors import GenerationError

MM = 72 / 25.4


def _polygon(points: list[tuple[float, float]]) -> G.SubPath:
    """直線だけの閉じたパス（方向線はアンカーと同じ）."""
    return G.SubPath(list(points), list(points), list(points), True)


def _circle(cx: float, cy: float, r: float, n: int = 32) -> G.SubPath:
    return _polygon(
        [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    )


class TestBaseExtension:
    """ADR-0038: 土台を最下点まで延ばす."""

    def test_no_extension_when_the_base_is_already_the_lowest_edge(self) -> None:
        body = _polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
        assert G.base_extension_rect(body, 5 * MM) is None

    def test_extends_to_a_protrusion_below_the_base(self) -> None:
        # 土台の下辺は y=10。右側の足先が y=4 まではみ出している
        body = _polygon([(0, 10), (60, 10), (62, 4), (70, 4), (72, 10), (100, 10), (100, 100), (0, 100)])
        rect = G.base_extension_rect(body, 5 * MM)
        assert rect is not None
        left, top, right, bottom = rect
        # 土台（最も長い水平な辺 x=0..60）から、はみ出した範囲（x=72 まで）を、
        # 土台の中へ 1pt 食い込ませて埋める
        assert left == 0
        assert right == pytest.approx(72, abs=0.5)  # 曲線は 16 分割で調べる
        assert top == pytest.approx(11)
        assert bottom == pytest.approx(4)

    def test_fails_when_there_is_no_flat_base(self) -> None:
        """土台が見つからない入力は失敗させる（タブの無いデータを成功として納入しない）."""
        with pytest.raises(GenerationError, match="flat base edge not found"):
            G.base_extension_rect(_circle(50, 50, 40), 5 * MM)

    def test_short_flat_segments_are_not_a_base(self) -> None:
        """丸い輪郭の上の短い水平線は土台ではない（VectorCraft のトレースが作ることがある）."""
        short = G.MIN_BASE_LENGTH_PT * 0.5
        body = _polygon([(50 - short / 2, 0), (50 + short / 2, 0), (90, 40), (50, 80), (10, 40)])
        assert G.find_base_edge(body, 5 * MM) is None

    def test_ignores_flat_edges_far_above_the_lowest_point(self) -> None:
        # 最下点（y=0 の頂点）から 5mm より上にある水平な辺は土台ではない
        body = _polygon([(50, 0), (100, 30), (100, 100), (0, 100), (0, 30)])
        assert G.find_base_edge(body, 5 * MM) is None


class TestMergePedestalTab:
    def _tab(self) -> G.SubPath:
        """肩ライン y=20 に、深さ 20 のノッチ（幅 40）を持つタブのテンプレート."""
        return _polygon([(0, 20), (30, 20), (30, 0), (70, 0), (70, 20), (100, 20), (100, 40), (0, 40)])

    def test_tab_is_placed_unchanged_at_the_bottom_center(self) -> None:
        body = _polygon([(0, 10), (200, 10), (200, 300), (0, 300)])
        merged = G.merge_pedestal_tab(body, self._tab())

        # タブはテンプレートの形のまま平行移動するだけ（ADR-0038 の必須条件）。
        # 肩ラインを本体の底（y=10）に、中心を本体の中心（x=100）に合わせる
        dx, dy = 100 - 50, 10 - 20
        notch = {(30 + dx, 0 + dy), (70 + dx, 0 + dy), (30 + dx, 20 + dy), (70 + dx, 20 + dy)}
        assert notch <= set(merged.A)
        assert G.bounds([merged])[3] == pytest.approx(10 - 20)  # ノッチの深さだけ下へ伸びる

    def test_fails_without_a_flat_bottom(self) -> None:
        with pytest.raises(GenerationError, match="need >=2 bottom points"):
            G.merge_pedestal_tab(_circle(100, 100, 80), self._tab())

    # 左右の脚が土台と同じ高さ（y=10）で床に着き、土台（x=60..140）との間にすき間がある。
    # 椅子やピアノの脚が床に着いている絵柄（BUG-0005）
    _LEGS: list[tuple[float, float]] = [
        (0, 10), (20, 10), (20, 30), (60, 30), (60, 10), (140, 10),
        (140, 30), (180, 30), (180, 10), (200, 10), (200, 300), (0, 300),
    ]  # fmt: skip

    @pytest.mark.parametrize("reverse", [False, True])
    @pytest.mark.parametrize("start", [0, 3, 5, 9])
    def test_keeps_the_body_when_legs_touch_the_floor_beside_the_base(self, reverse: bool, start: int) -> None:
        """BUG-0005: 底の高さの点が離れて何か所にもあっても、タブは土台だけに付け、本体の輪郭は残す."""
        pts = list(reversed(self._LEGS)) if reverse else list(self._LEGS)
        body = _polygon(pts[start:] + pts[:start])
        merged = G.merge_pedestal_tab(body, self._tab())

        # 本体の外形はそのまま（下だけノッチの深さ 20 伸びる）
        assert G.bounds([merged]) == pytest.approx((0, 300, 200, -10))
        # 脚の底は残る
        assert {(0, 10), (20, 10), (180, 10), (200, 10)} <= set(merged.A)
        # タブは土台の中央（本体の中心 x=100）に付く
        notch = {(80, -10), (120, -10), (80, 10), (120, 10)}
        assert notch <= set(merged.A)
        # 土台の両端だけがタブの肩につながり、土台の途中の点は残らない
        assert len(merged.A) == len(body.A) - 2 + 4 + 2

    def test_fails_when_the_tab_is_wider_than_the_base(self) -> None:
        """土台にタブが収まらないときは、壊れたカットラインを作らずに失敗させる（ADR-0038）."""
        body = _polygon([(0, 30), (90, 30), (90, 10), (110, 10), (110, 30), (200, 30), (200, 300), (0, 300)])
        with pytest.raises(GenerationError, match="does not fit"):
            G.merge_pedestal_tab(body, self._tab())


class TestKeyhole:
    def test_finds_the_concentric_inner_and_outer_circles(self) -> None:
        inner = _circle(100, 200, 5.03 / 2)
        outer = _circle(100, 200, 17.36 / 2)
        other = _circle(300, 300, 50)
        found = G.find_keyhole_pair([other, outer, inner])
        assert found is not None
        assert found.points is inner
        assert found.outer_diameter_pt == pytest.approx(17.36, abs=0.1)

    def test_replaces_the_traced_hole_with_the_template_circle(self) -> None:
        circle = G.find_keyhole_pair([_circle(0, 0, 17.36 / 2), _circle(0, 0, 5.03 / 2)])
        assert circle is not None
        body = _circle(100, 100, 80)
        traced_hole = _circle(100, 170, 3)
        out = G.replace_keyhole([body, traced_hole], circle)
        hole = out[0]
        b = G.bounds([hole])
        assert ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) == pytest.approx((100, 170))
        assert b[2] - b[0] == pytest.approx(5.03, abs=0.1)
        assert out[1] is body


class TestSmoothing:
    def test_keeps_the_bottom_edge_when_asked(self) -> None:
        # 細かいアンカーの円の下に平らな辺。底の点は間引かない
        pts = [(x, 0.0) for x in range(0, 101, 2)] + [
            (50 + 50 * math.cos(t / 20 * math.pi), 50 * math.sin(t / 20 * math.pi)) for t in range(1, 20)
        ]
        sp = _polygon(pts)
        out = G.smooth_cutline_path(sp, 5, preserve_bottom_edge=True)
        assert sum(1 for a in out.A if abs(a[1]) < 1) == sum(1 for a in sp.A if abs(a[1]) < 1)
