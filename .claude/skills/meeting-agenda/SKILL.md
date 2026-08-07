---
name: meeting-agenda
description: 前回議事録の未決事項、要件の状態、進行中の PR を読み込んで、次回打ち合わせのアジェンダを生成する。「次回のアジェンダを作って」「明日の MTG の準備」「打ち合わせの議題を用意して」「顧客との定例の準備をしたい」と言われたときは必ずこのスキルを使う。打ち合わせ前の準備は常にこのスキルから始める。
argument-hint: [開催日 YYYY-MM-DD]
allowed-tools: Bash(gh pr list:*) Bash(git log:*) Bash(python3 scripts/docs-lint.py:*)
---

# アジェンダ生成

打ち合わせの時間は顧客の意思決定に使う。**報告に使わない。** アジェンダは「決めてほしいこと」を先頭に置く。

## 1. 現況を集める

```!
echo "--- 採否が未判断の要件 ---"
grep -l "^priority: undecided" docs/01-requirements/REQ-*.md 2>/dev/null | while read f; do
  echo "$f: $(grep -m1 '^title:' "$f")  $(grep -m1 '^area:' "$f")"
done || echo "なし"
echo "--- 決まっていない論点（proposed の ADR）---"
grep -l "^status: proposed" docs/02-decisions/ADR-*.md 2>/dev/null | while read f; do
  echo "$f: $(grep -m1 '^title:' "$f")"
done || echo "なし"
echo "--- ブロッキング判定用 ---"
grep -A3 "判断が出ないと止まるもの" docs/01-requirements/REQ-*.md docs/02-decisions/ADR-*.md 2>/dev/null | grep -v "^--" || echo "なし"
echo "--- 未決参照 ---"
grep -rn "NEEDS-DECISION" docs/ || echo "なし"
echo "--- 実装中の要件 ---"
grep -rl "^status: in-progress" docs/01-requirements/ || echo "なし"
echo "--- 保留中の要件 ---"
grep -rl "^status: on-hold" docs/01-requirements/ || echo "なし"
echo "--- 未修正の不具合（顧客への説明対象）---"
for f in docs/05-defects/BUG-*.md; do
  [ -e "$f" ] || continue
  grep -q "^status: done" "$f" && continue
  echo "$f: $(grep -m1 '^priority:' "$f")  $(grep -m1 '^title:' "$f")"
done
echo "--- 直さないと判断した不具合（説明が要る）---"
grep -l "^priority: wont" docs/05-defects/BUG-*.md 2>/dev/null || echo "なし"
```

**不具合は「決めてほしいこと」ではなく「報告すること」である。** 採否は既に決まっているので、
議題の先頭には置かない。ただし次の 2 つは**顧客の判断が要るので議題に上げる。**

- `priority: future` に下げたい不具合（＝既知の不具合として今回リリースする提案）
- `priority: wont` にしたい不具合（＝現状仕様として受容する提案）

**未修正の不具合は、決定事項でなくても必ず報告欄に載せる。** 伏せると次にまとめて発覚する。

加えて次を取得する。

```bash
gh pr list --state open --limit 30
```

前回議事録（`docs/03-meetings/` の最新ファイル）を読み、**宿題の消化状況**を確認する。宿題として書かれた項目それぞれについて、対応する PR / コミット / 要件があるかを調べ、完了・進行中・未着手を判定する。

## 2. アジェンダを組み立てる

`_templates/agenda.md` をひな形に `docs/03-meetings/AGENDA-YYYY-MM-DD.md` を作成する。

**議題の並び順は次の通り。この順序を守る。**

1. **決定が必要な事項** — 次の 2 つ。ブロッキング度が高い順に並べる。
   - `priority: undecided` の要件（やる / やらないの判断）
   - `status: proposed` の ADR（論点。選択肢からの判断）

   本文の「判断が出ないと止まるもの」が埋まっているものを上に置く。
2. **確認していただきたい事項** — 受入基準が固まっていない `must` の要件。合意を取りに行く。
3. **共有事項** — 進捗と完了報告。**短く**。
4. **持ち帰り・次回以降** — 判断は不要だが認識合わせが要るもの。

各議題には次を必ず書く。

- **想定所要時間**（合計が打ち合わせ時間に収まっているか確認する）
- **判断する人**（顧客側の誰か、を具体的に）
- **判断しなかった場合に何が止まるか**（これが最も重要。書けないなら、その議題は不要である可能性が高い）
- 関連 ID（REQ / ADR / MTG）

## 3. 事前に潰せるものは潰す

議題に載せる前に、次を自問する。

- ドキュメントを読めば分かることを聞こうとしていないか → 削る
- 複数の未決事項が同じ根本論点から来ていないか → 束ねて 1 つの議題にする。
  **同じ `area` の論点は束ねやすい。** 顧客も業務単位で考えているので、話が飛ばずに済む
- `area: unassigned` の要件が溜まっていないか → 「これはどの機能の話か」を確認する議題を 1 つ立てる。
  領域が決まらないと `must` に上げられない
- 選択肢を提示できないか → 「どうしましょうか」ではなく「A か B か」の形にする。案がないまま議題に載せるのは準備不足。
  論点は ADR を `proposed` で起こし、選択肢と弊社推奨を書いてから議題にする
- 30 日以上動いていない `undecided` の要件がないか → `/docs-audit` で先に洗い出してから議題を組む

**選択肢を提示できない議題は、選択肢を作ってから載せる。**

## 4. 出力する

```bash
git switch -c docs/agenda-YYYY-MM-DD
git add docs/03-meetings/AGENDA-YYYY-MM-DD.md
git commit -m "docs(meeting): YYYY-MM-DD のアジェンダ"
git push -u origin docs/agenda-YYYY-MM-DD
```

PR を出したうえで、**顧客にそのまま送れる形の要約**をチャットに出力する。Markdown のまま貼り付けられるように、リポジトリ内のパスや ID の羅列を含めない読みやすい形にする。

## 5. 打ち合わせ後

`/meeting-intake` で文字起こしを取り込む。アジェンダファイルは残したままにする（何を議題にしたかの記録になる）。
