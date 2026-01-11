# Technical Context

## Technology Stack

### Frontend (web/)

| カテゴリ | 技術 |
|---------|------|
| フレームワーク | Next.js 15 (App Router) |
| 言語 | TypeScript |
| UIライブラリ | shadcn/ui |
| スタイリング | Tailwind CSS |
| データ取得 | SWR |
| フォーム | React Hook Form |
| API型生成 | openapi-typescript |

### Backend (api/)

| カテゴリ | 技術 |
|---------|------|
| フレームワーク | FastAPI |
| 言語 | Python 3.12+ |
| ORM | SQLAlchemy 2.0 |
| バリデーション | Pydantic v2 |
| データベース | PostgreSQL |
| マイグレーション | Alembic |
| 認証 | python-jose (JWT) |

### プロジェクト構成

**モノレポ構成**を採用。フロントエンドとバックエンドを単一リポジトリで管理。

```
project/
├── api/          # FastAPI バックエンド
├── web/          # Next.js フロントエンド
└── openapi/      # 共有 OpenAPI スキーマ
```

## Architecture Pattern

### Frontend: Feature-based Architecture
機能単位でコードをまとめ、責務を明確化する。

### Backend: Layered Architecture
レイヤードアーキテクチャを採用。

```
Router → Service → Repository → Model
                       ↓
                    Database
```

| 層 | 責務 |
|---|---|
| Router | HTTPの入出力処理 |
| Service | ビジネスロジック |
| Repository | データ永続化 |
| Schema | データ構造定義 |
| Model | DBテーブル定義 |

## API Design

- OpenAPI スキーマを Single Source of Truth として管理
- フロントエンド: `openapi-typescript` で型を自動生成
- バックエンド: FastAPI の自動スキーマ生成と整合性を維持
- フロントエンド・バックエンド間の型安全性を担保

## State Management (Frontend)

| 状態の種類 | 管理方法 |
|-----------|---------|
| サーバー状態 | SWR |
| フォーム状態 | React Hook Form |
| ローカルUI状態 | useState / useReducer |
| グローバルUI状態 | Zustand（必要な場合のみ） |

## Key Technical Decisions

### フロントエンド

- `types/api/generated.ts` は自動生成（手動編集禁止）
- フロントエンド固有の型は `features/[domain]/types/` に定義
- Server Components でのデータ取得を基本とする
- ビジネスロジックは hooks に集約

### バックエンド

- 1ファイル1クラス（Router除く）
- Schemaで入出力を明示（Modelを直接レスポンスに使わない）
- 例外はServiceで発生させる
- DIでテスト容易性を確保

## External Integrations

| 連携先 | 連携方式 | 内容 |
|--------|----------|------|
| 外部販売サイト（RKSYO等） | API | 受注情報・製造データの受信 |
| TOSYO DRIVE | ファイルアップロード | 発注資料の共有 |
| 配送代行資料作成PG | CSV入出力 | 配送資料連携 |
| 各運送会社システム | CSV | 配送ラベル印刷用データ |

## Code Generation

```bash
# フロントエンド: OpenAPI から型生成
cd web && npm run generate:api-types

# バックエンド: OpenAPI スキーマ出力
cd api && python -m app.main --export-openapi > ../openapi/schema.yaml
```
