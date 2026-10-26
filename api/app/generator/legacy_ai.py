"""VectorCraft の .ai を、Illustrator がレイヤー付きで開ける旧形式（Illustrator 8 形式）に書き直す.

VectorCraft の .ai は「PDF＋VectorCraft 独自の文書」で、Illustrator で開くとレイヤーが 1 枚にまとまる。
製造委託先はレイヤー（CutLine / ColorPrint / White）を分けて作業するので、そのままでは渡せない（ADR-0039）。

Illustrator 8 形式は PostScript ベースのテキストで、Illustrator 2026 でもレイヤー・CMYK・複合パス・
埋め込み画像を保ったまま開ける。書式は Illustrator 自身が書いた Illustrator 8 形式に合わせてある。

- 入力: VectorCraft が保存した .ai。埋め込みの VectorCraft 文書（パス・レイヤー・アートボード）と、
  PDF 部分の画像（保存時の出力変換で Japan Color 2001 Coated の CMYK になったもの）を使う
- 出力: Illustrator 8 形式の .ai（日本語は Shift_JIS）

Illustrator 8 形式そのものの制約:

- 画像の透明（アルファ）を持てない。透明部分はインキ 0%（紙白）に合成する。印刷するインキの量は同じ。
  背景を透過して見せるため、アクリル系の印刷画像は絵の外形のクリッピングマスクで切り抜いてある
  （``pipelines._clip_to_art``、BUG-0004）。マスクは Illustrator と同じ ``q`` 〜 ``Q`` で書く
- ICC プロファイルを埋め込めない。CMYK の数値はそのまま
"""

from __future__ import annotations

import binascii
import io
import json
import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import numpy.typing as npt
from pypdf import PdfReader
from pypdf.generic import DictionaryObject, StreamObject

from app.generator.errors import GenerationError

# VectorCraft が .ai に埋め込む自身の文書の名前
NATIVE_ATTACHMENT = "vectorcraft-editing.vectorcraft"

_LAYER_COLORS = [(79, 128, 255), (255, 79, 79), (79, 255, 79), (79, 79, 255), (255, 170, 0)]

Cmyk = tuple[float, float, float, float]


def _n(v: float) -> str:
    """PostScript の数値（小数 4 桁、末尾の 0 を落とす）."""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _ps_string(s: str) -> bytes:
    """PostScript の文字列の中身。**Shift_JIS にしてからバイト単位で逃がす**.

    文字のまま逃がしてから変換すると、2 バイト目が 0x5C（バックスラッシュ）の文字（ソ・表・能 など）が
    閉じ括弧を逃がしてしまい、文字列が閉じなくなる。cp932 は Shift_JIS に ～ や ① などを足したもの
    """
    raw = s.encode("cp932", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _odd_ceil(v: float) -> int:
    c = math.ceil(v)
    return c if c % 2 == 1 else c + 1


def _pdf_images(resources: DictionaryObject) -> Iterator[StreamObject]:
    """ページ（とその中のフォーム XObject）にある画像を、描画される順に返す."""
    xobjects = resources.get("/XObject")
    if xobjects is None:
        return
    for ref in cast(DictionaryObject, xobjects.get_object()).values():
        obj = cast(StreamObject, ref.get_object())
        if obj.get("/Subtype") == "/Image":
            yield obj
        elif "/Resources" in obj:
            yield from _pdf_images(cast(DictionaryObject, obj["/Resources"].get_object()))


def _cmyk_pixels(image: StreamObject) -> npt.NDArray[np.uint8]:
    """PDF 部分の画像を CMYK の配列にし、透明部分を紙白（インキ 0%）に合成する."""
    width, height = int(cast(Any, image["/Width"])), int(cast(Any, image["/Height"]))
    data = image.get_data()
    if len(data) != width * height * 4:
        raise GenerationError("embedded image is not 8-bit CMYK (check the output conversion)")
    arr = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4)
    smask = image.get("/SMask")
    if smask is not None:
        alpha_data = cast(StreamObject, smask.get_object()).get_data()
        alpha = np.frombuffer(alpha_data, dtype=np.uint8).reshape(height, width)
        # 大きな画像で一時配列を増やさないよう、16 ビットの配列 1 つの中で計算する
        wide = arr.astype(np.uint16)
        wide *= alpha[..., None]
        wide //= 255
        arr = wide.astype(np.uint8)
    return arr


@dataclass(frozen=True)
class _Raster:
    """画像の本文（16 進）。巨大なので文字列にせず、書き出すときに直接バイト列へ書く."""

    pixels: npt.NDArray[np.uint8]

    # 1 行 64 文字（32 バイト）
    _ROW = 32

    def size(self) -> int:
        """本文（``XI`` と各行）のバイト数."""
        n = self.pixels.size
        rows = -(-n // self._ROW)
        return len(b"XI\n%") + 2 * n + len(b"\n%") * max(rows - 1, 0)

    def write_to(self, buf: io.BytesIO) -> None:
        data = memoryview(np.ascontiguousarray(self.pixels)).cast("B")
        buf.write(b"XI\n%")
        block = self._ROW * 2048  # 行の区切りを入れながら、64KB ずつ 16 進にする
        for start in range(0, len(data), block):
            if start:
                buf.write(b"\n%")
            hexed = binascii.hexlify(data[start : start + block]).upper()
            step = self._ROW * 2
            buf.write(b"\n%".join(hexed[i : i + step] for i in range(0, len(hexed), step)))


class _Writer:
    def __init__(self, native: dict[str, Any], images: list[npt.NDArray[np.uint8]], title: str):
        self._native = native
        self._images = iter(images)
        self._title = title
        self._out: list[str | bytes | _Raster] = []

    # VectorCraft は y 下向き。Illustrator 8 形式は y 上向き
    @staticmethod
    def _pt(p: list[float]) -> tuple[float, float]:
        return p[0], -p[1]

    @staticmethod
    def _cmyk(paint: dict[str, Any] | None) -> Cmyk | None:
        if not paint or paint.get("type") != "solid":
            return None
        c = paint["color"]
        if c["model"] == "cmyk":
            return c["c"], c["m"], c["y"], c["k"]
        if c["model"] == "gray":
            return 0.0, 0.0, 0.0, 1 - c.get("gray", c.get("g", 0))
        raise GenerationError(f"unexpected color model in a CMYK document: {c['model']}")

    def _paint(self, node: dict[str, Any]) -> tuple[bool, bool]:
        fill: Cmyk | None = None
        stroke: Cmyk | None = None
        width = 1.0
        for item in (node.get("appearance") or {}).get("items", []):
            if item["kind"] == "fill":
                fill = self._cmyk(item["paint"])
            elif item["kind"] == "stroke":
                stroke = self._cmyk(item["paint"])
                width = item.get("width", 1.0)
        if fill:
            self._out += ["0 O", " ".join(_n(v) for v in fill) + " k"]
        if stroke:
            self._out += ["0 R", " ".join(_n(v) for v in stroke) + " K"]
        self._out += [f"0 J 0 j {_n(width)} w 10 M []0 d", "0 XR"]
        return fill is not None, stroke is not None

    @staticmethod
    def _op(filled: bool, stroked: bool) -> str:
        # 小文字 = 閉じたパス。f 塗り / s 線 / b 両方 / n どちらも無し
        return "b" if filled and stroked else "f" if filled else "s" if stroked else "n"

    def _end_op(self, node: dict[str, Any], clip: bool) -> str:
        """パスの書式（色・線の設定）を書き、サブパスの終わり方を返す.

        マスクのパスは、Illustrator が書くとおり閉じて（h）マスクに加え（W）、塗らない（n）。
        VectorCraft はマスクにしたパスの塗りと線を外すので、書くのは線の設定の行だけになる。
        """
        painted = self._paint(node)
        return "h\nW\nn" if clip else self._op(*painted)

    def _subpath(self, sp: dict[str, Any], op: str) -> None:
        anchors = sp["anchors"]
        x, y = self._pt(anchors[0]["p"])
        self._out.append(f"{_n(x)} {_n(y)} m")
        segs = list(zip(anchors, anchors[1:], strict=False))
        if sp.get("closed"):
            segs.append((anchors[-1], anchors[0]))
        for a, b in segs:
            o = self._pt(a.get("out") or a["p"])
            i = self._pt(b.get("in") or b["p"])
            p = self._pt(b["p"])
            if o == self._pt(a["p"]) and i == p:
                self._out.append(f"{_n(p[0])} {_n(p[1])} L")
            else:
                self._out.append(
                    f"{_n(o[0])} {_n(o[1])} {_n(i[0])} {_n(i[1])} {_n(p[0])} {_n(p[1])} C"
                )
        self._out.append(op if sp.get("closed") else op.upper())

    def _node(self, node: dict[str, Any], *, clip: bool = False) -> None:
        """``clip``: クリッピングマスクのパスとして書く（塗りも線も無く、サブパスごとにマスクへ加える）."""
        kind = node["kind"]
        t = kind["type"]
        if clip and t not in ("path", "compound"):
            raise GenerationError(f"unsupported clipping path in the document: {t}")
        if t == "path":
            subpaths = kind["path"]["subpaths"]
            # サブパスが複数あるパスは複合パスとして書く。別々に書くと穴が塗りつぶされる
            compound = len(subpaths) > 1
            if compound:
                self._out.append("*u")
            op = self._end_op(node, clip)
            for sp in subpaths:
                self._subpath(sp, op)
            if compound:
                self._out.append("*U")
        elif t == "compound":
            self._out.append("*u")
            op = self._end_op(node, clip)
            for child in kind["children"]:
                for sp in child["kind"]["path"]["subpaths"]:
                    self._subpath(sp, op)
            self._out.append("*U")
        elif t == "group" and kind.get("clip"):
            # クリッピンググループ。VectorCraft ではマスクのパスが最初（最背面）の子になる。
            # Illustrator 8 形式では q 〜 Q で囲み、マスクのパスを先頭に書く（BUG-0004）
            mask, *rest = kind["children"]
            self._out.append("q")
            self._node(mask, clip=True)
            for child in rest:
                self._node(child)
            self._out.append("Q")
        elif t == "group":
            self._out.append("u")
            for child in kind["children"]:
                self._node(child)
            self._out.append("U")
        elif t == "image":
            self._image(kind)
        else:
            raise GenerationError(f"unsupported object in the document: {t}")

    def _image(self, kind: dict[str, Any]) -> None:
        pixels = next(self._images, None)
        if pixels is None:
            raise GenerationError("the document has more images than its PDF part")
        xf = kind["xf"]
        w, h = kind["width"], kind["height"]
        if pixels.shape[:2] != (h, w):
            raise GenerationError("image size differs between the document and its PDF part")
        tx, ty = self._pt([xf[4], xf[5]])
        m = f"[ {_n(xf[0])} 0 0 {_n(xf[3])} {_n(tx)} {_n(ty)} ]"
        body = _Raster(pixels)
        self._out += [
            "0 O",
            "0 g",
            "0 J 0 j 1 w 10 M []0 d",
            "0 XR",
            "%AI5_File:",
            "%AI5_BeginRaster",
            "() 1 XG",
            f"{m} {w} {h} 0 Xh",
            f"{m} 0 0 {w} {h} {w} {h} 8 4 0 0 0 0",
            f"%%BeginData: {body.size() + 1}",  # 本文（ASCII）と、その後ろの改行 1 つのバイト数
            body,
            "%%EndData",
            "XH",
            "%AI5_EndRaster",
            "F",
        ]

    def write(self) -> bytes:
        doc = self._native["document"]
        ab = doc["artboards"][0]["rect"]
        left, right = ab["x0"], ab["x1"]
        top, bottom = -ab["y0"], -ab["y1"]
        w, h = right - left, top - bottom
        # Illustrator は旧形式を開くとき、アートボード左上を「TemplateBox の中心 − 幅を切り上げた奇数 / 2」
        # に置く（50/70/100mm の各サイズで実測して一致）。狙いの位置になるよう逆算する
        cx, cy = left + _odd_ceil(w) / 2, top - _odd_ceil(h) / 2
        layers = doc["layers"]  # 背面から
        self._out = [
            "%!PS-Adobe-3.0",
            "%%Creator: Adobe Illustrator(R) 8.0",
            "%%AI8_CreatorVersion: 8.0",
            "%%For: (pod-admin) ()",
            b"%%Title: (" + _ps_string(self._title) + b")",
            f"%%BoundingBox: {int(left)} {int(bottom)} {int(right) + 1} {int(top) + 1}",
            f"%%HiResBoundingBox: {_n(left)} {_n(bottom)} {_n(right)} {_n(top)}",
            "%%DocumentProcessColors: Cyan Magenta Yellow Black",
            "%AI5_FileFormat 4.0",
            "%AI3_ColorUsage: Color",
            "%AI7_ImageSettings: 0",
            f"%AI3_TemplateBox: {_n(cx)} {_n(cy)} {_n(cx)} {_n(cy)}",
            f"%AI3_TileBox: {_n(cx - 306)} {_n(cy - 396)} {_n(cx + 306)} {_n(cy + 396)}",
            "%AI3_DocumentPreview: None",
            f"%AI5_ArtSize: {_n(w)} {_n(h)}",
            "%AI5_RulerUnits: 1",
            "%AI5_ArtFlags: 0 0 0 1 0 0 1 0 0",
            "%AI5_TargetResolution: 800",
            f"%AI5_NumLayers: {len(layers)}",
            "%%EndComments",
            "%%BeginProlog",
            "%%EndProlog",
            "%%BeginSetup",
            "%%EndSetup",
        ]
        for i, layer in enumerate(layers):
            r, g, b = _LAYER_COLORS[i % len(_LAYER_COLORS)]
            printable = 1 if layer["kind"].get("printable", True) else 0
            self._out += [
                "%AI5_BeginLayer",
                f"1 1 1 {printable} 0 0 1 {i} {r} {g} {b} 0 50 Lb",
                b"(" + _ps_string(layer["name"]) + b") Ln",
                "0 A",
            ]
            for child in layer["kind"]["children"]:
                self._node(child)
            self._out += ["LB", "%AI5_EndLayer--"]
        if next(self._images, None) is not None:
            raise GenerationError("the PDF part has images that are not in the document")
        self._out += ["%%PageTrailer", "gsave annotatepage grestore showpage", "%%Trailer", "%%EOF"]
        # 1 行ずつ書く。日本語は Shift_JIS（Illustrator 8 日本語版の書き方）。画像の本文は直接書き、
        # 巨大な文字列の写し（16 進・大文字・連結・変換）を作らない
        buf = io.BytesIO()
        for line in self._out:
            if isinstance(line, _Raster):
                line.write_to(buf)
            elif isinstance(line, bytes):
                buf.write(line)
            else:
                buf.write(line.encode("shift_jis", errors="replace"))
            buf.write(b"\n")
        return buf.getvalue()


def to_illustrator8(vectorcraft_ai: bytes, title: str) -> bytes:
    """VectorCraft の .ai（バイト列）を Illustrator 8 形式の .ai（バイト列）にする."""
    reader = PdfReader(io.BytesIO(vectorcraft_ai))
    attached = reader.attachments.get(NATIVE_ATTACHMENT)
    if not attached:
        raise GenerationError(f"{NATIVE_ATTACHMENT} is not embedded in the VectorCraft .ai")
    native = json.loads(attached[0])
    resources = cast(DictionaryObject, reader.pages[0]["/Resources"].get_object())
    images = [_cmyk_pixels(im) for im in _pdf_images(resources)]
    return _Writer(native, images, title).write()
