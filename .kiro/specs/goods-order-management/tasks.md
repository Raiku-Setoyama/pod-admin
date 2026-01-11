# Implementation Tasks: goods-order-management

## Overview

PODグッズ受発注管理システムの実装タスク。バックエンド（FastAPI）とフロントエンド（Next.js）をモノレポ構成で実装する。

---

## Task 1: プロジェクト基盤セットアップ (P)

バックエンド・フロントエンドの両プロジェクトを初期化し、開発環境を構築する。

**Requirements covered:** 8.1.1, 8.1.2, 8.2.1

### Sub-tasks

- [x] 1.1 バックエンドプロジェクトの初期化
  - api/ ディレクトリに FastAPI プロジェクトを作成する
  - requirements.txt に依存関係を定義する（fastapi, uvicorn, sqlalchemy, asyncpg, pydantic, alembic, python-jose, openpyxl）
  - pyproject.toml を設定する
  - app/main.py にエントリポイントを作成し、CORS 設定を行う
  - app/config.py に環境設定を定義する

- [x] 1.2 データベース接続とマイグレーション設定
  - app/database.py に非同期 SQLAlchemy エンジンとセッションを設定する
  - Alembic を初期化し、alembic.ini と env.py を設定する
  - app/models/base.py に SQLAlchemy Base クラスを定義する

- [x] 1.3 フロントエンドプロジェクトの初期化
  - web/ ディレクトリに Next.js 15 プロジェクトを作成する（App Router 使用）
  - TypeScript, Tailwind CSS, shadcn/ui を設定する
  - package.json に依存関係を追加する（swr, react-hook-form, zod, openapi-typescript）
  - tsconfig.json にパスエイリアス（@/*）を設定する

- [x] 1.4 共通ユーティリティと例外処理の実装
  - api/app/utils/exceptions.py にカスタム例外クラスを定義する（AppException, NotFoundError, ValidationError, UnauthorizedError, ForbiddenError, DailyOrderLimitExceededError）
  - api/app/main.py に例外ハンドラを登録する
  - api/app/utils/file_storage.py にファイル保存機能を実装する

---

## Task 2: 認証・認可システムの実装

管理者認証、メーカー認証、API Key 認証を実装する。

**Requirements covered:** 8.3.1, 8.3.2, 8.3.3, 1.1.6, 4.1

### Sub-tasks

- [x] 2.1 JWT 認証基盤の実装
  - api/app/utils/security.py に JWT トークン生成・検証機能を実装する
  - パスワードハッシュ機能を実装する（passlib + bcrypt）
  - api/app/models/user.py に User モデルを定義する
  - 初期マイグレーションを作成・適用する

- [x] 2.2 管理者認証 API の実装
  - api/app/schemas/auth.py にログインスキーマを定義する
  - api/app/services/auth_service.py に認証ロジックを実装する
  - api/app/routers/auth.py にログイン・トークンリフレッシュエンドポイントを実装する
  - api/app/dependencies.py に get_current_admin 依存関数を実装する

- [x] 2.3 API Key 認証の実装
  - api/app/dependencies.py に verify_api_key 依存関数を実装する
  - X-API-Key ヘッダーからの認証を実装する

- [x] 2.4 フロントエンド認証の実装
  - web/src/lib/api/client.ts に API クライアントを実装する（認証トークン付与）
  - web/src/features/auth/components/login-form.tsx にログインフォームを実装する
  - web/src/app/(auth)/login/page.tsx にログインページを実装する
  - 認証ミドルウェアを設定する

---

## Task 3: 商品マスタ管理機能の実装 (P)

商品情報の CRUD 操作と一覧・詳細表示を実装する。

**Requirements covered:** 6.1.1, 6.1.2, 6.1.3, 6.1.4, 6.1.5

### Sub-tasks

- [x] 3.1 商品モデルとスキーマの定義
  - api/app/models/product.py に Product モデルを定義する（id, product_type, name, size, color, manufacturer_id, cost, lead_time_days, order_limit, is_active）
  - api/app/schemas/product.py に ProductCreate, ProductUpdate, ProductResponse スキーマを定義する
  - マイグレーションを作成・適用する

- [x] 3.2 商品 Repository と Service の実装
  - api/app/repositories/product_repository.py に ProductRepository を実装する（CRUD, 検索, ページネーション）
  - api/app/services/product_service.py に ProductService を実装する
  - api/app/dependencies.py に DI 関数を追加する

- [x] 3.3 商品 API エンドポイントの実装
  - api/app/routers/products.py に CRUD エンドポイントを実装する（GET /, POST /, GET /{id}, PATCH /{id}, DELETE /{id}）
  - 商品種類のバリデーション（アクリルキーホルダー、アクリルスタンド、ステッカー、マグカップ、Tシャツ）を実装する

- [x] 3.4 商品管理フロントエンドの実装
  - web/src/features/products/hooks/use-products.ts に SWR フックを実装する
  - web/src/features/products/components/product-list.tsx に商品一覧コンポーネントを実装する
  - web/src/features/products/components/product-form.tsx に登録・編集フォームを実装する
  - web/src/app/(dashboard)/products/ にページを実装する（一覧, 新規登録, 編集）

---

## Task 4: メーカー管理機能の実装 (P)

メーカー情報の CRUD 操作を実装する。

**Requirements covered:** 3.1.1, 3.1.2, 3.1.3, 3.1.4

### Sub-tasks

- [x] 4.1 メーカーモデルとスキーマの定義
  - api/app/models/manufacturer.py に Manufacturer モデルを定義する（id, name, email, phone, supported_products, unit_prices, lead_time_days, daily_order_limit, sharing_method, password_hash, is_active）
  - api/app/schemas/manufacturer.py に ManufacturerCreate, ManufacturerUpdate, ManufacturerResponse スキーマを定義する
  - マイグレーションを作成・適用する

- [x] 4.2 メーカー Repository と Service の実装
  - api/app/repositories/manufacturer_repository.py に ManufacturerRepository を実装する
  - api/app/services/manufacturer_service.py に ManufacturerService を実装する

- [x] 4.3 メーカー API エンドポイントの実装
  - api/app/routers/manufacturers.py に CRUD エンドポイントを実装する
  - 共有方式（DRIVE / portal）の選択機能を実装する

- [x] 4.4 メーカー管理フロントエンドの実装
  - web/src/features/manufacturers/hooks/use-manufacturers.ts に SWR フックを実装する
  - web/src/features/manufacturers/components/ にコンポーネントを実装する
  - web/src/app/(dashboard)/manufacturers/ にページを実装する

---

## Task 5: 受注 API の実装

外部販売サイトからの受注登録 API を実装する。

**Requirements covered:** 1.1.1, 1.1.2, 1.1.3, 1.1.4, 1.1.5, 1.1.6, 9.1.1, 9.1.2

### Sub-tasks

- [x] 5.1 受注モデルとスキーマの定義
  - api/app/models/order.py に Order モデルを定義する（id, order_number, status, product_id, product_name, price, quantity, customer_*, manufacturing_data_*, ordered_at, created_at, updated_at）
  - api/app/schemas/order.py に OrderCreate, OrderResponse, ManufacturingDataInfo スキーマを定義する
  - OrderStatus 列挙型を定義する（pending, ordered, manufacturing, delivered, shipping, completed）
  - マイグレーションを作成・適用する

- [x] 5.2 受注 Repository と Service の実装
  - api/app/repositories/order_repository.py に OrderRepository を実装する
  - api/app/services/order_service.py に OrderService を実装する
  - 商品マスタ照合、製造データ保存ロジックを実装する

- [x] 5.3 受注登録 API エンドポイントの実装
  - api/app/routers/orders.py に POST / エンドポイントを実装する
  - multipart/form-data で受注データと製造データ（1ファイル）を受け付ける
  - API Key 認証を適用する
  - バリデーションエラー時のエラーレスポンスを実装する

---

## Task 6: 受注一覧・詳細表示機能の実装

管理者向けの受注一覧・詳細表示機能を実装する。

**Requirements covered:** 1.2.1, 1.2.2, 1.2.3, 1.2.4

### Sub-tasks

- [x] 6.1 受注一覧 API の実装
  - api/app/routers/orders.py に GET / エンドポイントを実装する
  - 受注日、商品種別、ステータスによるフィルタリングを実装する
  - ページネーションを実装する

- [x] 6.2 受注詳細 API の実装
  - api/app/routers/orders.py に GET /{id} エンドポイントを実装する
  - 製造データのダウンロード URL を動的に生成する

- [x] 6.3 受注管理フロントエンドの実装
  - web/src/features/orders/hooks/use-orders.ts に SWR フックを実装する
  - web/src/features/orders/components/order-list.tsx に受注一覧コンポーネントを実装する
  - web/src/features/orders/components/order-filters.tsx にフィルター UI を実装する
  - web/src/features/orders/components/order-detail.tsx に受注詳細コンポーネントを実装する
  - web/src/features/orders/components/order-status-badge.tsx にステータスバッジを実装する
  - web/src/app/(dashboard)/orders/ にページを実装する

---

## Task 7: 発注管理機能の実装

メーカーへの発注作成とステータス管理を実装する。

**Requirements covered:** 2.1.1, 2.1.2, 2.1.3, 2.1.4, 2.4.1, 2.4.2, 2.4.3, 2.4.4

### Sub-tasks

- [x] 7.1 発注モデルとスキーマの定義
  - api/app/models/purchase_order.py に PurchaseOrder, PurchaseOrderItem モデルを定義する
  - api/app/schemas/purchase_order.py にスキーマを定義する
  - PurchaseOrderStatus 列挙型を定義する（ordered, manufacturing, delivered）
  - マイグレーションを作成・適用する

- [x] 7.2 発注 Repository と Service の実装
  - api/app/repositories/purchase_order_repository.py に PurchaseOrderRepository を実装する
  - api/app/services/purchase_order_service.py に PurchaseOrderService を実装する
  - 1日発注上限チェック、納期計算ロジックを実装する
  - ステータス更新履歴の記録を実装する

- [x] 7.3 発注 API エンドポイントの実装
  - api/app/routers/purchase_orders.py にエンドポイントを実装する（POST /, GET /, GET /{id}, PATCH /{id}/status）
  - 発注時に関連受注のステータスを「発注済み」に更新する

- [x] 7.4 発注管理フロントエンドの実装
  - web/src/features/purchase-orders/hooks/ に SWR フックを実装する
  - web/src/features/purchase-orders/components/ にコンポーネントを実装する
  - web/src/app/(dashboard)/purchase-orders/ にページを実装する
  - 発注作成時の受注選択 UI を実装する

---

## Task 8: 発注資料作成機能の実装

発注書・製造データの ZIP 化とダウンロード機能を実装する。

**Requirements covered:** 2.2.1, 2.2.2, 2.2.3, 2.2.4

### Sub-tasks

- [x] 8.1 Excel 生成機能の実装
  - api/app/utils/excel_generator.py に発注書 Excel 生成機能を実装する（openpyxl 使用）
  - 発注情報、商品一覧、メーカー情報をシートに出力する
  - スタイリング（ヘッダー、罫線、列幅）を適用する

- [x] 8.2 サムネイル生成と ZIP 化機能の実装
  - api/app/utils/thumbnail_generator.py にサムネイル生成機能を実装する
  - api/app/utils/zip_builder.py に ZIP 作成機能を実装する
  - ディレクトリ構成「[メーカー名][日付]発注分/」を実装する

- [x] 8.3 発注資料ダウンロード API の実装
  - api/app/routers/purchase_orders.py に GET /{id}/documents エンドポイントを実装する
  - xlsx, csv, zip 形式のダウンロードに対応する
  - StreamingResponse でファイルを返却する

- [x] 8.4 発注資料ダウンロード UI の実装
  - web/src/features/purchase-orders/components/purchase-order-documents.tsx にダウンロード UI を実装する
  - 形式選択とダウンロードボタンを実装する

---

## Task 9: メーカー専用ページの実装

メーカー向けのログイン・発注一覧・ダウンロード・ステータス更新機能を実装する。

**Requirements covered:** 4.1, 4.2, 4.3, 4.4, 4.5, 4.6

### Sub-tasks

- [x] 9.1 メーカー認証 API の実装
  - api/app/services/manufacturer_portal_service.py にメーカー認証ロジックを実装する
  - api/app/routers/manufacturer_portal.py に POST /login エンドポイントを実装する
  - api/app/dependencies.py に get_current_manufacturer 依存関数を実装する

- [x] 9.2 メーカー向け発注一覧・詳細 API の実装
  - api/app/routers/manufacturer_portal.py に GET /orders エンドポイントを実装する
  - メーカー ID に基づくデータアクセス制限を実装する
  - GET /orders/{id}/documents エンドポイントを実装する

- [x] 9.3 メーカー向けステータス更新 API の実装
  - api/app/routers/manufacturer_portal.py に PATCH /orders/{id}/status エンドポイントを実装する
  - 「製造中」への更新と備考入力を許可する

- [x] 9.4 メーカー専用ページフロントエンドの実装
  - web/src/features/auth/components/manufacturer-login-form.tsx にメーカーログインフォームを実装する
  - web/src/app/(manufacturer)/manufacturer-login/page.tsx にログインページを実装する
  - web/src/app/(manufacturer)/manufacturer/ に発注一覧・詳細ページを実装する
  - web/src/app/(manufacturer)/layout.tsx にメーカー向けレイアウトを実装する

---

## Task 10: 配送管理機能の実装

配送依頼・ステータス管理・梱包写真アップロード機能を実装する。

**Requirements covered:** 5.1.1, 5.1.2, 5.1.3, 5.3.1, 5.3.2, 5.3.3, 5.4.1, 5.4.2, 5.4.3, 5.4.4

### Sub-tasks

- [x] 10.1 配送モデルとスキーマの定義
  - api/app/models/shipment.py に Shipment, ShipmentItem モデルを定義する
  - api/app/schemas/shipment.py にスキーマを定義する
  - ShipmentStatus 列挙型を定義する（pending, ready, shipping, completed）
  - マイグレーションを作成・適用する

- [x] 10.2 配送 Repository と Service の実装
  - api/app/repositories/shipment_repository.py に ShipmentRepository を実装する
  - api/app/services/shipment_service.py に ShipmentService を実装する
  - ステータス遷移ルール（pending → ready → shipping → completed）を実装する

- [x] 10.3 配送 API エンドポイントの実装
  - api/app/routers/shipments.py にエンドポイントを実装する（POST /, GET /, GET /{id}, PATCH /{id}/status）
  - 梱包写真アップロード（POST /{id}/packing-photo）を実装する
  - 伝票番号 CSV インポート（POST /import-tracking）を実装する

- [x] 10.4 配送管理フロントエンドの実装
  - web/src/features/shipments/hooks/ に SWR フックを実装する
  - web/src/features/shipments/components/ にコンポーネントを実装する
  - web/src/features/shipments/components/packing-photo-upload.tsx に梱包写真アップロード UI を実装する
  - web/src/features/shipments/components/tracking-import.tsx に伝票番号インポート UI を実装する
  - web/src/app/(dashboard)/shipments/ にページを実装する

---

## Task 11: 配送資料作成機能の実装

配送代行用 CSV・配送ラベル CSV・同梱商品リストを生成する。

**Requirements covered:** 5.2.1, 5.2.2, 5.2.3, 5.2.4, 5.2.5, 9.3.1, 9.3.2

### Sub-tasks

- [x] 11.1 CSV 生成機能の実装
  - api/app/utils/csv_generator.py に配送代行用 CSV 生成機能を実装する
  - 各運送会社フォーマットの配送ラベル CSV 生成機能を実装する
  - 同梱ルール（同一注文番号・当日処理分）を実装する

- [x] 11.2 同梱商品リスト生成機能の実装
  - 注文番号ごとの同梱商品リスト生成機能を実装する
  - サムネイル画像付きのリスト形式を実装する

- [x] 11.3 配送資料ダウンロード API の実装
  - api/app/routers/shipments.py に GET /{id}/documents エンドポイントを実装する
  - 各種フォーマットのダウンロードに対応する

- [x] 11.4 配送資料ダウンロード UI の実装
  - web/src/features/shipments/components/shipment-documents.tsx にダウンロード UI を実装する

---

## Task 12: メーカーチャット機能の実装

メーカーとの簡易チャット機能を実装する。

**Requirements covered:** 3.2.1, 3.2.2, 3.2.3, 3.2.4

### Sub-tasks

- [x] 12.1 チャットモデルとスキーマの定義
  - api/app/models/chat_message.py に ChatMessage, Attachment モデルを定義する
  - api/app/schemas/chat.py にスキーマを定義する
  - マイグレーションを作成・適用する

- [x] 12.2 チャット Repository と Service の実装
  - api/app/repositories/chat_repository.py に ChatRepository を実装する
  - api/app/services/chat_service.py に ChatService を実装する
  - ファイル添付機能を実装する

- [x] 12.3 チャット API エンドポイントの実装
  - api/app/routers/chat.py にエンドポイントを実装する（GET /manufacturers/{id}/chat, POST /manufacturers/{id}/chat）
  - メッセージ取得（ページネーション付き）とメッセージ送信を実装する

- [x] 12.4 チャット UI の実装
  - web/src/features/manufacturers/components/manufacturer-chat.tsx にチャット UI を実装する
  - メッセージ一覧、送信フォーム、ファイル添付 UI を実装する
  - web/src/app/(dashboard)/manufacturers/[id]/chat/page.tsx にチャットページを実装する

---

## Task 13: ダッシュボード機能の実装

受注・発注・配送の状況サマリを表示するダッシュボードを実装する。

**Requirements covered:** 7.1.1, 7.1.2, 7.1.3

### Sub-tasks

- [x] 13.1 ダッシュボード API の実装
  - api/app/schemas/dashboard.py に DashboardSummary スキーマを定義する
  - api/app/services/dashboard_service.py に集計ロジックを実装する
  - api/app/routers/dashboard.py に GET /summary エンドポイントを実装する
  - 本日の受注・発注・配送件数、各ステータス件数、アラート情報を集計する

- [x] 13.2 ダッシュボードフロントエンドの実装
  - web/src/features/dashboard/hooks/use-dashboard.ts に SWR フックを実装する
  - web/src/features/dashboard/components/dashboard-summary.tsx にサマリーカードを実装する
  - web/src/features/dashboard/components/status-cards.tsx にステータス別件数を表示する
  - web/src/features/dashboard/components/alert-list.tsx にアラート一覧を実装する
  - web/src/app/(dashboard)/page.tsx にダッシュボードページを実装する

---

## Task 14: 共通 UI コンポーネントとレイアウトの実装 (P)

共通 UI コンポーネントとアプリケーションレイアウトを実装する。

**Requirements covered:** 1.2.4, 2.4.1, 5.4.1

### Sub-tasks

- [x] 14.1 shadcn/ui コンポーネントのセットアップ
  - 必要なコンポーネントを追加する（button, input, table, dialog, form, select, badge, card, tabs, toast）
  - テーマカスタマイズを行う

- [x] 14.2 共通コンポーネントの実装
  - web/src/components/common/data-table.tsx にページネーション付きテーブルを実装する
  - web/src/components/common/pagination.tsx にページネーション UI を実装する
  - web/src/components/common/loading-spinner.tsx にローディング表示を実装する
  - web/src/components/common/error-boundary.tsx にエラーバウンダリを実装する
  - web/src/components/common/file-upload.tsx にファイルアップロード UI を実装する
  - web/src/components/common/status-badge.tsx にステータスバッジを実装する

- [x] 14.3 レイアウトコンポーネントの実装
  - web/src/components/layout/header.tsx にヘッダーを実装する
  - web/src/components/layout/sidebar.tsx にサイドバーナビゲーションを実装する
  - web/src/components/layout/page-container.tsx にページコンテナを実装する
  - web/src/app/(dashboard)/layout.tsx にダッシュボードレイアウトを実装する

---

## Task 15: 発注自動化機能の実装

受注登録時の自動メーカー振り分けと DRIVE アップロード機能を実装する。

**Requirements covered:** 2.3.1, 2.3.2, 2.3.3, 2.3.4, 2.3.5, 9.2.1

### Sub-tasks

- [x] 15.1 自動メーカー振り分けロジックの実装
  - api/app/services/order_service.py に自動振り分けロジックを追加する
  - 商品マスタの製造メーカー情報を元に発注先を決定する
  - 1日発注件数の記録と上限チェックを実装する

- [x] 15.2 TOSYO DRIVE 連携クライアントの実装
  - api/app/utils/drive_client.py に DRIVE アップロード機能のインターフェースを実装する
  - 共有方式が「DRIVE」の場合のみアップロードを実行する
  - アップロード完了通知を実装する

- [x]* 15.3 自動化フローのテスト
  - 受注登録 → メーカー振り分け → 発注作成 → DRIVE アップロードの一連のフローをテストする

---

## Task 16: OpenAPI スキーマ生成と型連携

FastAPI から OpenAPI スキーマを生成し、フロントエンドの型を自動生成する。

**Requirements covered:** 8.3.1

### Sub-tasks

- [x] 16.1 OpenAPI スキーマ生成スクリプトの実装
  - api/app/main.py に OpenAPI スキーマ出力機能を追加する
  - openapi/schema.yaml にスキーマを出力するスクリプトを作成する

- [x] 16.2 フロントエンド型生成の設定
  - web/package.json に型生成スクリプトを追加する（openapi-typescript）
  - web/src/types/api/generated.ts に型を生成する
  - web/src/types/index.ts に型エイリアスを定義する

- [x] 16.3 API クライアントの型安全化
  - web/src/lib/api/client.ts に型安全な API クライアントを実装する
  - 各ドメインの API 関数に型を適用する

---

## Requirements Coverage

| 要件 ID | タスク |
|--------|--------|
| 1.1.1, 1.1.2, 1.1.3, 1.1.4, 1.1.5, 1.1.6 | Task 5 |
| 1.2.1, 1.2.2, 1.2.3, 1.2.4 | Task 6, Task 14 |
| 2.1.1, 2.1.2, 2.1.3, 2.1.4 | Task 7 |
| 2.2.1, 2.2.2, 2.2.3, 2.2.4 | Task 8 |
| 2.3.1, 2.3.2, 2.3.3, 2.3.4, 2.3.5 | Task 15 |
| 2.4.1, 2.4.2, 2.4.3, 2.4.4 | Task 7 |
| 3.1.1, 3.1.2, 3.1.3, 3.1.4 | Task 4 |
| 3.2.1, 3.2.2, 3.2.3, 3.2.4 | Task 12 |
| 4.1, 4.2, 4.3, 4.4, 4.5, 4.6 | Task 9 |
| 5.1.1, 5.1.2, 5.1.3 | Task 10 |
| 5.2.1, 5.2.2, 5.2.3, 5.2.4, 5.2.5 | Task 11 |
| 5.3.1, 5.3.2, 5.3.3 | Task 10 |
| 5.4.1, 5.4.2, 5.4.3, 5.4.4 | Task 10, Task 14 |
| 6.1.1, 6.1.2, 6.1.3, 6.1.4, 6.1.5 | Task 3 |
| 7.1.1, 7.1.2, 7.1.3 | Task 13 |
| 8.1.1, 8.1.2, 8.2.1 | Task 1 |
| 8.3.1, 8.3.2, 8.3.3 | Task 2 |
| 9.1.1, 9.1.2 | Task 5 |
| 9.2.1 | Task 15 |
| 9.3.1, 9.3.2 | Task 11 |

---

## Task 17: 詳細ページとフォームの実装

design.md の File Structure に記載されているが未実装だった詳細ページ・フォームを実装する。

**Requirements covered:** 1.2.2, 1.2.3, 2.4.1, 3.1.2, 3.1.3, 4.3, 5.4.2, 6.1.2, 6.1.3

### Sub-tasks

- [x] 17.1 受注詳細ページの実装
  - web/src/features/orders/components/order-detail.tsx に受注詳細コンポーネントを実装する
  - web/src/app/(dashboard)/orders/[id]/page.tsx に受注詳細ページを実装する
  - 受注情報、顧客情報、製造データダウンロード、ステータス表示を含める

- [x] 17.2 発注詳細ページの実装
  - web/src/features/purchase-orders/components/purchase-order-detail.tsx に発注詳細コンポーネントを実装する
  - web/src/app/(dashboard)/purchase-orders/[id]/page.tsx に発注詳細ページを実装する
  - 発注情報、含まれる受注一覧、ステータス更新 UI、ダウンロード機能を含める

- [x] 17.3 メーカー詳細・編集ページの実装
  - web/src/features/manufacturers/components/manufacturer-form.tsx にメーカー登録・編集フォームを実装する
  - web/src/app/(dashboard)/manufacturers/[id]/page.tsx にメーカー詳細・編集ページを実装する
  - 対応商品、単価設定、共有方式、1日発注上限の編集を含める

- [x] 17.4 配送詳細ページの実装
  - web/src/features/shipments/components/shipment-detail.tsx に配送詳細コンポーネントを実装する
  - web/src/app/(dashboard)/shipments/[id]/page.tsx に配送詳細ページを実装する
  - 配送先情報、含まれる商品一覧、ステータス更新、梱包写真アップロードを含める

- [x] 17.5 商品登録・編集ページの実装
  - web/src/features/products/components/product-form.tsx に商品登録・編集フォームを実装する
  - web/src/app/(dashboard)/products/new/page.tsx に商品新規登録ページを実装する
  - web/src/app/(dashboard)/products/[id]/page.tsx に商品編集ページを実装する
  - 商品種別選択、メーカー選択、原価、リードタイム設定を含める

- [x] 17.6 メーカー向け発注詳細ページの実装
  - web/src/app/(manufacturer)/manufacturer/[id]/page.tsx にメーカー向け発注詳細ページを実装する
  - 発注情報、含まれる受注一覧、ダウンロード機能、ステータス更新 UI を含める

- [x] 17.7 発注作成フローの実装
  - web/src/features/purchase-orders/components/create-purchase-order-form.tsx に発注作成フォームを実装する
  - web/src/app/(dashboard)/purchase-orders/new/page.tsx に発注作成ページを実装する
  - 受注選択 UI、メーカー選択、発注確認を実装する

---

*Generated: 2025-12-27*
*Updated: 2025-12-28 - Task 17 追加（詳細ページとフォームの実装漏れ対応）*
*Updated: 2025-12-28 - Task 17 完了*
