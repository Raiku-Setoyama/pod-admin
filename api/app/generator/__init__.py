"""製造データ生成（REQ-0067 / ADR-0039）.

元データの画像から、製造委託先に渡す製造データ（.ai／.pdf）を作る。以前は Windows VM 上の
Adobe Illustrator（illustrator-vm）が作っていたものを、OSS の VectorCraft で同じ手順のまま作る。

**生成はワーカー（``app.worker``）だけが行う。** 依存（VectorCraft の実行ファイル、
numpy / scipy / pypdf）はワーカー用のイメージにだけ入っており、API のイメージには無い。
そのため、**このパッケージの入口（ここ）と ``errors`` だけが軽く、ほかのサブモジュールは重い。**
呼び出し側はここの ``generate`` / ``check_available`` を使う。重い ``runner`` はその中で読み込み、
依存が無いとき（API のイメージ）は ``GeneratorUnavailableError`` にする。

- ``runner``: 1 件作る本体
- ``pipelines``: 商品ごとの VectorCraft の操作（illustrator-vm の ExtendScript の移植）
- ``geometry``: カットラインのパス計算
- ``white_plate``: 白版画像の抜けを埋める
- ``legacy_ai``: Illustrator がレイヤー付きで開ける旧形式（Illustrator 8 形式）の .ai に書き直す
- ``pdf_finish``: T シャツ・トートの PDF を整える
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config import settings
from app.generator.errors import GenerationError, GeneratorUnavailableError

if TYPE_CHECKING:
    from app.utils.mfg_product_mapping import GenerationSpec

__all__ = [
    "GeneratedFile",
    "GenerationError",
    "GeneratorUnavailableError",
    "check_available",
    "generate",
]


@dataclass(frozen=True)
class GeneratedFile:
    """生成した製造データ."""

    filename: str
    content: bytes


def generate(spec: GenerationSpec, images: dict[str, bytes], order_id: str) -> GeneratedFile:
    """製造データを 1 件作る（同期。非同期のコードからは ``asyncio.to_thread`` で呼ぶ）.

    Args:
        spec: ``build_generation_spec`` が作った生成のパラメータ。
        images: レイヤー種別（color / cutline / white / design）→ PNG のバイト列。
        order_id: 出力ファイル名に入れる ID（製造データの ID）。

    Raises:
        GenerationError: この入力からは作れない。
        GeneratorUnavailableError: 生成処理を動かせない（依存が無い・VectorCraft が起動しない・落ちた）。
    """
    try:
        from app.generator import runner
    except ImportError as exc:
        raise GeneratorUnavailableError(f"generator dependencies are not installed: {exc}") from exc
    return runner.generate(
        spec,
        images,
        order_id,
        cli=settings.GENERATOR_VECTORCRAFT_CLI,
        timeout_seconds=settings.GENERATOR_TIMEOUT_SECONDS,
    )


def check_available() -> None:
    """生成処理（VectorCraft）が動くかを確かめる（ワーカーの死活確認）.

    Raises:
        GeneratorUnavailableError: 動かない。
    """
    try:
        from app.generator import runner
    except ImportError as exc:
        raise GeneratorUnavailableError(f"generator dependencies are not installed: {exc}") from exc
    runner.check_available(
        cli=settings.GENERATOR_VECTORCRAFT_CLI, timeout_seconds=settings.GENERATOR_TIMEOUT_SECONDS
    )
