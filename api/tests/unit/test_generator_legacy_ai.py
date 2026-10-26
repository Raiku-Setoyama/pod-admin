"""旧形式 .ai の書き出しの細部（app/generator/legacy_ai.py）.

全体の構造は tests/generator/test_vectorcraft.py が実際の VectorCraft の出力で確かめている。
"""

import io

import numpy as np
import pytest

from app.generator.legacy_ai import _ps_string, _Raster, _Writer


def test_ps_string_escapes_after_shift_jis_encoding() -> None:
    """2 バイト目が 0x5C の文字（ソ）を、閉じ括弧を逃がすバックスラッシュと取り違えない."""
    assert _ps_string("ソ") == b"\x83\\\\"  # 0x83 0x5C → 0x5C を逃がす
    assert _ps_string("a(b)c\\") == b"a\\(b\\)c\\\\"
    assert _ps_string("～①") == "～①".encode("cp932")  # Shift_JIS に無い記号も ? にしない


@pytest.mark.parametrize("n", [0, 1, 31, 32, 33, 64, 65535, 65536, 65537, 131072, 131073])
def test_raster_size_matches_the_bytes_written(n: int) -> None:
    """%%BeginData に書く長さが、実際に書いた本文と一致する（行・ブロックの境目でも）."""
    pixels = np.arange(n, dtype=np.uint8)
    raster = _Raster(pixels)
    buf = io.BytesIO()
    raster.write_to(buf)

    written = buf.getvalue()
    assert raster.size() == len(written)
    # 1 行 64 文字の 16 進。以前の書き方（文字列で組み立てる）と同じ並び
    hexed = pixels.tobytes().hex().upper()
    expected = "XI\n%" + "\n%".join(hexed[i : i + 64] for i in range(0, len(hexed), 64))
    assert written == expected.encode()


def _square(x: float, y: float, w: float) -> dict[str, object]:
    pts = [[x, y], [x + w, y], [x + w, y + w], [x, y + w]]
    return {"anchors": [{"p": p} for p in pts], "closed": True}


def test_clip_group_is_written_as_an_illustrator_clipping_mask() -> None:
    """#153: クリッピンググループは Illustrator 8 形式のマスク（q … W n … Q）で書く.

    形は Illustrator 2026 自身が Illustrator 8 形式で保存したもの（複合パスのマスク）に合わせてある。
    VectorCraft の文書では、マスクのパスがグループの最初（最背面）の子になる。
    """
    clip = {
        "kind": {
            "type": "compound",
            "children": [
                {"kind": {"type": "path", "path": {"subpaths": [_square(10, 10, 20)]}}},
                {"kind": {"type": "path", "path": {"subpaths": [_square(40, 10, 20)]}}},
            ],
        }
    }
    image = {"kind": {"type": "image", "width": 2, "height": 1, "xf": [10, 0, 0, 10, 0, 0]}}
    native = {
        "document": {
            "artboards": [{"rect": {"x0": 0, "y0": 0, "x1": 100, "y1": 100}}],
            "layers": [
                {
                    "name": "ColorPrint",
                    "kind": {"children": [{"kind": {"type": "group", "clip": True, "children": [clip, image]}}]},
                }
            ],
        }
    }
    text = _Writer(native, [np.zeros((1, 2, 4), dtype=np.uint8)], "t").write().decode("shift_jis")
    layer = text.split("0 A\n", 1)[1].split("LB\n", 1)[0]

    head, raster = layer.split("%AI5_BeginRaster", 1)
    assert head.startswith("q\n*u\n")
    assert head.count("h\nW\nn\n") == 2  # サブパスごとにマスクへ加える
    assert head.rstrip().endswith("*U\n0 O\n0 g\n0 J 0 j 1 w 10 M []0 d\n0 XR\n%AI5_File:")
    assert raster.rstrip().endswith("F\nQ")


def test_plain_group_is_still_written_as_a_group() -> None:
    image = {"kind": {"type": "image", "width": 1, "height": 1, "xf": [1, 0, 0, 1, 0, 0]}}
    native = {
        "document": {
            "artboards": [{"rect": {"x0": 0, "y0": 0, "x1": 10, "y1": 10}}],
            "layers": [{"name": "L", "kind": {"children": [{"kind": {"type": "group", "children": [image]}}]}}],
        }
    }
    text = _Writer(native, [np.zeros((1, 1, 4), dtype=np.uint8)], "t").write().decode("shift_jis")
    layer = text.split("0 A\n", 1)[1].split("LB\n", 1)[0]
    assert layer.startswith("u\n") and layer.rstrip().endswith("U")
    assert "W\nn" not in layer
