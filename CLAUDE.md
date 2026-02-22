# プロジェクト規約（ADD方式）

## 開発哲学

このプロジェクトはADD思想に基づく。
**コードの行ではなく、意図・制約・成果で品質を担保する。**

原則:
- Intent-First: すべての実装は構造化された意図仕様から始める
- Test-Proven: 正しさはテストで証明する（人間のコード読解に依存しない）
- Docker-First: 開発・テスト環境はDockerコンテナで完結させ、ローカルを汚さない
- Full-Auto Default: 仕様→設計→実装→テスト→PR作成は原則AIが全自動で行う

---

## 自動化パイプライン

`/ship` 実行時、以下のサブエージェントを順に呼び出して全自動で処理する:

| Phase | サブエージェント | 役割 |
|---|---|---|
| 1 | spec-writer | 自然言語→Intent Spec（YAML）に変換、`.claude/specs/` に保存 |
| 2 | architect | 変更対象の特定、アーキテクチャ判断、実装順序の決定 |
| 3 | tdd-writer | ユニットテスト（`tests/unit/`）+ 統合テスト（`tests/integration/`）+ Playwright E2E（`e2e/`）を生成 |
| 4 | implementer | テストをパスするコードを実装 |
| 5 | quality-gate | 6層検証（静的→Unit→Integration→E2E→仕様適合→AI意味レビュー） |
| 6 | /ship 自身 | 品質ゲートPASS時にコミット・プッシュ・PR作成 |

FAIL時: implementer に戻して修正（最大3回）→ それでもFAILなら人間に報告

---

## テスト戦略

### バックエンド（2層テスト）
- **ユニットテスト**（pytest、`api/tests/unit/`、カバレッジ80%以上）
  - 単一モジュール・関数の振る舞いを検証
  - 外部依存はモック・スタブで分離
- **統合テスト**（pytest、`api/tests/integration/`）
  - 複数モジュール間の連携・DB接続・API呼び出しを検証
  - Docker環境で実DBを使用（テスト用コンテナ）

### フロントエンド
- **ユニット/コンポーネントテスト**（vitest、`web/tests/`）
- **E2Eテスト**（Playwright、`e2e/`、ブラウザからの統合検証）

### テスト完遂ルール
**すべてのテスト（ユニット・統合・E2E）がパスするまで実装を続ける。**
テストが失敗している状態でのコミット・PR作成は禁止。

## Docker環境

```bash
# 開発環境起動
docker compose up -d

# バックエンドテスト
docker compose exec api uv run pytest api/tests/unit          # ユニットテスト
docker compose exec api uv run pytest api/tests/integration   # 統合テスト
docker compose exec api uv run pytest --cov=app               # 全テスト + カバレッジ

# フロントエンドテスト
docker compose exec web npm test                              # vitest
docker compose exec web npm run test:coverage                 # vitest + カバレッジ

# E2E
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm e2e
```

## コマンド

- `/spec <要望>` — 対話型で仕様を詰め、確定後そのまま全自動実装へ
- `/ship <要望>` — 全自動パイプライン（サブエージェントを順に呼び出す）
- `/ship --spec <id>` — 過去の仕様ファイルから再実装

## アーキテクチャガイド

以下のスキルを参照:

- **プロジェクト初期設定**: `.claude/skills/project-init/` — 技術スタック検出、Docker環境構築、テスト設定
- **バックエンド**: `.claude/skills/fastapi-architecture/` — FastAPI レイヤードアーキテクチャ
- **フロントエンド**: `.claude/skills/nextjs-architecture/` — Next.js App Router アーキテクチャ
- **統合テスト環境**: `.claude/skills/integration-test-setup/` — Docker + 実DBを使った統合テスト環境（`tests/integration/` 未存在時に参照）
- **E2E環境構築**: `.claude/skills/e2e-setup/` — Playwright E2E環境の初期セットアップ（`e2e/` 未存在時に参照）

既存プロジェクトの場合は、そのプロジェクトの技術スタック・アーキテクチャに合わせる。

## 技術スタック

- **フロントエンド** (`web/`):
  - Next.js 16 (App Router)
  - React 19
  - TypeScript 5
  - Tailwind CSS 4
  - shadcn/ui (Radix UI)
  - react-hook-form + zod
  - SWR
- **バックエンド** (`api/`):
  - Python 3.12
  - FastAPI + Uvicorn
  - SQLAlchemy 2 (async) + asyncpg
  - Alembic (マイグレーション)
  - uv (パッケージ管理)
- **データベース**:
  - PostgreSQL 16
- **テスト**:
  - pytest + pytest-asyncio（バックエンド）
  - vitest（フロントエンド）
  - Playwright（E2E）
- **コード品質**:
  - ruff + mypy（バックエンド）
  - ESLint（フロントエンド）
- **コンテナ**: Docker Compose
