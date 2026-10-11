"""製造データ生成の例外.

呼び出し側（manufacturing_data_service）は、この 2 つで扱いを分ける。

- ``GeneratorUnavailableError``: 生成処理そのものが動かない（実行ファイルが無い・起動しない）。
  入力の誤りではないので、行を failed にせず pending へ戻す（VM に届かなかったときと同じ）。
- ``GenerationError``: この入力では作れない（画像として読めない・タブを合成できない等）。
  何度やっても同じなので failed にする。
  - ``GenerationTimeoutError``: 時間内に終わらなかった。入口の ``generate`` が 1 回だけやり直し、
    それでも終わらなければ failed にする（REQ-0069）。
"""

from __future__ import annotations


class GenerationError(Exception):
    """この入力からは製造データを作れない."""


class GeneratorUnavailableError(Exception):
    """生成処理（VectorCraft）を起動できない."""


class GenerationTimeoutError(GenerationError):
    """生成が時間内に終わらなかった."""
