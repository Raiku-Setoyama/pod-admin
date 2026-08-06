# AGENTS.md

このリポジトリで作業するすべての AI エージェントが従う規約。
Claude Code は `CLAUDE.md` 経由でこのファイルを読み込む。

**このファイルは規約の正本である。** 起票から完了までの流れは `WORKFLOW.md` を参照。

## このリポジトリの性質

受託開発プロジェクトの **SSoT（Single Source of Truth）**。
要件定義・議事録・意思決定記録・ソースコードを 1 つの Git リポジトリで管理する。

エージェントは作業を行い、人間は判断のみを行う。
すべての判断は **Pull Request のレビュー** という形で行われる。

## 絶対に守るルール

1. **`main` に直接コミットしない。** 例外なく PR を経由する。
2. **議事録（`docs/03-meetings/`）は追記のみ。** 過去の議事録の本文を書き換えてはならない。誤りは訂正エントリを追記して表現する。
3. **`docs/03-meetings/raw/` は絶対に編集しない。** 文字起こしの原文である。
4. **実装 PR は必ず品質検証を通す。** `/quality-gate` を実行せずに `git push` してはならない。Push フックがこれを機械的に強制している。
5. **人間の判断が必要な箇所を勝手に決めない。** 不明点は `[NEEDS-DECISION]` マーカーを本文に残し、PR 説明で明示する。推測で埋めない。
6. **PR を自動マージしない。** マージは人間の操作である。

## ID 体系

すべての文書要素は安定した ID を持つ。ID は一度振ったら変えない。

| 種別 | ID 形式 | 置き場所 |
|---|---|---|
| 要件 | `REQ-0001` | `docs/01-requirements/REQ-0001.md` |
| 意思決定記録・論点 | `ADR-0001` | `docs/02-decisions/ADR-0001.md` |
| 議事録 | `MTG-2026-07-28` | `docs/03-meetings/MTG-2026-07-28.md` |

**要求・要件・バックログは分けない。** 3 つとも `REQ-XXXX` の 1 層に入り、
`priority`（採否）と `status`（実装）の 2 つのフィールドで区別する（下記「2 つの軸」）。

同日に複数の打ち合わせがある場合は `MTG-2026-07-28-a`、`-b` と連番を付ける。

新規 ID を採番するときは、該当ディレクトリの既存ファイルを確認して最大値 + 1 を使う。

## 領域（area）

ID が MTG → REQ → PR という**縦の連鎖**を作るのに対し、`area` は同じ機能まわりの文書を
**横に串刺し**にする。「見積管理の要件を全部出す」「この領域だけ進捗を報告する」が機械的にできる。

語彙は案件ごとに違う。**正本は `docs/00-charter/areas.md`。** 何を単位にするかはシステムによるが、
Web アプリなら機能単位が分かりやすい。

- REQ と ADR の 2 種に、**1 つだけ**付ける。
  **議事録には付けない。** 打ち合わせは複数領域にまたがるイベントであり、分類する対象ではない。
- 複数領域にまたがるものは `common`。まだ決まっていないものは `unassigned`。
  **空欄は CI エラーになる。**「分からない」は空欄ではなく `unassigned` で表明する。
- **判断ゲートを通るときは、領域が確定していなければならない。**
  要件は `priority` を `undecided` から動かすとき、ADR は `proposed` を抜けるとき。
  それ以降に `unassigned` が残っていると CI エラーになる。
  正確な判定は `scripts/docs-lint.py` の `area_may_be_pending()` が正本である。
- **エージェントは領域を独断で確定させない。** 既存の語彙に当てはまらないときは `unassigned` にしたうえで、
  `areas.md` への追加を PR で提案する。確定はマージの瞬間である。語彙が無秩序に増えると分類の意味がなくなる。
- **最初の語彙は、最初に材料が揃ったスキルが提案する。** 起票より前に先回りして決めない。
  打ち合わせがあるなら初回の `/meeting-intake`、持たないなら初回の `/requirements-intake`、
  既存プロジェクトへの後付けなら `/adopt-repo` である。**定例の有無で入口が変わるだけで、
  「起票の材料から作る」という原則は同じ。**
  `common` を「分からない」の置き場にしない。それは `unassigned` である。
- キーは ID と同じく一度振ったら変えない。表示名は変えてよい。
  廃止するときは削除せず、状態を `retired` にする（過去の文書が参照しているため）。

`category` とは別の軸である。混同しない。

| フィールド | 軸 | 値 |
|---|---|---|
| `area` | **どの機能まわりの話か** | 案件ごとに定義（`areas.md`） |
| `category` | 要件の性質 | `functional` / `non-functional` / `constraint` |

## トレーサビリティ

ID は次の向きで連鎖する。エージェントは変更時に必ず前後を辿って整合性を保つ。

```
MTG（議事録） → REQ（要件） → PR → コード
（任意）          ↑     ↑
              ADR（決定・論点）  WBS
```

**REQ-XXXX がそのまま作業 ID である。GitHub Issue は使わない。**
要件・受入基準・進捗のすべてを `docs/01-requirements/` に置く。写しをリポジトリの外に作らない。

**議事録は連鎖の起点として必須ではない。** 定例を持たないチームでは、Slack のスレッドや
口頭のメモから `/requirements-intake` で直接起票してよい。連鎖の必須部分は **REQ → PR → コード**
であり、MTG はその前段にあってもなくてもよい。**要件になっていることだけが条件である。**

**出た話は、すべて要件として起票する。** 打ち合わせ・Slack・口頭のいずれで出たかを問わない。
ただし `priority: undecided` から始める。
「やる」と決まったものだけが `must` / `future` に上がる。決まらなかったものは `undecided` に、
見送ったものは `wont` に残る。**決める必要がある論点は要件ではなく ADR（`proposed`）にする。**

- 要件の `source` には、その要件を生んだ／変えた議事録 ID をすべて列挙する。
  **打ち合わせ由来でない要件は空（`[]`）でよい。** 架空の MTG-ID を作らない。
  出典は本文の `## 経緯` に一行で書く（Slack のスレッド、口頭依頼など）。
- 要件を `future` / `wont` にするときは `decision` と `decided_at` を必ず埋める。
- 順序の制約は `depends_on` に書く。親子関係は作らない。
- PR のタイトルは `[REQ-0001] 概要` の形式にする（ブランチ名は「ブランチ命名」を参照）。
- PR 本文には `Refs: REQ-0001` を必ず書く。**これが唯一のトレーサビリティ記載であり、CI が検証する。**
  **実装 PR に書ける要件 ID は 1 つだけ。**

## frontmatter スキーマ

すべての文書は YAML frontmatter を持つ。詳細は `_templates/` の各ひな形を参照。

共通フィールド:

| フィールド | 必須 | 説明 |
|---|---|---|
| `id` | ○ | 上記 ID 体系に従う |
| `title` | ○ | 一行の要約 |
| `status` | ○ | 種別ごとに定義（下記） |
| `area` | ○ | `docs/00-charter/areas.md` のキー。議事録は対象外（上記「領域」を参照） |
| `updated` | ○ | `YYYY-MM-DD`。変更のたびに更新する |

要件はこれに加えて `priority` を必ず持つ。

## 2 つの軸

要件は直交する 2 つの軸を持つ。**この 2 つが要求・要件・バックログの区別を置き換える。**

### 軸 1: `priority` — 採否・約束の度合い

**人間が PR のマージで決める。** エージェントが確定させてはならない。

| 値 | 意味 | 旧モデルの相当 |
|---|---|---|
| `undecided` | 実装するかは未定。判断待ち | 要求（RQ `new` / `discussing`） |
| `must` | 必ず必要。今回のスコープ | 要件（REQ `agreed`） |
| `future` | 将来的に必ず必要。今回はやらない | 要求（RQ `deferred`） |
| `wont` | やらないと決めた | 要求（RQ `rejected`）/ 要件（REQ `dropped`） |

- **起票は必ず `undecided`。** エージェントはここから動かさない。
- `future` / `wont` にするときは `decision` と `decided_at` が必須。**理由のない判断は必ず蒸し返される。**
- `must` にするときは受入基準が必須。**「やると決めるなら、何をもって完了とするかも決める。」**

### 軸 2: `status` — 実装の進み具合

エージェントが進める。

| 値 | 意味 |
|---|---|
| `not-started` | 未着手 |
| `in-progress` | 着手中。受入基準の一部が未達 |
| `done` | 実装済み |
| `on-hold` | 保留。着手したが止めている（理由を本文に書く） |

`done` は実装 PR 自身が書き込む。**そのマージが完了の承認になる。**
未達の受入基準を残したまま `done` にすると CI が落ちる。

**`undecided`（やるか決まっていない）と `on-hold`（やると決めたが止めている）は別物である。**
前者は採否、後者は実行の話。混同しない。

ADR の `status` は `proposed` → `accepted` → `superseded`。
`proposed` は「まだ決まっていない論点」、`accepted` は「決まった」。
**`accepted` への遷移は人間の承認（PR マージ）を経てのみ行う。**

### 着手可能かどうかは保存しない

次の条件の論理積である。フラグとして持たず、`scripts/docs-lint.py` と
`/implement-requirement` がその場で判定する。

```
priority ∈ {must, future} ∧ status = not-started ∧ 受入基準が 1 件以上
∧ [NEEDS-DECISION] なし ∧ area ≠ unassigned ∧ depends_on がすべて done
```

保存されたフラグは、立てたあとに前提が崩れても立ったままになる。導出ならその事故が起きない。

## 文書の役割分担

| 層 | ディレクトリ | 性質 | 更新頻度 |
|---|---|---|---|
| 憲章 | `docs/00-charter/` | 前提・制約・非機能要件。滅多に変わらない | 低 |
| 要件 | `docs/01-requirements/` | **現在の状態**。判断待ちも合意内容も実行計画もここ | 高 |
| 決定・論点 | `docs/02-decisions/` | **追記**。決定の履歴と、決まっていない論点 | 中 |
| 議事録 | `docs/03-meetings/` | **追記**。イベントログ | 高 |
| WBS | `docs/04-wbs/` | 要件から導出されるスケジュール | 中 |

**議事録はイベント、要件は状態。** 議事録を「起きたこと」として記録し、そこから要件という「今どうなっているか」を導出する。この向きを逆にしない。

## 未決事項の書き方

決まっていないことを本文に埋め込むときは、必ず論点の ID を添える。
論点は `docs/02-decisions/` に ADR を `status: proposed` で起票し、**選択肢と推奨を書く。**

```
[NEEDS-DECISION: ADR-0012]
```

ID のない `[NEEDS-DECISION]` は CI エラーになる。**論点には必ず住所を与える。**

決まったら同じ ADR が `accepted` になる。**論点と決定を別々の文書に書き分けない。**
書き直しが発生し、経緯が切れる。

**起票した論点は、必ず回収される経路に乗せる。** 起票しただけで放置すると、
`[NEEDS-DECISION]` を抱えた要件が着手できないまま溜まる。回収の経路は 2 つあり、
**どちらか一方があればよい。**

| チームの形 | 回収するもの |
|---|---|
| 定例の打ち合わせがある | `/meeting-agenda` が `proposed` の ADR を次回議題に載せる |
| **定例を持たない** | **`/requirements-refine` が `proposed` の ADR を PR の「判断していただきたいこと」に出す** |

後者は打ち合わせを必要としない。**定例がないチームは `/requirements-refine` を定期的に回す。**

## 作業の単位

**作業の単位は要件である。行数の上限は設けない。**

- 1 打ち合わせ = 1 ドキュメント PR
- **1 要件 = 1 実装 PR**（原則）

### PR を分けてよいとき

実装の都合で分けたほうがよいときだけ分ける。例:

- スキーマ変更・マイグレーションを先に入れ、確認してからロジックを載せたい
- 依存パッケージの追加や大量の機械的置換を、レビュー対象から切り離したい
- 中間状態がそれ自体で動作し、レビュー可能な形になっている

**「行数が多いから」は分割の理由にならない。**
意味のある単位で切られた 1 本の PR は、要件を半分ずつ実装した 2 本より読みやすい。
律速が人間のレビューであることは変わらないが、それに対する答えは
「小さく切る」ではなく **「意味のある単位で切る」** である。

**中間状態が壊れる分割はしない。** `main` が動かない状態を経由するくらいなら 1 本で出す。

分けると決めたら `## 実装メモ` に計画を書き、要件は `status: in-progress` のままにする。
受入基準を段階的に `[x]` にし、**すべて埋まった最後の PR が `done` を書く。**

**この判断に人間の承認は要らない。** 実装の都合はエージェントが決めてよい。

### 要件そのものを分けるとき

**実体が複数の要件だったときだけ**である。「実装が大きいから」で要件を分けない。
要件の粒度は顧客との合意の単位で決まる。分割は `/requirements-refine` の仕事である。

### 不変条件

**PR → 要件は多対一。** 1 要件が N 個の PR に分かれるのは可、
1 つの PR が N 個の要件を実装するのは不可。CI が機械的に拒否する。

### 全工程を通さなくてよい変更

次の 2 種類は MTG → REQ を通さず、直接 PR を出してよい。

1. **要件に影響しない軽微な変更** — 誤字修正、コメント追加、依存パッケージのパッチ更新など。
   判断基準は「顧客に説明が必要か」。必要なら軽微ではないので、要件の起票から始める。
2. **運用基盤そのものの変更** — `.claude/skills/`、`scripts/`、`.github/workflows/docs-check.yml`、
   `.github/workflows/pr-quality-check.yml` の改善。要件にならない。
   **運用しながら直すことが前提の設計である。**
   ただし `.github/workflows/ci.yml` は**成果物のビルド・テストゲート**なので、ここに含めない。
   緩めるなら顧客に説明が必要であり、1 の判断基準に従う。

`Refs:` には関連する既存 ID を書く。該当する ID がなければ `なし（理由）` と書く。

```
Refs: なし（軽微な修正）
Refs: なし（スキルの改善）
```

**CI は全角括弧で囲まれた理由が空でないことだけを見て、ID の要求を外す。**
半角括弧や括弧なしは通らない。理由が妥当かはレビュアーが判断する。
この抜け道を使っても、品質検証（`/quality-gate`）は省略できない。

## コミットメッセージ

Conventional Commits に従う。

```
<type>(<scope>): <subject>

Refs: REQ-0003
```

`type` は `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `ci`。
ドキュメント更新は `docs`、スコープは `req` / `meeting` / `adr` を使う。

## ブランチ命名

| 用途 | 形式 |
|---|---|
| 実装 | `feat/REQ-0001-short-slug` |
| 議事録取り込み | `docs/mtg-2026-07-28` |
| 打ち合わせによらない起票 | `docs/intake-2026-07-28` |
| 要件の棚卸し | `docs/requirements-refine-2026-07-28` |

1 要件を複数 PR に分ける場合も要件 ID は同じままにする
（`feat/REQ-0001-schema`, `feat/REQ-0001-api` など）。

## よく使うスキル

| コマンド | 用途 |
|---|---|
| `/meeting-agenda` | 次回打ち合わせのアジェンダを生成 |
| `/meeting-intake` | 文字起こしから議事録を作り、要件の更新 PR を出す |
| `/requirements-intake` | 打ち合わせによらない入力（Slack・メモ・口頭）から要件を起票する |
| `/requirements-refine` | 要件の棚卸し（採否の仕分け・受入基準の確定・分割・WBS 更新） |
| `/implement-requirement` | 要件を実装し、品質検証を通して PR を出す |
| `/quality-gate` | 静的チェック + `/simplify max` の品質検証 |
| `/client-export` | 顧客向け資料（Excel・CSV・要件定義書）を生成 |
| `/docs-audit` | ドキュメントの ID 整合性を検査 |
| `/status-report` | 進捗サマリーを生成 |

## プロジェクト固有の設定

<!-- ここから下は各プロジェクトで書き換える -->

### 構成

モノレポ。`api/`（FastAPI バックエンド）と `web/`（Next.js フロントエンド）の 2 つから成る。
`openapi/schema.yaml` を正本に、`web` は `npm run generate:api-types` で型を生成する。

### 技術スタック

- フロント: Next.js 16 / React 19 / TypeScript 5 / Tailwind CSS 4 / Radix UI / React Hook Form + Zod / SWR
- バック: FastAPI / SQLAlchemy 2 (async + asyncpg) / Alembic / Pydantic 2 / SendGrid / WeasyPrint
- DB: PostgreSQL 16
- パッケージ管理: npm（`web`）/ uv（`api`）
- テスト: vitest（`web`）/ pytest（`api`）/ Playwright（E2E）
- コンテナ: Docker Compose（`api/docker-compose.yml`。api / web / db / e2e）

### ビルド・テストコマンド

```bash
# 依存インストール
cd api && uv sync --extra dev        # backend
cd web && npm install                # frontend
# 開発サーバ起動（api ディレクトリの compose が api/web/db/e2e を束ねる）
cd api && docker compose up
# テスト
cd api && uv run pytest              # backend（testpaths=tests, asyncio_mode=auto）
cd web && npm run test:run           # frontend（vitest run）
# 型チェック
cd api && uv run mypy .              # backend
cd web && npx tsc --noEmit           # frontend
# Lint
cd api && uv run ruff check .        # backend（line-length 100, py312）
cd web && npm run lint               # frontend（eslint 9）
```

`scripts/quality-gate.sh` の `PROJECT_CHECKS` は現状 docs-lint のみ有効。上記のコード用チェック（ruff / mypy / eslint / tsc）は 2026-08-06 時点で大量に失敗するため導入予定（REQ-0041）。緑化したものから順に有効化する。

### このプロジェクト特有の注意点

- **タスク管理は `REQ-XXXX` に一本化した。** 従来の GitHub Issue はこのリポジトリでは新規に使わない
  （移行前の Open Issue は段階2で要件に畳み込む）。作業 ID は要件 ID である。
- **本番 API のデプロイは Railway。`api/` で `railway up` を実行する。** 環境変数変更による
  自動再デプロイは hello-world が出て本番ダウンにつながるため、必ず `railway up` で反映する。
  手順は `api/DEPLOY.md`。
- **Alembic のマイグレーションは多重ヘッドに注意。** 複数 PR が同じ親から分岐すると本番起動が
  crash（502）する。分岐したらマージマイグレーションで単一ヘッドに戻す。
- ファイルの永続化は本番で GCS（`google-cloud-storage`）。未設定なら未使用。
- `docs/superpowers/` は別体系（brainstorming 由来の設計メモ）。この docs 管理体制の対象外として残す。
