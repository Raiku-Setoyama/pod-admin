# AGENTS.md

このリポジトリで作業するすべての AI エージェントが従う規約。
Claude Code は `CLAUDE.md` 経由でこのファイルを読み込む。

## 絶対に守るルール

1. **`main` に直接コミットしない。** 例外なく PR を経由する。
2. **人間の判断が必要な箇所を勝手に決めない。** 不明点は PR 説明や Issue で明示する。推測で埋めない。
3. **PR を自動マージしない。** マージは人間の操作である。

## タスク管理

**タスクは GitHub Issues で管理する。** リポジトリ内に Markdown でタスク・要件・進捗を置かない。

- 作業は Issue から始める。PR 本文には `Closes #123` を書いて Issue と紐づける。
- 実装中に見つけたスコープ外の作業は、新しい Issue として起票する。

## コミットメッセージ

Conventional Commits に従う。

```
<type>(<scope>): <subject>
```

`type` は `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `ci`。

## ブランチ命名

| 用途 | 形式 |
|---|---|
| 機能追加 | `feat/123-short-slug` |
| 不具合の修正 | `fix/123-short-slug` |
| ドキュメント | `docs/short-slug` |

数字は Issue 番号。

## プロジェクト固有の設定

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
# インフラ
bash scripts/terraform-check.sh      # infra/（terraform fmt / validate）
```

`ci.yml` は ruff / mypy / eslint / tsc / terraform-check をブロッキングで実行する。
**赤い状態を新たに持ち込まないこと。** PR を出す前に上記をローカルで通す。

mypy は `strict = true` で、対象は `app/` だけでなく `tests/` / `scripts/` / `alembic/` を含む api 全体である。
ruff / mypy のルールの除外は**ツールの仕様上の偽陽性に限る**（現在は FastAPI の `Depends()` / `Query()` に対する ruff の `B008` のみ）。
指摘を消すためのルール無効化や、理由のない `# type: ignore` を足さないこと。

テスト（pytest / vitest）はまだ CI に入っていない。

### このプロジェクト特有の注意点

- **本番は GCP Cloud Run。** 本番デプロイは `deploy-prod.yml` の手動実行のみ、stg は `main` マージで自動。
- **Alembic のマイグレーションは多重ヘッドに注意。** 複数 PR が同じ親から分岐すると本番起動が
  crash（502）する。分岐したらマージマイグレーションで単一ヘッドに戻す。
- ファイルの永続化は本番で GCS（`google-cloud-storage`）。未設定なら未使用。
- `docs/superpowers/` は brainstorming 由来の設計メモ。
