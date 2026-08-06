# WORKFLOW — 起票から完了まで

**この 1 枚を読めば運用を始められます。** 規約の正本は `AGENTS.md` です。

---

## 3 行でいうと

1. 出た話は**すべて要件（`REQ-XXXX`）として起票**する。やると決まっていなくてよい。
   打ち合わせで出た話も、Slack で流れた話も、行き先は同じ 1 か所である。
2. 「やるか」と「何をもって完了とするか」は**同じ PR で人間が決める**。
3. **要件がそのまま作業 ID**。起票した ID のまま実装 PR になる。Issue もタスクも作らない。

---

## 1 つの要件のライフサイクル

```
話が出る（打ち合わせ / Slack / 口頭 / 実装中の気づき）
  │
  ├─ /meeting-intake  ────────────→ 【判断①】起票 PR
  │  または                            「出た話と合っているか」
  │  /requirements-intake
  │     REQ-0042 を起票
  │     priority: undecided
  │     status:   not-started
  │
  ├─ /requirements-refine ────────→ 【判断②】要件棚卸し PR
  │     priority: undecided → must     「やるか」＋「何をもって完了とするか」
  │     受入基準を確定                  ← 受入基準が固まるのはここ
  │     area を確定
  │
  └─ /implement-requirement ──────→ 【判断③】実装 PR
        status: not-started              「マージしてよいか」
             → in-progress → done      ← マージが完了の承認
```

**人間がやることは、この 3 つの PR をマージするかどうかだけです。**

**打ち合わせは前提ではありません。** 起票の入口が 2 つあるだけで、以降の流れは同じです。

| 起票の材料 | 入口 | 議事録 |
|---|---|---|
| 文字起こしのある打ち合わせ | `/meeting-intake` | 作る（`MTG-YYYY-MM-DD`） |
| Slack のスレッド・口頭のメモ・箇条書き | `/requirements-intake` | 作らない。出典は要件の `## 経緯` に書く |

要件の `source`（議事録 ID）は**打ち合わせ由来でなければ空（`[]`）で構いません。**
`scripts/docs-lint.py` も CI も、議事録の存在を要求しません。

要件は 2 つのフィールドで表されます。詳細は `docs/01-requirements/index.md`。

| 軸 | フィールド | 値 | 誰が決めるか |
|---|---|---|---|
| 採否 | `priority` | `undecided` / `must` / `future` / `wont` | **人間（PR マージ）** |
| 実装 | `status` | `not-started` / `in-progress` / `done` / `on-hold` | エージェント |

---

## 運用サイクル

チームの形に合わせて 2 通りあります。**違うのは判断の場を「打ち合わせ」に置くか
「PR」だけに置くかで、判断①②③の中身は同じです。**

### A. 定例が週 1 回ある場合

```
月曜  /meeting-agenda 2026-08-04
      → アジェンダ PR + 顧客送付用テキスト。前日中に顧客へ送る

火曜  文字起こしを docs/03-meetings/raw/ に置く
      /meeting-intake 2026-08-04
      → 議事録 + 要件更新 PR（新規要件はすべて priority: undecided）
      → 【判断①】差分をレビューしてマージ

水曜  /requirements-refine
      → 採否の提案 + 受入基準の確定 + 状態の修正 + WBS 更新 PR
      → 【判断②】やる / やらないと受入基準を確認してマージ

木〜金 /implement-requirement REQ-0042
      → 実装 + 品質検証 + PR
      → 【判断③】レビューしてマージ（要件が done になる）
      （複数要件を並行させる場合は git worktree で分離）

金曜  /status-report client     → 顧客向け週次報告
月末  /client-export            → Excel(3タブ) / CSV / 要件定義書(Word)
週次  /docs-audit               → 参照切れ・矛盾・放置の検出
```

### B. 定例を持たない場合（少人数チーム向け）

打ち合わせに紐づく `/meeting-agenda` と `/meeting-intake` を使いません。
**代わりに `/requirements-refine` が心拍になります。**

```
随時  話が出たその場で /requirements-intake
      「この Slack のスレッドを起票して」でよい
      → 起票 PR（すべて priority: undecided）
      → 【判断①】起票内容が合っているかを見てマージ

週 1  /requirements-refine
      → 採否の提案 + 受入基準の確定 + 状態の修正 + WBS 更新
      → proposed の ADR が全件ここに集まる          ← 論点の回収はここだけ
      → 【判断②】やる / やらないと受入基準を確認してマージ

随時  /implement-requirement REQ-0042
      → 実装 + 品質検証 + PR
      → 【判断③】レビューしてマージ（要件が done になる）

週次  /status-report            → 進捗の把握
週次  /docs-audit               → 参照切れ・矛盾・放置の検出
```

**`/requirements-refine` を止めると、この形は破綻します。** 定例がある場合は
判断待ちが `/meeting-agenda` 経由で議題に上がりますが、定例がなければ
**`undecided` の要件と `proposed` の ADR を人間の前に運ぶ経路がここしかありません。**
週 1 回で回らなければ隔週でも構いませんが、**動かさない期間を作らないでください。**

初回だけ注意点があります。**領域（`area`）の語彙は初回の `/requirements-intake` が
起票の材料から提案します。** 語彙が `common` と `unassigned` だけのままだと、
`must` に上げる時点で `docs-lint` が落ちて実装に進めません（→ `docs/00-charter/areas.md`）。

---

## 各段階で何が起きるか

### ① 打ち合わせ前 — `/meeting-agenda [日付]`

<!-- 定例がある場合だけの段階です。持たないチームは②から読んでください -->

判断待ちの要件（`priority: undecided`）、決まっていない論点（`proposed` の ADR）、`[NEEDS-DECISION]`、滞留 PR、前回の宿題を集めます。

議題は**「決めてほしいこと」が先頭**に並び、各議題に「判断が出ないと何が止まるか」が付きます。

### ② 起票 — `/meeting-intake [日付]` または `/requirements-intake`

打ち合わせを取り込むなら前者、Slack のスレッドや口頭のメモから起こすなら後者です。
**違いは議事録を作るかどうかだけで、起票のルールは同じです。**

いずれも**出た話がすべて起票**されます。行き先は 2 つだけです。

| 出た話 | 行き先 |
|---|---|
| 「〜したい」「自動化できそう」「これだと困る」 | 要件（`priority: undecided`） |
| **「承認は 2 段階か 3 段階か」** | **ADR（`status: proposed`）** ← 論点は要件にしない |

起票は必ず `priority: undecided` です。その場で合意した話も例外ではありません。
合意した事実は議事録の「決定事項」（`/requirements-intake` なら PR 本文）に書き、
採否の確定は PR 本文で提案します。

**受入基準はここでは書きません。** 埋めるのは採否を決める瞬間です。

PR 本文の「判断していただきたいこと」を見れば、レビューすべき点が分かります。差分を全部読む必要はありません。

### ③ 棚卸し — `/requirements-refine`

`undecided` の要件を 1 件ずつ仕分けます。

| 提案 | 併せてやること |
|---|---|
| `must`（今回やる） | **受入基準を書く**（必須）、`area` を確定 |
| `future`（次期フェーズ） | `decision` と `decided_at` を書く |
| `wont`（やらない） | 同上 — **見送りの記録が受託では資産になる** |
| `undecided` のまま | 何が足りないかを本文に書き、次回議題へ |

同じスキルが、実態に合わせた `status` の修正と WBS の再生成もやります。

### ④ 実装 — `/implement-requirement REQ-0042`

**着手可能かどうかはフラグとして保存していません。** その場で判定します。

```
priority ∈ {must, future} ∧ status = not-started ∧ 受入基準が 1 件以上
∧ [NEEDS-DECISION] なし ∧ area ≠ unassigned ∧ depends_on がすべて done
```

以降は `feat/REQ-0042-slug` で実装 → `/quality-gate` → 受入基準を `[x]` → `status: done` → PR（`Refs: REQ-0042`）。
**ステータス更新を別作業でやる必要はありません。**

### ⑤ 顧客への提出 — `/client-export [review|agreed]`

`docs/` が正本で、資料はそこからの**投影**です。資料を直接編集せず、`docs/` を直して再生成します。

| ファイル | 中身 |
|---|---|
| `dist/プロジェクト管理表.xlsx` | 要件 / 検討事項 / 決定事項の 3 タブ。**1 ファイルで手渡すならこれ** |
| `dist/requirements.csv` | 要件（`must` / `future`）。実装状況の列つき |
| `dist/pending.csv` | 検討事項（`undecided` / `wont`）。判断内容と判断日つき |
| `dist/decisions.csv` | 決定事項・論点（ADR） |
| `dist/要件定義書.docx` | 提出・検収用。目次・改ページつき |

合意版を出したら `git tag -a v1.0-requirements` で版を固定します。

---

## 迷ったときの判断

### 実装が大きい

**行数の上限はありません。** 1 要件 = 1 PR が原則で、分けるのは実装の都合があるときだけです
（スキーマ変更を先に確認したい、機械的置換を切り離したい等）。**「行数が多いから」は理由になりません。**

分けるときは `## 実装メモ` に計画を書き、`status: in-progress` のまま複数 PR で消化して、
**受入基準が全部 `[x]` になった最後の PR が `done` を書きます**。この判断に人間の承認は要りません。

**要件そのものを分けるのは、実体が複数の要件だったときだけ**で、それは `/requirements-refine` の仕事です。

### 実装中に判断が必要になった

エージェントは**実装せずに止まります**。出口は 2 つで、どちらもリポジトリに残ります。

- **その場で聞けば済む** → 選択肢と推奨が提示される。回答を要件に反映する PR を先に出す
- **顧客・PM の判断が要る** → **ADR を `proposed` で起票**し、要件に `[NEEDS-DECISION: ADR-XXXX]` を置いて止まる

起票した論点は、**次のどちらかが必ず人間の前に運びます。**

| チームの形 | 回収する経路 |
|---|---|
| 定例がある | `/meeting-agenda` が次回議題に自動で載せる |
| **定例を持たない** | **`/requirements-refine` が PR の「判断していただきたいこと（論点）」に出す** |

### 実装中に別の問題を見つけた

直さずに `priority: undecided` の要件として起票します。**スコープを広げません。**

### 全工程を通さなくてよいもの

要件に影響しない軽微な修正（誤字・コメント）と、スキル・CI 自体の改善は直接 PR を出せます。
`Refs: なし（理由）` と書きます。判断基準は**「顧客に説明が必要か」**。詳細は `AGENTS.md`。

---

## 機械が守っていること

規律を人間の記憶に頼っていません。

| 検査 | どこで |
|---|---|
| `must` なのに受入基準が空 | docs-lint → **エラー** |
| `in-progress` / `done` なのに `priority` が `undecided` / `wont` | docs-lint → **エラー** |
| `done` なのに受入基準が未達 | docs-lint → **エラー** |
| `future` / `wont` なのに `decision` が空 | docs-lint → **エラー** |
| 判断済みなのに `area: unassigned` | docs-lint → **エラー** |
| 1 つの PR が 2 件以上の要件を実装 | pr-quality-check → **拒否** |
| `/quality-gate` を通さず `git push` | PreToolUse フック → **拒否** |

**`1 要件 → N PR` は可、`1 PR → N 要件` は不可。** この非対称が唯一の不変条件です。

---

## もっと詳しく

| 知りたいこと | 読む場所 |
|---|---|
| 規約の正本（ID 体系・領域・2 つの軸・作業の単位） | `AGENTS.md` |
| スキル一覧 | `AGENTS.md`「よく使うスキル」 |
| `priority` と `status` の意味、着手可能の条件 | `docs/01-requirements/index.md` |
| ビルド・テスト・デプロイ | `AGENTS.md`「プロジェクト固有の設定」 |
