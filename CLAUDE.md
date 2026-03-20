# プロジェクト規約

## 技術スタック

- フロントエンド: Next.js 16 / React / TypeScript 5 / Tailwind CSS 4 / Radix UI
- バックエンド: FastAPI / SQLAlchemy 2 (async) / Alembic / Pydantic 2
- 言語: TypeScript (フロントエンド) / Python 3.12 (バックエンド)
- データベース: PostgreSQL 16
- テスト: vitest（フロントエンド）, pytest（バックエンド）, Playwright（E2E）
- パッケージ管理: npm（フロントエンド）, uv（バックエンド）
- コンテナ: Docker Compose

---

## カスタムコマンド

このプロジェクトでは、ADD（AI-Driven Development）方式のカスタムコマンドを利用できます。

| コマンド | 説明 |
|----------|------|
| `/spec <要望>` | 対話型で仕様を作成（GitHub Issue として登録） |
| `/ship #<issue番号>` | GitHub Issue の仕様から全自動実装→PR作成 |

**注意:** 上記コマンド使用時のみ、ADD方式のルール（テスト戦略、品質チェック等）が適用されます。
通常のClaude Code使用時には、これらのルールは適用されません。

詳細: `.claude/skills/add-methodology/SKILL.md`

---

## アーキテクチャガイド

| スキル | 説明 |
|--------|------|
| `docker-env` | Docker環境のサービス検出・技術スタック判定・テスト実行コマンド |
| `fastapi-architecture` | FastAPI レイヤードアーキテクチャ |
| `nextjs-architecture` | Next.js App Router アーキテクチャ |
| `integration-test-setup` | 統合テスト環境（DBモック方式） |
| `add-methodology` | ADD方式の開発哲学・テスト戦略 |

既存プロジェクトの場合は、そのプロジェクトの技術スタック・アーキテクチャに合わせる。
