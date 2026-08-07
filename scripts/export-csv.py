#!/usr/bin/env python3
"""export-csv.py — 要件・検討事項・決定事項・不具合を顧客向けの表形式で出力する。

使い方:
    python3 scripts/export-csv.py                # dist/ に全部出す
    python3 scripts/export-csv.py --kind pending # 検討事項のみ
    python3 scripts/export-csv.py --internal     # 社内用（内部項目も含める）

出力は UTF-8 BOM 付き。Excel でそのまま開いても日本語が化けない。
Google スプレッドシートはファイル > インポート でそのまま読める。

顧客向け（既定）ではステータスなどを日本語に訳し、内部管理用の項目を落とす。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from _exports import BUILDERS

DOCS = Path("docs")
OUT = Path("dist")


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig = BOM 付き。これがないと Excel で日本語が文字化けする
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=list(BUILDERS) + ["all"], default="all")
    parser.add_argument("--internal", action="store_true", help="内部項目も含めて出力する")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    if not DOCS.exists():
        print("docs/ が見つかりません。リポジトリのルートで実行してください。", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    kinds = list(BUILDERS) if args.kind == "all" else [args.kind]
    suffix = "-internal" if args.internal else ""

    for kind in kinds:
        label, _sheet, builder = BUILDERS[kind]
        header, rows = builder(client=not args.internal)
        target = out_dir / f"{kind}{suffix}.csv"
        write_csv(target, header, rows)
        print(f"{label}: {len(rows)} 件 -> {target}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
