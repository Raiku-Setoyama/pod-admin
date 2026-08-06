---
name: implement-requirement
description: 要件 REQ-XXXX を実装し、品質検証を通して Pull Request を作成する。「REQ-0003 を実装して」「この要件をやって」「実装して PR を出して」「次のタスクに着手して」と言われたときは必ずこのスキルを使う。実装作業の入口は常にこのスキルであり、REQ-ID なしで直接コードを書き始めてはいけない。
argument-hint: [REQ-ID]
effort: high
---

# 要件の実装

`$ARGUMENTS` で指定された REQ-XXXX を実装する。**作業 ID は REQ-XXXX であり、GitHub Issue は使わない。**

REQ-ID が渡されていない場合は、着手可能な要件を列挙してユーザーに選んでもらう。

```!
echo "--- 着手可能そうな要件（priority が must/future かつ status が not-started）---"
for f in docs/01-requirements/REQ-*.md; do
  [ -e "$f" ] || continue
  p=$(grep -m1 '^priority:' "$f" | awk '{print $2}')
  s=$(grep -m1 '^status:' "$f" | awk '{print $2}')
  case "$p:$s" in
    must:not-started|future:not-started) echo "$f: $(grep -m1 '^title:' "$f")" ;;
  esac
done
```

```bash
# 着手中（要件を参照する open な PR がある）ものを除外するために確認する
gh pr list --state open --json number,title,body,headRefName
```

## 1. 文脈を読み込む

`docs/01-requirements/REQ-XXXX.md` を読み、そこから次を **必ず** 読む。

- `docs/00-charter/` の非機能要件と制約
- `depends_on` が指す要件（完了しているか、前提が変わっていないか）
- 関連する `docs/02-decisions/ADR-XXXX.md`
- **同じ `area` の既存文書**（下記）

`REQ-XXXX.md` は既に読んでいるので、その `area` の値をそのまま埋めて実行する。

```bash
grep -rlE "^area:[[:space:]]*[\"']?(<要件の area>|common)\b" docs/01-requirements/ docs/02-decisions/
```

同じ領域の要件と決定事項には、この要件に書かれていない前提が入っていることが多い。
命名・エラーの扱い・画面遷移などがそこで既に決まっている。**読まずに実装すると領域内で流儀がぶれる。**

**受入基準は `REQ-XXXX.md` の `## 受入基準` が正本である。** 他のどこにも写しを作らない。

## 2. 着手前に確認する

次のいずれかに当てはまるなら、**実装せずに止まる**。

- 受入基準が曖昧で、複数の解釈が成り立つ
- `priority` が `must` / `future` ではない（採否が決まっていない、またはやらないと決めたもの）
- `status` が `not-started` でも `in-progress` でもない
- `depends_on` の要件が `done` になっていない
- `[NEEDS-DECISION]` が残っている
- 憲章の制約（技術・非機能）と矛盾する
- 要件に書かれていない設計判断が必要になる

止まったときの出口は 2 つ。**どちらもリポジトリの中に残す。** チャットだけで完結させない。

**(a) その場でユーザーに聞けば済む場合** — 次の形式で提示し、回答を得てから着手する。

```markdown
**論点**: <一行>
**選択肢 A**: <案と、それを選んだ場合の帰結>
**選択肢 B**: <案と、それを選んだ場合の帰結>
**推奨**: <どちらか。理由を一行で>
```

回答を得たら、その内容を `REQ-XXXX.md` の受入基準または本文に反映する PR を先に出す。

**(b) 顧客・PM の判断が要る場合** — `_templates/adr.md` から `docs/02-decisions/ADR-XXXX.md` を
`status: proposed` で起票し、**選択肢と弊社推奨を用意する**。`area` は起点の要件から引き継ぐ。
`REQ-XXXX.md` の本文に `[NEEDS-DECISION: ADR-XXXX]` を置く。
これを `docs/` の PR として出して止まる。`/meeting-agenda` が自動で次回議題に載せる。

推測で埋めて進めない。判断は人間の仕事である。

## 3. PR の分け方を決める

**1 要件 = 1 実装 PR が原則である。行数の上限はない。**

実装の都合で分けたほうがよいときだけ分ける。例:

- スキーマ変更・マイグレーションを先に入れ、確認してからロジックを載せたい
- 依存パッケージの追加や大量の機械的置換を、レビュー対象から切り離したい
- 中間状態がそれ自体で動作し、レビュー可能な形になっている

**「行数が多いから」は分割の理由にならない。**
意味のある単位で切られた 1 本の PR は、要件を半分ずつ実装した 2 本より読みやすい。
**中間状態が壊れる分割はしない。** main が動かない状態を経由するくらいなら 1 本で出す。

分けると決めたら、`REQ-XXXX.md` の `## 実装メモ` に計画を書く。

```markdown
## 実装メモ

スキーマ変更を先に確認したいので 2 PR に分ける。
1. テーブル追加とマイグレーション（受入基準 1）
2. API・画面・E2E（受入基準 2, 3, 4）
```

**この判断に人間の承認は要らない。** 実装の都合はエージェントが決めてよい。
ただし**要件そのものを分割するのは別の話**であり、それは `/requirements-refine` の仕事である
（実体が複数の要件だったときだけ行う）。

**1 つの PR が 2 つ以上の要件を実装してはならない。** CI が機械的に拒否する。

## 4. ブランチを切る

```bash
git switch -c feat/REQ-XXXX-short-slug
```

複数 PR に分ける場合も、要件 ID は同じままにする（`feat/REQ-XXXX-schema`, `feat/REQ-XXXX-api` など）。

## 5. 実装する

- 既存のコード規約に従う。`AGENTS.md` のプロジェクト固有セクションを確認する。
- 受入基準の各項目に対応するテストを書く。テストが書けない受入基準は、基準の書き方が悪い。
  `REQ-XXXX.md` 側を直す PR を先に出す。
- 実装中に発見した別の問題は、直さずに `docs/01-requirements/` へ新しい要件を
  `priority: undecided` で起票する。`area` は問題が見つかった場所の領域にする（起点の要件とは限らない）。
  スコープを広げない。**PR 本文のメモだけで済ませない。** マージ後に誰も読み返さない。

## 6. 品質検証（必須）

`/quality-gate` を実行する。静的チェック → `/simplify max` → 静的チェック再実行 → `--seal` の 4 ステップである。

**この手順を飛ばして push しようとすると、PreToolUse フックが拒否する。**

## 7. コミットとプッシュ

```bash
git add -A
git commit -m "feat(scope): 概要

Refs: REQ-XXXX"
git push -u origin feat/REQ-XXXX-short-slug
```

## 8. ドキュメントの状態を更新

同じ PR に含める。

- 満たした受入基準を `[x]` にする
- **すべての受入基準を満たしたなら** `docs/01-requirements/REQ-XXXX.md` の `status` を **`done`** にし、
  `updated` を今日にする（根拠は `AGENTS.md`「status の取りうる値」）。
  一部しか満たしていない場合（複数 PR に分けている途中を含む）は `in-progress` にし、残作業を本文に書く。
  **未チェックの受入基準を残したまま `done` にすると docs-lint が落ちる。**
- 実装により要件の解釈が確定した場合は、本文を明確化する（合意内容を変えるのではなく、曖昧さを解消するだけ）
- 設計上の判断をした場合は ADR を起こす（`status: accepted`。論点ではなく決定なので `proposed` にしない）

ドキュメントを変更したら `/quality-gate` を **やり直す**（ファイル内容が変わったため封が無効になる）。

## 9. PR を作成する

`.github/pull_request_template.md` の項目をすべて埋める。特に:

- `Refs: REQ-XXXX` — **これが唯一のトレーサビリティ記載である。** CI が必須で検証する。
  **要件 ID は 1 つだけ書く。** 2 つ以上書くと CI が落ちる
- 品質検証セクション（`/quality-gate` が指示する形式）
- レビュアーに判断してほしい点を「レビュー観点」に具体的に書く
- 複数 PR に分けている場合は、何本目でありこの PR がどの受入基準を満たすかを書く

```bash
gh pr create --draft --title "[REQ-XXXX] 概要" --body-file /tmp/pr-body.md
```

Draft で作成する。CI が通ってから Ready にする。

## 10. 報告して終わる

**PR をマージしない。** `gh pr merge` は権限設定で拒否される。

ユーザーには次を伝えて終了する。

- PR の URL
- レビューで判断してほしい点（あれば）
- この要件を複数 PR に分けた場合は、残りの本数と次に出す内容
- 実装中に起票した要件・ADR（あれば）
