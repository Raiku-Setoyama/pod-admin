---
name: client-export
description: 顧客に提出する資料一式を生成する。要件・検討事項・決定事項・不具合を 4 タブの Excel（プロジェクト管理表）と CSV で、要件定義書を 1 つの Word 文書として出力する。「顧客向けの資料を作って」「要件定義書を出して」「要件をスプレッドシートにして」「4 タブの Excel を出して」「客先に提出する資料」「検討事項の一覧が欲しい」「不具合一覧を出して」と言われたときは必ずこのスキルを使う。定例の前や検収前にも実行する。
argument-hint: [review | agreed]
allowed-tools: Bash(python3 scripts/export-csv.py:*) Bash(python3 scripts/export-xlsx.py:*) Bash(python3 scripts/export-requirements.py:*) Bash(python3 scripts/docs-lint.py:*) Bash(git tag:*) Bash(git log:*)
---

# 顧客向け資料の生成

`docs/` が正本で、顧客向け資料はそこからの**投影**。資料を直接編集しない。
修正が必要なら `docs/` を直して再生成する。

`$ARGUMENTS` が `agreed` なら合意版、`review` または省略ならレビュー版。

## 1. 出す前に整合性を確認する

```bash
python3 scripts/docs-lint.py
```

**エラーが出ている状態で顧客に出さない。** 参照切れやステータス矛盾がそのまま資料に出る。

警告のうち次の 2 つは、資料の内容に直接影響するので必ず確認する。

- `priority が future ですが受入基準がありません` → 次期フェーズの範囲が顧客に伝わらない
- `未決事項 ADR-XXXX が残っています` → 要件定義書の「未決事項」章に載る（載ること自体は正常）

## 2. 生成する

```bash
python3 scripts/export-csv.py
python3 scripts/export-xlsx.py
python3 scripts/export-requirements.py --docx
```

合意版の場合:

```bash
python3 scripts/export-requirements.py --agreed-only --docx
```

出力は `dist/` に入る。`dist/` は `.gitignore` されているのでコミットされない。

| ファイル | 内容 | 用途 |
|---|---|---|
| `dist/プロジェクト管理表.xlsx` | 要件・検討事項・決定事項・不具合の 4 タブ | 1 ファイルで顧客に手渡す一覧 |
| `dist/requirements.csv` | 要件一覧（`must` / `future`）。実装状況の列を含む | 進捗とチェックリストを兼ねる |
| `dist/pending.csv` | 検討事項一覧（`undecided` / `wont`）。判断内容と判断日を含む | 顧客の判断待ちと見送り記録 |
| `dist/decisions.csv` | 決定事項・論点（ADR）一覧 | 決定の履歴と判断待ちの論点 |
| `dist/defects.csv` | 不具合一覧（`docs/05-defects/`）。対象要件と修正状況を含む | 瑕疵対応の状況 |
| `dist/要件定義書.md` | 結合済み要件定義 | 中間生成物 |
| `dist/要件定義書.docx` | Word 版 | 顧客提出・検収用 |

**要件タブと検討事項タブは同じ `docs/01-requirements/` から出る。** 違いは `priority` だけで、
合意済み（`must` / `future`）が要件、未判断・見送り（`undecided` / `wont`）が検討事項になる。
旧モデルのように 2 つの一覧を ID で突き合わせる必要はない。

**不具合タブだけは別のディレクトリ（`docs/05-defects/`）から出る。**
要件定義書には載らない。**不具合は要件ではないので、検収の対象文書に混ぜない。**
要件タブの「未修正の不具合」列が、完了した要件のうち今どれが壊れているかを示す
（`defect_of` の逆引きで導出。要件を `done` のまま戻さないぶん、この列が実態を担保する）。

`プロジェクト管理表.xlsx` は 4 つの CSV と同じ列を 1 つの Excel（要件 / 検討事項 / 決定事項 / 不具合タブ）に束ねたもの。
Google スプレッドシート連携（手順 4）は CSV を使うので、Excel はメール等で 1 ファイルを手渡すときに使う。
`--internal` を付けると内部項目も含む `プロジェクト管理表-internal.xlsx` が出る。

## 3. 生成物を確認する

**必ず中身を読んでから渡す。** 特に次を見る。

- `dist/要件定義書.md` の「未決事項」章 — 顧客に見えて問題ない書き方か
- CSV の「判断内容」列 — 見送った理由が顧客に対して失礼な表現になっていないか
- 社内向けメモが `## 実装メモ` から漏れていないか（要件本文はそのまま要件定義書に出る）
- **「領域」列に「未分類」が残っていないか** — 顧客資料に「未分類」が並ぶのは内部の整理不足である。
  残っていたら資料を出す前に `/docs-audit` で潰す
- **要件定義書の節（領域）が顧客の言葉になっているか** — `docs/00-charter/areas.md` の
  「表示名」列がそのまま章立てに出る。開発側の用語になっていたら `areas.md` を直して再生成する

顧客に出すべきでない内容が含まれていたら、**資料ではなく `docs/` 側を直す**。

## 4. Google スプレッドシートへ反映する（設定済みの場合のみ）

```bash
python3 scripts/push-sheets.py \
  --push dist/requirements.csv:要件 dist/pending.csv:検討事項
```

環境変数 `SHEET_ID` と `GOOGLE_SERVICE_ACCOUNT_JSON` が必要。未設定なら CSV を手渡しする。

**顧客がシートに書いたコメントは、管理列より右に書いてもらう。**
このスクリプトは管理列しか書き換えないので、顧客の追記は保持される。
コメントを回収するときは:

```bash
python3 scripts/push-sheets.py --pull 検討事項
```

回収した内容は `/meeting-intake` の入力として扱い、新しい要件として起票する（採否は根拠に応じて提案する）。
**シートを直接 docs に取り込まない。** 経緯が追えなくなる。

## 5. 合意版を確定させる（agreed の場合のみ）

顧客の承認を得たら、その時点の要件定義をタグで固定する。

```bash
git tag -a v1.0-requirements -m "要件定義 合意版 v1.0（YYYY-MM-DD 承認）"
git push origin v1.0-requirements
```

これで「いつ時点の何に合意したか」が機械的に確定する。**受託では追加要件の判別根拠になる。**
タグを打ったことと、その版に含まれる要件の件数を報告する。

## 6. 報告する

生成したファイルのパスと、次の内容を伝える。

- 収録した要件の件数（`must` / `future` の内訳）
- 判断待ちの件数（`undecided` の要件 + `proposed` の ADR）
- 顧客に判断してほしい点（`undecided` の要件がある場合）
