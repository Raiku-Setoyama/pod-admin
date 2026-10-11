"""旧形式 .ai の書き出しの細部（app/generator/legacy_ai.py）.

全体の構造は tests/generator/test_vectorcraft.py が実際の VectorCraft の出力で確かめている。
"""

import io

import numpy as np
import pytest

from app.generator.legacy_ai import _ps_string, _Raster


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
