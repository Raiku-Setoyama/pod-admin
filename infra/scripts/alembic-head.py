#!/usr/bin/env python3
"""alembic のマイグレーション一式から head リビジョンを求める。

移送先のスキーマがコードに追いついているかを、migrate-data.sh が判定するために使う。
**件数の突合ではこれを検出できない。** 移送元のコード世代が古ければダンプの
スキーマも古く、移送先では新しいコードが存在しない列を触って 500 になる
（REQ-0054 で実際に踏んだ。突合は通っていた）。

**正規表現で読まない。** `down_revision` は文字列とは限らず、マージ
マイグレーションではタプルになる。素朴な正規表現はタプルを読み落とし、
**マージ済みのリビジョンをヘッドだと誤検出する**（実際に誤検出した）。
Python のソースなので ast で読む。

    usage: alembic-head.py <versions ディレクトリ>
    出力  : ヘッドが 1 つならその ID。複数なら MULTI:<id>,<id>...
"""

from __future__ import annotations

import ast
import pathlib
import sys


def _literals(node: ast.AST) -> list[str]:
    """代入の右辺から、リビジョン ID の文字列をすべて拾う。"""
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (tuple, list)):
        return [v for v in value if isinstance(v, str)]
    return []


def main() -> int:
    versions = pathlib.Path(sys.argv[1])
    if not versions.is_dir():
        print(f"ディレクトリがありません: {versions}", file=sys.stderr)
        return 1

    revisions: set[str] = set()
    parents: set[str] = set()

    for path in sorted(versions.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            # `revision = "x"` と `revision: str = "x"` の両方を受ける。
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            else:
                continue
            if node.value is None:
                continue
            if "revision" in names:
                revisions.update(_literals(node.value))
            if "down_revision" in names:
                parents.update(_literals(node.value))

    heads = revisions - parents
    if not heads:
        print("ヘッドが見つかりません", file=sys.stderr)
        return 1
    # **多重ヘッドはそれ自体が事故である。** 本番の起動が crash する
    # （AGENTS.md「Alembic のマイグレーションは多重ヘッドに注意」）。
    print(sorted(heads)[0] if len(heads) == 1 else "MULTI:" + ",".join(sorted(heads)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
