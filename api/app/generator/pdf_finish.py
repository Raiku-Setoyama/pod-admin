"""VectorCraft が書いた PDF を、Illustrator で開いたときに従来のデータと同じに見えるよう整える.

T シャツ・トートの製造データ（PDF）に使う。

1. レイヤーごとの目印（x = -32000pt にある空のクリップパス）を取り除く。
   VectorCraft は各レイヤーの描画の先頭に ``q -32000 n m -31999 n l -31999 n l h W n Q`` を書く。
   印刷には影響しないが、Illustrator で開くと幅 11m を超える空のグループになり、
   全選択やアートボードの調整で邪魔になる。この命令列だけを消す。
2. 埋め込みの sRGB プロファイルを、標準の「sRGB IEC61966-2.1」に差し替える。
   VectorCraft は内部では sRGB IEC61966-2.1 として扱うが、書き出す ICC は自前で生成した
   説明名「sRGB」のもので、Illustrator のドキュメント情報に「sRGB」と出る
   （製造委託先の指摘、2026-10-09）。どちらも sRGB なので、画像の数値は変えずにプロファイルだけを入れ替える。
"""

from __future__ import annotations

import io
import re
import struct
from collections.abc import Iterator

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, StreamObject

_MARKER = re.compile(
    rb"q\s+-32000\s+[-\d.]+\s+m\s+-31999\s+[-\d.]+\s+l\s+-31999\s+[-\d.]+\s+l\s+h\s+W\s+n\s+Q\s*"
)
_VECTORCRAFT_SRGB_DESC = "sRGB"


def icc_description(data: bytes) -> str | None:
    """ICC v2 プロファイルの説明名（desc タグ）。ICC でなければ None."""
    if len(data) < 132 or data[36:40] != b"acsp":
        return None
    for i in range(struct.unpack(">I", data[128:132])[0]):
        sig, off, _ = struct.unpack(">4sII", data[132 + 12 * i : 144 + 12 * i])
        if sig == b"desc" and data[off : off + 4] == b"desc":
            n = struct.unpack(">I", data[off + 8 : off + 12])[0]
            return data[off + 12 : off + 12 + n].rstrip(b"\0").decode("latin-1")
    return None


def _content_streams(resources_owner: DictionaryObject) -> Iterator[StreamObject]:
    """ページとフォーム XObject の描画命令のストリームを、入れ子までたどって返す."""
    contents = resources_owner.get("/Contents")
    if contents is not None:
        contents = contents.get_object()
        if isinstance(contents, ArrayObject):
            yield from (c.get_object() for c in contents)
        else:
            yield contents
    resources = resources_owner.get("/Resources")
    if resources is None:
        return
    for ref in resources.get_object().get("/XObject", {}).values():
        xobj = ref.get_object()
        if xobj.get("/Subtype") == "/Form":
            yield xobj
            yield from _content_streams(xobj)


def _icc_streams(resources_owner: DictionaryObject) -> Iterator[StreamObject]:
    """画像と色空間が参照する ICC プロファイルのストリーム."""
    resources = resources_owner.get("/Resources")
    if resources is None:
        return
    resources = resources.get_object()
    spaces = [cs.get_object() for cs in resources.get("/ColorSpace", {}).values()]
    for ref in resources.get("/XObject", {}).values():
        xobj = ref.get_object()
        if xobj.get("/Subtype") == "/Image" and "/ColorSpace" in xobj:
            spaces.append(xobj["/ColorSpace"].get_object())
        elif xobj.get("/Subtype") == "/Form":
            yield from _icc_streams(xobj)
    for cs in spaces:
        if isinstance(cs, ArrayObject) and len(cs) == 2 and cs[0] == "/ICCBased":
            yield cs[1].get_object()


def finish_pdf(pdf: bytes, srgb_icc: bytes) -> bytes:
    """目印のパスを消し、sRGB プロファイルを標準のものに差し替えた PDF を返す."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    for page in writer.pages:
        for stream in _content_streams(page):
            data = stream.get_data()
            cleaned = _MARKER.sub(b"", data)
            if cleaned != data:
                stream.set_data(cleaned)
        for stream in _icc_streams(page):
            if icc_description(stream.get_data()) == _VECTORCRAFT_SRGB_DESC:
                stream.set_data(srgb_icc)
                # 標準のプロファイルの既定値（0〜1）と同じなので消す
                stream.pop(NameObject("/Range"), None)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
