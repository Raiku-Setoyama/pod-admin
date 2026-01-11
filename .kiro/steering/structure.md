# Project Structure

## Monorepo Organization

```
project/
├── api/                      # バックエンド（FastAPI）
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── routers/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── utils/
│   ├── alembic/              # マイグレーション
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
│
├── web/                      # フロントエンド（Next.js）
│   └── src/
│       ├── app/
│       ├── features/
│       ├── components/
│       ├── lib/
│       ├── types/
│       └── styles/
│
└── openapi/
    └── schema.yaml           # 共有 OpenAPI スキーマ
```

---

## Backend Structure (api/)

### Layer Responsibilities

| レイヤー | 責務 | 許可される操作 |
|---------|------|---------------|
| routers/ | HTTPの入出力処理 | リクエスト受付、レスポンス返却、Service呼び出し |
| services/ | ビジネスロジック | 業務ルール実装、複数Repository連携、トランザクション管理 |
| repositories/ | データ永続化 | CRUD操作、クエリ構築 |
| schemas/ | データ構造定義 | バリデーション、シリアライズ |
| models/ | DBテーブル定義 | ORMマッピング |
| utils/ | 共通ユーティリティ | 例外定義、ヘルパー関数 |

### Dependency Rules (Backend)

```
Router → Service → Repository → Model
                       ↓
                    Database
```

- 上位層は下位層のみに依存する
- 同一層同士は依存しない（Service → Service は避ける）
- 逆方向の依存は禁止（Repository → Service など）

### Naming Conventions (Backend)

| 対象 | 規則 | 例 |
|------|------|-----|
| Router ファイル | 複数形 | `routers/orders.py` |
| Service クラス | 単数形 + Service | `OrderService` |
| Repository クラス | 単数形 + Repository | `OrderRepository` |
| Schema クラス | 用途を接尾辞に | `OrderCreate`, `OrderResponse` |
| Model クラス | テーブル名と一致 | `Order` |

### Key Files (Backend)

| ファイル | 役割 |
|---------|------|
| `main.py` | アプリケーションエントリポイント |
| `config.py` | 環境設定 |
| `database.py` | DB接続設定 |
| `dependencies.py` | DI関数定義 |
| `utils/exceptions.py` | カスタム例外定義 |

---

## Frontend Structure (web/)

### Layer Responsibilities

| レイヤー | 責務 |
|---------|------|
| app/ | ルーティング、レイアウト、Server Components でのデータ取得 |
| features/ | 機能単位のコンポーネント・hooks・型 |
| components/ | 共通UI（ui/、layout/、common/） |
| lib/api/ | バックエンドAPIとの通信 |
| types/ | OpenAPI自動生成型・共通型定義 |

### Dependency Rules (Frontend)

| レイヤー | 依存可能 | 依存禁止 |
|---------|---------|---------|
| types/api/ | なし | すべて |
| app/ | features, components, lib, @/types | - |
| features/ | lib/api, components, @/types | 他の features |
| lib/api/ | @/types | features, app |
| components/ | なし | features, lib, app, @/types |

### Feature Module Pattern

```
features/[domain]/
├── components/     # 機能専用UIコンポーネント
├── hooks/          # 機能専用カスタムhooks
├── types/          # フロントエンド固有の型
└── index.ts        # 公開エクスポート
```

**ルール**: Feature 間の直接参照は禁止。共通化が必要な場合は `components/common/` へ移動。

### Naming Conventions (Frontend)

| 対象 | 規則 | 例 |
|------|------|-----|
| ファイル名 | ケバブケース | `order-list.tsx`, `use-orders.ts` |
| コンポーネント | パスカルケース | `OrderList`, `OrderStatusBadge` |
| Hooks | use + キャメルケース | `useOrders`, `useOrderForm` |
| 型 | パスカルケース | `Order`, `OrderStatus` |
| API関数 | オブジェクト + キャメルケース | `ordersApi.getAll()` |

### Import Aliases (Frontend)

```typescript
// tsconfig.json で設定
"@/*": ["./src/*"]

// 使用例
import { OrderList } from '@/features/orders'
import type { Order } from '@/types'
import { Button } from '@/components/ui/button'
```

### Key Files (Frontend)

| ファイル | 役割 |
|---------|------|
| `types/api/generated.ts` | OpenAPI 自動生成型（編集禁止） |
| `types/index.ts` | 型のre-export・エイリアス |
| `lib/api/client.ts` | API通信基盤 |
| `features/*/index.ts` | 機能モジュールの公開API |

---

## Shared Resources

### OpenAPI Schema

`openapi/schema.yaml` は以下の用途で使用：
- フロントエンド型生成のソース
- バックエンド実装の仕様参照
- API ドキュメント生成
