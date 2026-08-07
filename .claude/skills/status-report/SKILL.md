---
name: status-report
description: プロジェクトの進捗サマリーを生成する。要件の消化状況、進行中の PR、ブロッカー、未決事項をまとめる。「進捗を教えて」「今どうなってる」「週報を作って」「顧客向けの報告資料が欲しい」「ステータスをまとめて」と言われたときはこのスキルを使う。
argument-hint: [internal | client]
allowed-tools: Bash(gh pr list:*) Bash(git log:*)
---

# 進捗レポート

`$ARGUMENTS` が `client` なら顧客向け、`internal` または省略なら社内向けに出力する。

## 1. データを集める

```!
echo "--- 要件 ---"
grep -H "^priority:\|^status:\|^area:" docs/01-requirements/REQ-*.md 2>/dev/null | sed 's|docs/01-requirements/||' || echo "なし"
echo "--- 不具合 ---"
grep -H "^priority:\|^status:\|^area:\|^defect_of:" docs/05-defects/BUG-*.md 2>/dev/null | sed 's|docs/05-defects/||' || echo "なし"
echo "--- 論点（proposed の ADR）---"
grep -l "^status: proposed" docs/02-decisions/ADR-*.md 2>/dev/null || echo "なし"
echo "--- 未決事項 ---"
grep -rn "NEEDS-DECISION" docs/ || echo "なし"
echo "--- 領域の表示名 ---"
sed -n '/^## 領域一覧/,/^## /p' docs/00-charter/areas.md 2>/dev/null | grep '^|' || echo "なし"
```

```bash
gh pr list --state merged --limit 30 --json number,title,body,mergedAt
gh pr list --state open --json number,title,body,isDraft,createdAt
git log --since="7 days ago" --format="%ad %s" --date=short
```

## 2. 社内向け（internal）

正直に書く。悪い数字を丸めない。

```markdown
## 進捗 YYYY-MM-DD

### 要件の消化（priority: must / future のみ）
done <n> / in-progress <n> / on-hold <n> / not-started <n>

| 領域 | done | in-progress | on-hold | not-started |
|---|---|---|---|---|
| 見積管理 | 5 | 1 | 0 | 2 |
| 受注管理 | 0 | 0 | 1 | 4 |

**進んでいない領域が一目で分かることが目的。** 全体の合計だけでは、どこが止まっているか見えない。

### 不具合（要件の消化とは別に数える）
未修正 <n> 件（must <n> / future <n>） / 修正済み <n> 件 / 直さないと判断 <n> 件

| 領域 | 未修正 | 修正済み |
|---|---|---|
| 見積管理 | 2 | 5 |

**不具合を要件の分母に入れない。** 入れると不具合を見つけるほど要件の総数が増え、
消化率が意味を失う。**別の表にすることが目的である。**

### 完了しているが不具合を抱えている要件
| 要件 | 領域 | 未修正の不具合 |
|---|---|---|
| REQ-0009 | 見積管理 | BUG-0003, BUG-0007 |

**要件は不具合が出ても `done` のまま戻さない**（`done` はマージ時点の履歴であり、
今も満たしている保証ではない）。**そのぶん、ここを出さないと「完了」が実態より良く見える。**
`defect_of` の逆引きで導出する。**該当が無ければ「なし」と明記する。**

### 判断待ちの件数
undecided <n> 件 / 論点（proposed の ADR）<n> 件

### 今週マージされた PR
- #34 [REQ-0002] ...

### 滞留しているもの
| 対象 | 滞留日数 | 状況 |
|---|---|---|
| PR #31 | 9日 | レビュー待ち。レビュアーの指名が必要 |
| REQ-0009 | 78日 | undecided のまま。採否が決まっていない |

### ブロッカー
- <何が止まっていて、誰の何待ちか>

### リスク
- <気づいたこと。「特になし」と書くより、小さくても書く>
```

**レビュー待ちの PR が 3 本以上滞留している場合は、それを最初に書く。** レビュー律速がこの体制の最大のボトルネックである。

## 3. 顧客向け（client）

顧客が知りたいのは「予定通りか」「自分が何をすべきか」の 2 点である。

```markdown
## 開発状況のご報告（YYYY-MM-DD）

### 今週完了した機能
- <領域の表示名>: <一行で、業務上の意味を書く。技術用語を使わない>

### 現在進行中
- <領域の表示名>: <見込み>

### 不具合の対応状況
- 未修正 <n> 件（うち今週ご報告いただいたもの <n> 件） / 今週修正済み <n> 件
- <領域の表示名>: <現象を業務の言葉で。いつ直る見込みか>

### ご判断をお願いしたい事項
1. <論点> — <いつまでに判断が必要か。判断が遅れると何が遅れるか>

### 次週の予定
- <項目>
```

顧客向けでは PR 番号・ID を出さない。要件 ID を使わず、
**`docs/00-charter/areas.md` の「表示名」列の言葉で書く。** 顧客が普段使っている呼び方である。
リポジトリ内の内部事情（レビュー滞留など）も書かない。ただし **顧客側の判断待ちで止まっている場合は必ず書く。**

**不具合の件数を丸めない。** 完了した機能だけを並べて不具合に触れない報告は、
次にまとめて発覚したときに信用を失う。**0 件なら「未修正の不具合はありません」と明記する。**

## 4. 出力

レポートはファイルに保存せず、チャットに出力する。定例の記録として残したい場合はユーザーに確認してから `docs/03-meetings/` に置く。
