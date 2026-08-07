#!/usr/bin/env python3
"""push-sheets.py — 生成した CSV を Google スプレッドシートへ反映する。

顧客に「常に最新のシート」を見てもらうための片方向反映です。
**双方向同期はしません。** 競合と巻き戻しの原因になるためです。

顧客のコメントは、管理列より右のシートに書いてもらい、--pull で読み出します。
このスクリプトは管理列（A 列から出力幅まで）しか書き換えないため、
顧客が右側に追記した列は保持されます。

準備:
  1. Google Cloud で Sheets API を有効化し、サービスアカウントを作る
  2. 発行された JSON キーの client_email に、対象スプレッドシートを「編集者」で共有
  3. JSON キーを環境変数 GOOGLE_SERVICE_ACCOUNT_JSON に入れる（中身をそのまま）
  4. スプレッドシート ID を SHEET_ID に入れる

使い方:
  python3 scripts/push-sheets.py --push dist/requirements.csv:要件 dist/pending.csv:検討事項
  python3 scripts/push-sheets.py --pull 検討事項

依存: pip install google-api-python-client google-auth
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_service():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("依存が不足しています: pip install google-api-python-client google-auth",
              file=sys.stderr)
        raise SystemExit(1)

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        print("環境変数 GOOGLE_SERVICE_ACCOUNT_JSON が未設定です", file=sys.stderr)
        raise SystemExit(1)
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def ensure_tab(service, sheet_id: str, title: str) -> None:
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if title in existing:
        return
    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    ).execute()
    print(f"シート '{title}' を作成しました")


def col_letter(n: int) -> str:
    name = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


def push(service, sheet_id: str, csv_path: Path, tab: str) -> None:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        print(f"{csv_path} が空のためスキップします")
        return

    ensure_tab(service, sheet_id, tab)
    width = max(len(r) for r in rows)
    last_col = col_letter(width)

    # 管理列だけを消す。顧客が右側に足した列は残す
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id, range=f"'{tab}'!A:{last_col}",
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"'{tab}'!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()
    print(f"{csv_path} -> '{tab}' に {len(rows) - 1} 行を反映しました（管理列 A:{last_col}）")


def pull(service, sheet_id: str, tab: str) -> None:
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"'{tab}'",
    ).execute()
    rows = result.get("values", [])
    if not rows:
        print("（データなし）")
        return
    writer = csv.writer(sys.stdout)
    for row in rows:
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", nargs="*", default=[], metavar="CSV:タブ名")
    parser.add_argument("--pull", metavar="タブ名")
    parser.add_argument("--sheet-id", default=os.environ.get("SHEET_ID", ""))
    args = parser.parse_args()

    if not args.sheet_id:
        print("スプレッドシート ID を --sheet-id か環境変数 SHEET_ID で指定してください",
              file=sys.stderr)
        return 1

    service = get_service()

    for spec in args.push:
        path_str, _, tab = spec.partition(":")
        if not tab:
            print(f"形式が不正です: {spec}（CSV:タブ名 の形で指定）", file=sys.stderr)
            return 1
        push(service, args.sheet_id, Path(path_str), tab)

    if args.pull:
        pull(service, args.sheet_id, args.pull)

    return 0


if __name__ == "__main__":
    sys.exit(main())
