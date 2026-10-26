"""商品ごとの製造データの作り方（VectorCraft の操作）.

illustrator-vm の ExtendScript（`scripts/*.jsx`）と同じ手順を VectorCraft のコマンドで行う。
各関数は VectorCraft の形式で保存したファイルのパスを返す。製造委託先に渡す形式への変換
（旧形式 .ai、PDF の整形）は呼び出し側（``app.generator.generate``）が行う。

座標の約束: VectorCraft のコマンドは y 下向き・アートボード左上原点（pt）。
カットラインの計算は ``geometry`` で y 上向きに直して行う。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.generator import geometry as G
from app.generator.errors import GenerationError
from app.generator.products import (
    ICC_JAPAN_COLOR_2001_COATED,
    TOTE_TEMPLATE,
    TSHIRT_TEMPLATE,
    keyhole_template,
    stand_tab_template,
)
from app.generator.vectorcraft import VectorCraft

logger = logging.getLogger(__name__)

MM = 72 / 25.4
JAPAN_COLOR_2001_COATED = "Japan Color 2001 Coated"
K100 = {"c": 0, "m": 0, "y": 0, "k": 100}

# アクリル系の新規文書の余白（illustrator-vm の margin_mm = 3）
MARGIN_PT = 3 * MM
# アクリル系のレイヤー（上から）
ACRYLIC_LAYERS = ["CutLine", "ColorPrint", "White"]
# 白版の内寄せ（illustrator-vm の path_offset_pt。≈ -0.1mm）
WHITE_OFFSET_PT = -0.2835
# 画像トレースの設定。illustrator-vm が Illustrator 2026 で実際に使っている値に合わせた
# （本番スクリプトの pathFitting / cornerAngle は存在しないプロパティで、効いていない）
TRACE: dict[str, Any] = {
    "mode": "blackAndWhite",
    "threshold": 128,
    "paths": 50,
    "corners": 50,
    "noise": 50,
    "method": "overlapping",
    "ignoreWhite": False,
    "snapCurvesToLines": False,
}
# カットラインだけ精度を上げる。VectorCraft はアンカーが少なめで、本番の
# 「5pt 間引き＋スムーズ化」で形が崩れるため（この値で全ケース Illustrator 以上に元画像へ忠実になった）
TRACE_CUTLINE: dict[str, Any] = {**TRACE, "paths": 85}
# アクリルスタンドの土台を探す範囲（ADR-0038）
STAND_BASE_SEARCH_MM = 5
# T シャツ・トートの画像の余白（1mm）
TEMPLATE_IMAGE_MARGIN_PT = 1 * MM
# トートの「印刷範囲」。テンプレートでは塗りも線もない名前付きパスで、VectorCraft が読む PDF 部分に
# 出てこないため、Illustrator 上の値を固定で持つ（アートボード左上原点・y 下向き。x, y, 幅, 高さ）
TOTE_PRINT_AREA = (99.2126, 14.1732, 892.9134 - 99.2126, 722.835 - 14.1732)
# T シャツ・トートのテンプレートで、画像を置くレイヤー
DESIGN_LAYER = "デザイン"


@dataclass(frozen=True)
class AcrylicImages:
    """アクリル系の入力画像（ファイルのパス）."""

    color: Path
    cutline: Path
    white: Path | None
    # 印刷画像を切り抜くマスクの元画像（``art_mask``）。透明な画素が無い印刷画像では None
    color_mask: Path | None = None


class Job:
    """1 件分の VectorCraft セッションと、よく使う操作."""

    def __init__(self, vc: VectorCraft, workdir: Path) -> None:
        self.vc = vc
        self.workdir = workdir
        self.vc.cmd("color.loadProfile", path=str(ICC_JAPAN_COLOR_2001_COATED))

    # --- 文書 -----------------------------------------------------------------
    def color_settings(self) -> None:
        """Illustrator のカラー設定（日本-一般用途2）に合わせる.

        作業用 CMYK は Japan Color 2001 Coated、マッチング方法は知覚的、黒点補正あり。
        画像の CMYK 変換の色がこの設定で Illustrator と揃う（ΔE00 平均 0.22〜0.85）。
        """
        self.vc.cmd(
            "edit.colorSettings", cmyk=JAPAN_COLOR_2001_COATED, intent="perceptual", bpc=True
        )

    def new_cmyk(self, width: float, height: float) -> None:
        self.vc.cmd("file.new", width=width, height=height, colorMode="cmyk", units="Millimeters")
        self.color_settings()
        self.vc.cmd("edit.assignProfile", cmyk=JAPAN_COLOR_2001_COATED)

    def open(self, path: Path, **opts: Any) -> None:
        self.vc.cmd("document.open", path=str(path), **opts)

    def layers(self) -> list[dict[str, Any]]:
        layers: list[dict[str, Any]] = self.vc.inspect()["layers"]
        return layers

    def layer(self, name: str) -> dict[str, Any] | None:
        return next((layer for layer in self.layers() if layer["name"] == name), None)

    def children(self, layer_name: str) -> list[dict[str, Any]]:
        layer = self.layer(layer_name)
        return (layer or {}).get("children") or []

    def artboard(self) -> dict[str, float]:
        artboard: dict[str, float] = self.vc.inspect()["artboards"][0]
        return artboard

    def new_layer(self, name: str) -> int:
        layer_id: int = self.vc.cmd("layer.new", name=name)["id"]
        return layer_id

    def set_current_layer(self, layer_id: int) -> None:
        self.vc.cmd("layer.setCurrent", id=layer_id)

    def rename_first_layer(self, name: str) -> int:
        layer_id: int = self.layers()[0]["id"]
        self.vc.cmd("layer.setProps", id=layer_id, name=name)
        return layer_id

    # --- オブジェクト -----------------------------------------------------------
    def _place(self, path: Path) -> tuple[int, float, float, float, float]:
        """埋め込みで配置し、(ID, 幅, 高さ, 中心 x, 中心 y) を返す."""
        r = self.vc.cmd("file.place", path=str(path), link=False)
        img: int = r["ids"][0]
        xf = self.vc.node(img)["kind"]["xf"]
        w, h = r["width"], r["height"]
        return img, w, h, xf[4] + w / 2, xf[5] + h / 2

    def place_image(self, path: Path, size_pt: float, center: tuple[float, float]) -> int:
        """埋め込みで配置し、縦横 ``size_pt`` に変形して ``center`` に中心を合わせる."""
        img, w, h, icx, icy = self._place(path)
        sx, sy = size_pt / w, size_pt / h
        self.vc.cmd(
            "object.transform",
            ids=[img],
            matrix=[sx, 0, 0, sy, center[0] - sx * icx, center[1] - sy * icy],
        )
        return img

    def place_image_fit(
        self, path: Path, box: tuple[float, float, float, float], margin: float
    ) -> None:
        """``box``（x, y, 幅, 高さ）に余白 ``margin`` で縦横比を保って収め、中央に置く."""
        img, w, h, icx, icy = self._place(path)
        x, y, bw, bh = box
        s = min((bw - 2 * margin) / w, (bh - 2 * margin) / h)
        cx, cy = x + bw / 2, y + bh / 2
        self.vc.cmd(
            "object.transform", ids=[img], matrix=[s, 0, 0, s, cx - s * icx, cy - s * icy]
        )

    def trace(self, img: int, params: dict[str, Any]) -> None:
        self.vc.cmd("imageTrace.makeAndExpand", id=img, params=params)

    def ungroup_all(self, layer_name: str) -> None:
        while True:
            groups = [
                c["id"] for c in self.children(layer_name) if c["kind"] in ("Group", "Clip Group")
            ]
            if not groups:
                return
            self.vc.cmd("select.set", ids=groups)
            self.vc.cmd("object.ungroup")

    def release_compounds(self, layer_name: str) -> None:
        comps = [c["id"] for c in self.children(layer_name) if c["kind"] == "Compound Path"]
        if comps:
            self.vc.cmd("select.set", ids=comps)
            self.vc.cmd("object.compoundPath.release")

    def make_single_compound(self, layer_name: str) -> int:
        """レイヤーの中身を複合パス 1 つにまとめ、その ID を返す."""
        self.ungroup_all(layer_name)
        kids = self.children(layer_name)
        if not kids:
            raise GenerationError(f"{layer_name}: nothing was traced")
        if not (len(kids) == 1 and kids[0]["kind"] == "Compound Path"):
            self.vc.cmd("select.set", ids=[c["id"] for c in kids])
            self.vc.cmd("object.compoundPath.make")
        comp_id: int = self.children(layer_name)[0]["id"]
        return comp_id

    def paths(self, layer_name: str) -> list[tuple[int, G.SubPath]]:
        return [
            (c["id"], G.subpaths_of_node(self.vc.node(c["id"]))[0])
            for c in self.children(layer_name)
            if c["kind"] == "Path"
        ]

    def set_path(self, path_id: int, sp: G.SubPath) -> None:
        self.vc.cmd(
            "path.setAnchors",
            id=path_id,
            subpaths=[{"anchors": G.to_vc_anchors(sp), "closed": sp.closed}],
        )

    def create_path(self, sp: G.SubPath) -> int:
        path_id: int = self.vc.cmd(
            "path.create", anchors=G.to_vc_anchors(sp), closed=sp.closed
        )["id"]
        return path_id

    def stroke_only(self, ids: list[int], weight: float) -> None:
        self.vc.cmd("paint.setFill", ids=ids, none=True)
        self.vc.cmd("paint.setStroke", ids=ids, color=K100)
        self.vc.cmd("stroke.set", ids=ids, weight=weight)

    def fill_only(self, ids: list[int]) -> None:
        self.vc.cmd("paint.setFill", ids=ids, color=K100)
        self.vc.cmd("paint.setStroke", ids=ids, none=True)

    def delete(self, ids: list[int]) -> None:
        if ids:
            # ids を渡しても、選択が無いと消えない
            self.vc.cmd("select.set", ids=ids)
            self.vc.cmd("edit.clear", ids=ids)

    def move_all(self, layer_names: Iterable[str], matrix: list[float]) -> None:
        ids = [c["id"] for name in layer_names for c in self.children(name)]
        if ids:
            self.vc.cmd("object.transform", ids=ids, matrix=matrix, strokes=False)

    def layer_bounds_up(self, layer_name: str) -> G.Bounds:
        """レイヤー内のパスの外形（y 上向き）."""
        bs = [
            G.bounds(G.subpaths_of_node(self.vc.node(c["id"])))
            for c in self.children(layer_name)
            if c["kind"] in ("Path", "Compound Path")
        ]
        if not bs:
            raise GenerationError(f"{layer_name}: no paths")
        return G.union_bounds(bs)

    def order_layers(self, names_top_to_bottom: list[str]) -> None:
        # node.move の index は最背面が 0（inspect の並びは最前面が先頭）
        for i, name in enumerate(reversed(names_top_to_bottom)):
            layer = self.layer(name)
            if layer:
                self.vc.cmd("node.move", id=layer["id"], parent=None, index=i)

    def save_ai_cmyk(self, name: str) -> Path:
        """.ai（PDF 互換）で保存する.

        VectorCraft の埋め込み画像は RGB のままなので、PDF 部分の画像は保存時の出力変換で
        Japan Color 2001 Coated の CMYK にする（Illustrator が埋め込み時に行う変換に当たる）。
        """
        path = self.workdir / name
        self.vc.cmd(
            "file.saveAs",
            path=str(path),
            format="ai",
            options={
                "pdfCompatible": True,
                "embedProfiles": True,
                "compress": True,
                "createLayers": True,
                "output": {
                    "conversion": "destination",
                    "destination": JAPAN_COLOR_2001_COATED,
                    "profiles": "destination",
                },
            },
        )
        return path

    def export_pdf(self, name: str) -> Path:
        """Illustrator が実際に書いている PDF に合わせる（レイヤー付き・ICC タグ付き・出力インテントなし）."""
        path = self.workdir / name
        self.vc.cmd(
            "document.exportPdf",
            path=str(path),
            compatibility="1.6",
            createLayers=True,
            preserveEditing=False,
            output={"profiles": "all"},
        )
        return path


# --- アクリル系の共通処理 -------------------------------------------------------


def _canvas_center(job: Job) -> tuple[float, float]:
    ab = job.artboard()
    return (ab["x"] + ab["width"] / 2, ab["y"] + ab["height"] / 2)


def _trace_cutline(job: Job, image: Path, size_pt: float, center: tuple[float, float]) -> None:
    layer_id = job.new_layer("CutLine")
    job.set_current_layer(layer_id)
    img = job.place_image(image, size_pt, center)
    job.trace(img, TRACE_CUTLINE)
    job.ungroup_all("CutLine")
    job.release_compounds("CutLine")


def _white_plate(job: Job, image: Path, size_pt: float, center: tuple[float, float]) -> None:
    """白版: トレース結果を「抜きを穴に持つ K100 の複合パス 1 つ」にし、内側へ 0.1mm 寄せる.

    illustrator-vm の `lib/white_plate.jsx` と同じ形にする。VectorCraft のトレースは
    背景の白ベタも白い抜きパスも作らず、穴付きのパスを返すので、背景の削除は要らない。
    """
    color = job.layer("ColorPrint")
    assert color is not None
    job.set_current_layer(color["id"])
    job.set_current_layer(job.new_layer("White"))
    img = job.place_image(image, size_pt, center)
    job.trace(img, TRACE)
    comp = job.make_single_compound("White")
    job.fill_only([comp])
    job.vc.cmd("select.set", ids=[comp])
    job.vc.cmd("object.path.offsetPath", offset=WHITE_OFFSET_PT, joins="round", miterLimit=4)
    job.delete([comp])
    job.fill_only([job.make_single_compound("White")])


def _clip_to_art(
    job: Job, layer_id: int, image_id: int, mask: Path, size_pt: float, center: tuple[float, float]
) -> None:
    """印刷画像を、マスク画像をトレースした外形のクリッピングマスクで切り抜く（#153）.

    VectorCraft のクリッピンググループは、マスクのパスがグループの最背面の子になる。
    旧形式 .ai には Illustrator のマスク（``q`` 〜 ``Q``）として書かれる（``legacy_ai``）。
    """
    # トレースは別のレイヤーで行い、できた複合パスだけを画像の前面へ移す
    # （make_single_compound はレイヤーの中身をすべてまとめるので、画像と同じレイヤーでは行えない）
    work = job.new_layer("ColorMask")
    job.set_current_layer(work)
    job.trace(job.place_image(mask, size_pt, center), TRACE)
    clip = job.make_single_compound("ColorMask")
    job.vc.cmd("node.move", id=clip, parent=layer_id, index=1)
    job.vc.cmd("layer.delete", id=work)
    job.vc.cmd("select.set", ids=[image_id, clip])
    group: int = job.vc.cmd("object.group")["id"]
    job.vc.cmd("layer.clippingMask.toggle", id=group)
    job.set_current_layer(layer_id)


def _new_acrylic_document(
    job: Job, size_pt: float, height_pt: float, images: AcrylicImages
) -> tuple[float, float]:
    job.new_cmyk(size_pt + 2 * MARGIN_PT, height_pt + 2 * MARGIN_PT)
    center = _canvas_center(job)
    layer_id = job.rename_first_layer("ColorPrint")
    image_id = job.place_image(images.color, size_pt, center)
    if images.color_mask is not None:
        _clip_to_art(job, layer_id, image_id, images.color_mask, size_pt, center)
    return center


def _read_template(
    job: Job, template: Path, layer_name: str | None = None
) -> tuple[list[G.SubPath], dict[str, float]]:
    """テンプレートを開き、（指定があればそのレイヤーの）パスとアートボードを読んで閉じる.

    パスは入れ子（グループ・複合パス）までたどって、サブパス単位で集める。
    裁ち落とし付きのテンプレートがあるので、仕上がり（trim）で開く。
    """
    job.open(template, cropTo="trim")
    artboard = job.artboard()
    out: list[G.SubPath] = []
    for layer in job.layers():
        if layer_name is not None and layer["name"] != layer_name:
            continue
        stack = list(layer.get("children") or [])
        while stack:
            c = stack.pop()
            if c["kind"] in ("Path", "Compound Path"):
                out.extend(G.subpaths_of_node(job.vc.node(c["id"])))
            stack.extend(c.get("children") or [])
    job.vc.cmd("file.close")
    return out, artboard


# --- アクリルキーホルダー（acrylic_keychain_new.jsx） ----------------------------


def acrylic_keychain(job: Job, images: AcrylicImages, mm: int, name: str) -> Path:
    size = mm * MM
    circle = G.find_keyhole_pair(_read_template(job, keyhole_template(mm))[0])
    if circle is None:
        raise GenerationError(f"keyhole circles not found in the {mm}mm template")

    center = _new_acrylic_document(job, size, size, images)
    _trace_cutline(job, images.cutline, size, center)
    paths = job.paths("CutLine")
    sps = G.replace_keyhole([sp for _, sp in paths], circle)
    # キー穴より上は間引かない（キー穴のタブの形を保つ）
    protect = next((G.bounds([sp])[3] - 10 for sp in sps if G.is_small(sp)), None)
    sps = [
        G.smooth_cutline_path(sp, 5, preserve_above_y=protect)
        if len(sp) >= 20 and not G.is_small(sp)
        else sp
        for sp in sps
    ]
    sps = G.enlarge_keyhole_tab(sps, circle.outer_diameter_pt)
    # 計算した形で CutLine を作り直す（Illustrator 版も新しいパスを作って差し替えている）
    job.delete([pid for pid, _ in paths])
    job.stroke_only([job.create_path(sp) for sp in reversed(sps)], 0.5)  # 後に作るほど前面

    if images.white is not None:
        _white_plate(job, images.white, size, center)
    job.order_layers(ACRYLIC_LAYERS)
    job.vc.cmd("artboard.setProps", index=0, x=MARGIN_PT, y=MARGIN_PT, width=size, height=size)

    # タブ込みのカットラインがアートボードに収まるよう縮め、中央に置く（fit_content）
    ab = job.artboard()
    acx, acy = ab["x"] + ab["width"] / 2, -(ab["y"] + ab["height"] / 2)  # 上向き
    b = job.layer_bounds_up("CutLine")
    avail = size - 2 * 0.5 * MM
    s = min(avail / (b[2] - b[0]), avail / (b[1] - b[3]))
    if s < 1.0:
        job.move_all(ACRYLIC_LAYERS, [s, 0, 0, s, acx * (1 - s), -acy * (1 - s)])
    b = job.layer_bounds_up("CutLine")
    dx, dy = acx - (b[0] + b[2]) / 2, acy - (b[1] + b[3]) / 2
    if abs(dx) > 0.01 or abs(dy) > 0.01:
        job.move_all(ACRYLIC_LAYERS, [1, 0, 0, 1, dx, -dy])
    return job.save_ai_cmyk(name)


# --- ステッカー（sticker.jsx） -------------------------------------------------


def sticker(job: Job, images: AcrylicImages, mm: int, name: str) -> Path:
    size = mm * MM
    center = _new_acrylic_document(job, size, size, images)
    color_layer = job.layer("ColorPrint")
    assert color_layer is not None
    _trace_cutline(job, images.cutline, size, center)
    paths = job.paths("CutLine")
    job.stroke_only([pid for pid, _ in paths], 1.0)
    for pid, sp in paths:
        if len(sp) >= 20:
            job.set_path(pid, G.smooth_cutline_path(sp, 5))
    # 白版は使わないが、レイヤー構成を他のアクリル系と揃える（空の White）
    job.set_current_layer(color_layer["id"])
    job.new_layer("White")
    job.order_layers(ACRYLIC_LAYERS)
    job.vc.cmd("artboard.setProps", index=0, x=MARGIN_PT, y=MARGIN_PT, width=size, height=size)
    return job.save_ai_cmyk(name)


# --- アクリルスタンド（acrylic_stand.jsx） ---------------------------------------


def _load_tab(job: Job, mm: int) -> tuple[G.SubPath, float, float]:
    """台座テンプレートの差し込みタブ（アンカー最多のパス）と、タブの深さ・アートボードの高さ."""
    template = stand_tab_template(mm)
    sps, artboard = _read_template(job, template, layer_name="CutLine")
    if not sps:
        raise GenerationError(f"acrylic_stand: no tab path in {template.name}")
    tab = max(sps, key=len)
    depth = G.find_joint_y(tab.A, 0.5) - min(a[1] for a in tab.A)
    return tab, depth, artboard["height"]


def _main_path(job: Job) -> tuple[int, G.SubPath]:
    paths = job.paths("CutLine")
    if not paths:
        raise GenerationError("acrylic_stand: cutline is empty")
    return max(paths, key=lambda p: _area(G.bounds([p[1]])))


def _area(b: G.Bounds) -> float:
    return (b[2] - b[0]) * (b[1] - b[3])


def _extend_base_to_lowest_point(job: Job) -> None:
    """土台の下辺より下に絵柄がはみ出していれば、土台を最下点まで延ばす（ADR-0038）.

    トレース直後（塗りのパス、スムーズ化の前）に呼ぶ。スムーズ化の後では土台の角が丸められ、
    水平な辺として見つからなくなる。
    """
    main_id, main = _main_path(job)
    rect = G.base_extension_rect(main, STAND_BASE_SEARCH_MM * MM)
    if rect is None:
        return
    top_before = G.bounds([main])[1]
    left, top, right, bottom = rect
    corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
    rect_sp = G.SubPath(A=corners, LD=list(corners), RD=list(corners))
    rect_id = job.create_path(rect_sp)
    job.fill_only([rect_id])
    job.vc.cmd("select.set", ids=[main_id, rect_id])
    job.vc.cmd("object.pathfinder.unite")
    job.ungroup_all("CutLine")
    job.release_compounds("CutLine")
    _, merged = _main_path(job)
    if abs(G.bounds([merged])[1] - top_before) > 0.5 or G.bottom_anchor_count(merged) < 2:
        raise GenerationError("acrylic_stand: union of the base extension failed")
    logger.info("acrylic_stand: extended the base by %.2fmm", (top - 1 - bottom) / MM)


def acrylic_stand(job: Job, images: AcrylicImages, mm: int, name: str) -> Path:
    size = mm * MM
    tab, depth, tab_artboard_height = _load_tab(job, mm)
    top_gap = max(tab_artboard_height - size - depth, 0)
    artboard_height = size + depth + top_gap

    center = _new_acrylic_document(job, size, artboard_height, images)
    _trace_cutline(job, images.cutline, size, center)
    _extend_base_to_lowest_point(job)
    paths = job.paths("CutLine")
    job.stroke_only([pid for pid, _ in paths], 0.5)
    for pid, sp in paths:
        if len(sp) >= 20:
            job.set_path(pid, G.smooth_cutline_path(sp, 5, preserve_bottom_edge=True))

    if images.white is not None:
        _white_plate(job, images.white, size, center)
    job.order_layers(ACRYLIC_LAYERS)
    job.vc.cmd(
        "artboard.setProps", index=0, x=MARGIN_PT, y=MARGIN_PT, width=size, height=artboard_height
    )

    # 背景の矩形などを消す: アンカー最多のパス以外で 20 点未満のパス
    paths = job.paths("CutLine")
    main_id, _ = max(paths, key=lambda p: len(p[1]))
    job.delete([pid for pid, sp in paths if pid != main_id and len(sp) < 20])

    # 本体をアートボードに収め、底をタブの深さだけ上げた位置に揃える
    ab = job.artboard()
    ab_bottom = -(ab["y"] + ab["height"])  # 上向き
    acx, acy = ab["x"] + ab["width"] / 2, -(ab["y"] + ab["height"] / 2)
    b = job.layer_bounds_up("CutLine")
    fm = 1 * MM
    s = min((size - 2 * fm) / (b[2] - b[0]), (size - fm) / (b[1] - b[3]))
    if s < 1.0:
        job.move_all(ACRYLIC_LAYERS, [s, 0, 0, s, acx * (1 - s), -acy * (1 - s)])
    b = job.layer_bounds_up("CutLine")
    dx = acx - (b[0] + b[2]) / 2
    dy = (ab_bottom + depth) - b[3]
    if abs(dx) > 0.01 or abs(dy) > 0.01:
        job.move_all(ACRYLIC_LAYERS, [1, 0, 0, 1, dx, -dy])

    main_id, main = max(job.paths("CutLine"), key=lambda p: len(p[1]))
    job.set_path(main_id, G.merge_pedestal_tab(main, tab))
    return job.save_ai_cmyk(name)


# --- T シャツ・トート（tshirt_297x406.jsx / tote_bag_280x250.jsx） ----------------


def _place_on_template(
    job: Job, template: Path, image: Path, box: tuple[float, float, float, float] | None, name: str
) -> Path:
    job.open(template)
    design = job.layer(DESIGN_LAYER)
    # テンプレートの空のレイヤーは PDF 部分に残らないので、無ければ作る
    layer_id = design["id"] if design else job.new_layer(DESIGN_LAYER)
    job.set_current_layer(layer_id)
    if box is None:
        ab = job.artboard()
        box = (ab["x"], ab["y"], ab["width"], ab["height"])
    job.place_image_fit(image, box, TEMPLATE_IMAGE_MARGIN_PT)
    for layer in job.layers():
        if layer["name"] != DESIGN_LAYER:
            job.vc.cmd("layer.setProps", id=layer["id"], locked=False)
            job.vc.cmd("layer.delete", id=layer["id"])
    return job.export_pdf(name)


def tshirt(job: Job, image: Path, name: str) -> Path:
    """アートボードに 1mm の余白で収め、中央に置く."""
    return _place_on_template(job, TSHIRT_TEMPLATE, image, None, name)


def tote_bag(job: Job, image: Path, name: str) -> Path:
    """印刷範囲に 1mm の余白で収め、中央に置く."""
    return _place_on_template(job, TOTE_TEMPLATE, image, TOTE_PRINT_AREA, name)
