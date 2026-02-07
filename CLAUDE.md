# POD Admin

POD（プリント・オン・デマンド）商品の受注・製造管理システム。外部販売サイトから受注データを受け取り、複数の製造業者に発注・追跡するB2B管理プラットフォーム。

## テック・スタック

### バックエンド（`api/`）
- **フレームワーク**: FastAPI 0.115 + Python 3.12
- **データベース**: PostgreSQL 16 + SQLAlchemy 2.0（async）
- **マイグレーション**: Alembic
- **認証**: JWT + API Key

### フロントエンド（`web/`）
- **フレームワーク**: Next.js 16 + React 19 + TypeScript
- **UI**: Radix UI + Tailwind CSS
- **データフェッチング**: SWR

### インフラ
- **コンテナ**: Docker + Docker Compose
- **デプロイ**: Railway

## ディレクトリ構成

```
pod-admin/
├── api/                    # バックエンドAPI
│   ├── app/
│   │   ├── models/         # SQLAlchemyモデル
│   │   ├── repositories/   # データアクセス層
│   │   ├── routers/        # APIエンドポイント
│   │   ├── schemas/        # Pydanticスキーマ
│   │   ├── services/       # ビジネスロジック
│   │   └── utils/          # ユーティリティ
│   ├── alembic/            # DBマイグレーション
│   ├── scripts/seed.py     # 初期データ投入
│   └── tests/              # テスト
├── web/                    # フロントエンド
│   └── src/
│       ├── app/            # Next.js App Router
│       ├── features/       # 機能別コンポーネント
│       ├── components/     # 共有コンポーネント
│       └── lib/            # ユーティリティ
└── openapi/                # OpenAPI仕様
```

## 開発コマンド

```bash
# コンテナ起動
make up              # APIとDBを起動
make build           # イメージをビルド
make rebuild         # クリーンビルドして起動

# データベース
make migrate         # マイグレーション実行
make seed            # シードデータ挿入
make seed-reset      # データリセット後シード

# ログ・デバッグ
make logs            # 全コンテナのログ
make logs-api        # APIログのみ
make api-shell       # APIコンテナにbash
make db-shell        # DBにpsql接続

# テスト
make test            # pytest実行

# クリーンアップ
make down            # コンテナ停止
make clean           # コンテナ・ボリューム削除
```

## URL

- **フロントエンド**: http://localhost:3000
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/api/v1/docs

## 主要機能

### 商品種類
| 商品 | 説明 |
|-----|------|
| `tshirt` | Tシャツ（S/M/L/XL、白） |
| `acrylic_keychain` | アクリルキーホルダー |
| `acrylic_stand` | アクリルスタンド |
| `sticker` | ステッカー |
| `tote_bag` | トートバッグ |
| `mug` | マグカップ |

### 受注ステータス
1. `ordered` - 発注済み（初期状態）
2. `manufacturing` - 製造中
3. `delivered` - 納入済み
4. `shipped` - 発送完了

### 認証
- **外部API**: `X-API-Key` ヘッダー
- **管理画面**: JWT トークン

## 環境変数

| 変数 | 説明 |
|------|------|
| `DATABASE_URL` | PostgreSQL接続文字列 |
| `SECRET_KEY` | JWT署名用シークレット |
| `DEBUG` | デバッグモード |
| `CORS_ORIGINS` | CORS許可オリジン |
| `API_KEYS` | 外部API用キー |

---

# AI-DLC and Spec-Driven Development

Kiro-style Spec Driven Development implementation on AI-DLC (AI Development Life Cycle)

## Project Context

### Paths
- Steering: `.kiro/steering/`
- Specs: `.kiro/specs/`

### Steering vs Specification

**Steering** (`.kiro/steering/`) - Guide AI with project-wide rules and context
**Specs** (`.kiro/specs/`) - Formalize development process for individual features

### Active Specifications
- Check `.kiro/specs/` for active specifications
- Use `/kiro:spec-status [feature-name]` to check progress

## Development Guidelines
- Think in English, generate responses in Japanese. All Markdown content written to project files (e.g., requirements.md, design.md, tasks.md, research.md, validation reports) MUST be written in the target language configured for this specification (see spec.json.language).

## Minimal Workflow
- Phase 0 (optional): `/kiro:steering`, `/kiro:steering-custom`
- Phase 1 (Specification):
  - `/kiro:spec-init "description"`
  - `/kiro:spec-requirements {feature}`
  - `/kiro:validate-gap {feature}` (optional: for existing codebase)
  - `/kiro:spec-design {feature} [-y]`
  - `/kiro:validate-design {feature}` (optional: design review)
  - `/kiro:spec-tasks {feature} [-y]`
- Phase 2 (Implementation): `/kiro:spec-impl {feature} [tasks]`
  - `/kiro:validate-impl {feature}` (optional: after implementation)
- Progress check: `/kiro:spec-status {feature}` (use anytime)

## Development Rules
- 3-phase approval workflow: Requirements → Design → Tasks → Implementation
- Human review required each phase; use `-y` only for intentional fast-track
- Keep steering current and verify alignment with `/kiro:spec-status`
- Follow the user's instructions precisely, and within that scope act autonomously: gather the necessary context and complete the requested work end-to-end in this run, asking questions only when essential information is missing or the instructions are critically ambiguous.

## Steering Configuration
- Load entire `.kiro/steering/` as project memory
- Default files: `product.md`, `tech.md`, `structure.md`
- Custom files are supported (managed via `/kiro:steering-custom`)
