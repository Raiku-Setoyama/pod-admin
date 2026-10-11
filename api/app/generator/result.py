"""生成結果の型（重い依存を読み込まない。API のプロセスからも import できる）."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedFile:
    """生成した製造データ."""

    filename: str
    content: bytes
