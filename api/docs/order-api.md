# 受注API仕様書

外部販売サイトからPOD管理システムへ受注データを連携するためのAPIドキュメントです。

## 目次

1. [概要](#概要)
2. [認証](#認証)
3. [エンドポイント一覧](#エンドポイント一覧)
4. [受注作成API](#受注作成api)
5. [受注作成API（v2・製造データ生成方式）](#受注作成apiv2製造データ生成方式)
6. [注文ステータス取得API](#注文ステータス取得api)
7. [商品属性取得API](#商品属性取得api)
8. [価格取得API](#価格取得api)
9. [注文取り消しAPI](#注文取り消しapi)
10. [エラーハンドリング](#エラーハンドリング)
11. [データ定義](#データ定義)
12. [サンプルコード](#サンプルコード)

---

## 概要

### ベースURL

```
本番環境: https://api.example.com/api/v1
開発環境: http://localhost:8000/api/v1
```

### 通信仕様

- プロトコル: HTTPS（本番環境）
- データ形式: JSON
- 文字コード: UTF-8
- Content-Type: `application/json`

### 商品識別の概念

本APIでは以下のフィールドを使用して商品を識別します：

| フィールド | 説明 | 例 |
|-----------|------|-----|
| `uid` | 製品番号（7桁数字） | `"0000001"` |
| `product_type` | 製造種類（商品タイプ） | `"tshirt"` |

**例**: 外部サイトで販売している「オリジナルTシャツA」（uid: `0000001`）を、Tシャツ（product_type: `tshirt`）として製造する。

---

## 認証

### API Key認証

すべてのリクエストにはAPIキーが必要です。

**ヘッダー名**: `X-API-Key`

```http
X-API-Key: your-api-key-here
```

APIキーは事前に発行されたものをご使用ください。

### 認証エラー

| ステータスコード | 説明 |
|-----------------|------|
| 401 Unauthorized | APIキーが未指定または無効 |

---

## エンドポイント一覧

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| `/api/v1/orders` | POST | 受注作成（v1・完成デザインURL方式） |
| `/api/v2/orders` | POST | 受注作成（v2・製造データ生成方式） |
| `/api/v1/external/orders/{order_number}/status` | GET | 注文ステータス取得 |
| `/api/v1/external/product-options/{product_type}` | GET | 商品属性取得 |
| `/api/v1/external/price-calculation` | POST | 価格取得 |
| `/api/v1/external/orders/{order_number}/cancel` | POST | 注文取り消し |

---

## 受注作成API

外部販売サイトから新規受注を登録します。

```
POST /api/v1/orders
```

| 項目 | 内容 |
|------|------|
| メソッド | POST |
| URL | `/api/v1/orders` |
| 認証 | API Key（`X-API-Key`ヘッダー） |
| Content-Type | `application/json` |
| レスポンス | 201 Created（成功時） |

### リクエストボディ

```json
{
  "order_number": "0000001",
  "customer": {
    "name": "山田太郎",
    "postal_code": "123-4567",
    "address_prefecture": "東京都",
    "address_city": "渋谷区〇〇町1-2-3",
    "address_building": "○○ビル101",
    "phone": "03-1234-5678",
    "email": "yamada@example.com"
  },
  "items": [
    {
      "uid": "0000011",
      "product_type": "tshirt",
      "product_name": "オリジナルTシャツ デザインA",
      "price": 2500,
      "quantity": 2,
      "size": "M",
      "position": "正面",
      "color": "白",
      "design_image_url": "https://example.com/designs/design1.png",
      "thumbnail_image_url": "https://example.com/thumbnails/thumb1.png"
    }
  ]
}
```

### パラメータ詳細

#### ルートレベル

| フィールド | 型 | 必須 | 説明 | 制約 |
|-----------|-----|:---:|------|------|
| order_number | string | ○ | 受注番号（7桁数字） | 7桁数字、ユニーク |
| customer | object | ○ | 顧客情報 | 下記参照 |
| items | array | ○ | 受注明細（商品リスト） | 1件以上必須 |

#### customer（顧客情報）

| フィールド | 型 | 必須 | 説明 | 制約 |
|-----------|-----|:---:|------|------|
| name | string | ○ | 顧客名 | 1-100文字 |
| postal_code | string | ○ | 郵便番号 | 1-10文字 |
| address_prefecture | string | ○ | 都道府県 | 1-50文字 |
| address_city | string | ○ | 市区町村以降 | 1文字以上 |
| address_building | string | - | 建物名等 | 最大200文字 |
| phone | string | ○ | 電話番号 | 1-20文字 |
| email | string | - | メールアドレス | Email形式 |

#### items（受注明細）

| フィールド | 型 | 必須 | 説明 | 制約 |
|-----------|-----|:---:|------|------|
| uid | string | ○ | 製品番号（7桁数字） | 7桁数字 |
| product_type | string | ○ | 製造種類（商品タイプ） | 有効値: tshirt, acrylic_keychain, acrylic_stand, sticker, tote_bag |
| product_name | string | ○ | 外部販売サイトの商品名 | 1-200文字 |
| price | integer | ○ | 単価（税込） | 0以上 |
| quantity | integer | ○ | 数量 | 1以上（デフォルト: 1） |
| size | string | 条件付 | サイズ | 最大50文字。全商品タイプで必須。有効値は商品タイプ別（下記参照） |
| position | string | 条件付 | 印刷位置 | 最大50文字。Tシャツ・トートバッグで必須（有効値: 正面） |
| color | string | 条件付 | カラー | 最大50文字。Tシャツ・ステッカー・トートバッグで必須。有効値は商品タイプ別（下記参照） |
| design_image_url | string | - | デザイン画像URL | 最大2048文字 |
| thumbnail_image_url | string | - | サムネイル画像URL | 最大2048文字 |

**商品タイプ別のバリデーション**:

| 商品タイプ | size | color | position |
|-----------|:----:|:-----:|:--------:|
| tshirt | 必須 | 必須 | 必須 |
| acrylic_keychain | 必須 | 任意 | - |
| acrylic_stand | 必須 | 任意 | - |
| sticker | 必須 | 必須 | - |
| tote_bag | 必須 | 必須 | 必須 |

**各商品タイプの有効値**:

- **Tシャツ** (`product_type: tshirt`)
  - `size`: `S`, `M`, `L`, `XL`
  - `color`: `白`
  - `position`: `正面`

- **アクリルキーホルダー** (`product_type: acrylic_keychain`)
  - `size`: `50x50mm`, `70x70mm`, `100x100mm`
  - `color`: `アクリル`（任意）

- **アクリルスタンド** (`product_type: acrylic_stand`)
  - `size`: `50x50mm`, `70x70mm`, `100x100mm`
  - `color`: `アクリル`（任意）

- **ステッカー** (`product_type: sticker`)
  - `size`: `50x50mm`, `70x70mm`, `100x100mm`
  - `color`: `ホワイト`

- **トートバッグ** (`product_type: tote_bag`)
  - `size`: `M`
  - `color`: `ナチュラル`
  - `position`: `正面`

---

### 成功時（201 Created）

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "order_number": "0000001",
  "status": "ordered",
  "source": "RKSYO",
  "order_source_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "customer_name": "山田太郎",
  "customer_postal_code": "123-4567",
  "customer_address_prefecture": "東京都",
  "customer_address_city": "渋谷区〇〇町1-2-3",
  "customer_address_building": "○○ビル101",
  "customer_full_address": "東京都渋谷区〇〇町1-2-3○○ビル101",
  "customer_phone": "03-1234-5678",
  "customer_email": "yamada@example.com",
  "ordered_at": "2024-01-15T10:30:00+09:00",
  "total_price": 5000,
  "estimated_shipping_date": "2024-01-25",
  "items": [
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "uid": "0000011",
      "product_name": "オリジナルTシャツ デザインA",
      "product_type": "tshirt",
      "price": 2500,
      "quantity": 2,
      "size": "M",
      "position": "正面",
      "color": "白",
      "design_image_url": "https://example.com/designs/design1.png",
      "thumbnail_image_url": "https://example.com/thumbnails/thumb1.png",
      "expected_delivery_date": "2024-01-18",
      "status": "ordered",
      "product_code": null,
      "manufacturing_data": null,
      "created_at": "2024-01-15T10:30:00+09:00",
      "updated_at": "2024-01-15T10:30:00+09:00"
    }
  ],
  "shipment": null,
  "product_id": null,
  "product_name": null,
  "price": null,
  "quantity": null,
  "manufacturing_data": null,
  "created_at": "2024-01-15T10:30:00+09:00",
  "updated_at": "2024-01-15T10:30:00+09:00"
}
```

### レスポンスフィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| id | string | 受注ID（UUID） |
| order_number | string | 受注番号 |
| status | string | 受注ステータス（初期値: `ordered`） |
| source | string \| null | 受注元コード（order_source.codeから算出） |
| order_source_id | string \| null | 受注元ID（UUID） |
| customer_name | string | 顧客名 |
| customer_postal_code | string | 郵便番号 |
| customer_address_prefecture | string | 都道府県 |
| customer_address_city | string | 市区町村以降 |
| customer_address_building | string \| null | 建物名等 |
| customer_full_address | string | 住所（結合済み、自動生成） |
| customer_phone | string | 電話番号 |
| customer_email | string \| null | メールアドレス |
| ordered_at | datetime | 受注日時（サーバ側でJST現在時刻を採番。リクエストでは指定不可） |
| total_price | integer | 合計金額（各明細の price × quantity の合計。サーバ側で自動計算） |
| estimated_shipping_date | string(date) \| null | 配送予定日（`YYYY-MM-DD`。各明細の納品予定日の最大＋発送準備日数を営業日計算） |
| items | array | 受注明細 |
| shipment | object \| null | 出荷情報（納入済み以降で設定） |
| product_id | string \| null | レガシー項目（後方互換のため保持。通常 `null`） |
| product_name | string \| null | レガシー項目（後方互換のため保持。通常 `null`） |
| price | integer \| null | レガシー項目（後方互換のため保持。通常 `null`） |
| quantity | integer \| null | レガシー項目（後方互換のため保持。通常 `null`） |
| manufacturing_data | object \| null | レガシー項目（後方互換のため保持。通常 `null`） |
| created_at | datetime | 作成日時 |
| updated_at | datetime | 更新日時 |

#### items（レスポンス）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| id | string | 受注明細ID（UUID） |
| uid | string | 製品番号（7桁数字） |
| product_name | string | 外部販売サイトの商品名 |
| product_type | string | 製造種類（商品タイプ） |
| price | integer | 単価 |
| quantity | integer | 数量 |
| size | string \| null | サイズ |
| position | string \| null | 印刷位置 |
| color | string \| null | カラー |
| design_image_url | string \| null | デザイン画像URL |
| thumbnail_image_url | string \| null | サムネイル画像URL |
| expected_delivery_date | string(date) \| null | メーカーからの納品予定日（`YYYY-MM-DD`。受注日＋商品リードタイムを営業日計算） |
| status | string | 明細単位のステータス（`preparing_order` / `ordered` / `manufacturing` / `delivered` / `cancelled`。v1は `ordered` から開始。注文が取り消されると全明細が `cancelled` になる） |
| product_code | string \| null | v2用の商品識別子（v1は `null`） |
| manufacturing_data | object \| null | v2用の製造データ状態（v1は `null`。下記参照） |
| created_at | datetime | 作成日時 |
| updated_at | datetime | 更新日時 |

#### manufacturing_data（明細・v2のみ）

v2（製造データ生成方式）で作成された明細にのみ設定されます。v1明細では常に `null` です。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| id | string | 製造データID |
| status | string | 生成状態（`pending` / `generating` / `ready` / `failed`） |
| output_filename | string \| null | 生成済みファイル名 |
| file_size | integer \| null | ファイルサイズ（バイト） |
| error_message | string \| null | 失敗時のエラーメッセージ |

#### shipment（出荷情報）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| id | string | 出荷ID（UUID） |
| status | string | 出荷ステータス（`pending`, `ready`, `shipped`） |
| tracking_number | string \| null | 追跡番号 |
| carrier | string \| null | 配送業者 |

---

## 受注作成API（v2・製造データ生成方式）

完成デザインURLの代わりに、製造データ生成用の元データ（PNGレイヤーのURL）を受け取ります。受注後にシステム側で製造データを生成します（同一商品はキャッシュを再利用）。既存の v1（`POST /api/v1/orders`）とは**別プレフィックス**のため、v1連携には影響しません。

```
POST /api/v2/orders
```

| 項目 | 内容 |
|------|------|
| メソッド | POST |
| URL | `/api/v2/orders` |
| 認証 | API Key（`X-API-Key`ヘッダー） |
| Content-Type | `application/json` |
| レスポンス | 201 Created（成功時。**v1と同一の受注レスポンス**。`estimated_shipping_date` や明細の `expected_delivery_date` を含む） |

### v1との差分

- 明細（items）は `design_image_url` を**受け付けません**。代わりに下記の `product_code` と `source_images` を指定します。
- `items` は1注文あたり最大100件、`source_images` は明細あたり最大8件（DoS防御）。
- 顧客情報・`order_number`・その他の明細フィールド（`uid`, `product_type`, `product_name`, `price`, `quantity`, `size`, `position`, `color`, `thumbnail_image_url`）は v1 と同じです。
- 製造データを生成できる入力か（商品タイプ・サイズ・必須レイヤー）を受注時に同期検証し、不備は `400 VALIDATION_ERROR` を返します。

#### items（v2固有フィールド）

| フィールド | 型 | 必須 | 説明 | 制約 |
|-----------|-----|:---:|------|------|
| product_code | string | ○ | 製造データのキャッシュキー（商品識別子） | 1-255文字 |
| source_images | array | ○ | 製造データ生成の元データ（レイヤーPNG） | 1-8件 |
| source_images[].layer_type | string | ○ | レイヤー種別 | `color`, `cutline`, `white`, `design` |
| source_images[].url | string | ○ | レイヤーPNGのURL | 1-2048文字 |

### リクエストボディ例

```json
{
  "order_number": "0000001",
  "customer": {
    "name": "山田太郎",
    "postal_code": "123-4567",
    "address_prefecture": "東京都",
    "address_city": "渋谷区〇〇町1-2-3",
    "address_building": "○○ビル101",
    "phone": "03-1234-5678",
    "email": "yamada@example.com"
  },
  "items": [
    {
      "uid": "0000011",
      "product_type": "acrylic_keychain",
      "product_name": "アクリルキーホルダー デザインA",
      "price": 1200,
      "quantity": 1,
      "size": "50x50mm",
      "color": "アクリル",
      "product_code": "RKSYO-AKC-001",
      "source_images": [
        {"layer_type": "color", "url": "https://example.com/layers/color.png"},
        {"layer_type": "cutline", "url": "https://example.com/layers/cutline.png"}
      ],
      "thumbnail_image_url": "https://example.com/thumbnails/thumb1.png"
    }
  ]
}
```

---

## 注文ステータス取得API

指定した注文番号の現在のステータスを取得します。

```
GET /api/v1/external/orders/{order_number}/status
```

| 項目 | 内容 |
|------|------|
| メソッド | GET |
| URL | `/api/v1/external/orders/{order_number}/status` |
| 認証 | API Key（`X-API-Key`ヘッダー） |
| レスポンス | 200 OK（成功時） |

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|:---:|------|
| order_number | string | ○ | 注文番号（受注作成時に指定したもの） |

### レスポンス例

```json
{
  "order_number": "0000001",
  "status": "manufacturing",
  "ordered_at": "2024-01-15T10:30:00+09:00",
  "updated_at": "2024-01-16T14:00:00+09:00"
}
```

### レスポンスフィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| order_number | string | 注文番号 |
| status | string | 現在のステータス（`preparing_order`, `ordered`, `manufacturing`, `delivered`, `shipped`, `cancelled`） |
| ordered_at | datetime | 受注日時 |
| updated_at | datetime | 最終更新日時 |

### エラー例

#### 注文が見つからない（404 Not Found）

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Order with order_number 'ORD-INVALID' not found"
  }
}
```

### cURL例

```bash
curl -X GET "https://api.example.com/api/v1/external/orders/0000001/status" \
  -H "X-API-Key: your-api-key-here"
```

---

## 注文取り消しAPI

指定した注文番号の注文を取り消します。`ordered`（発注済み）ステータスの注文のみ取り消し可能です。
取り消すと配下の受注明細のステータスも全て `cancelled` になり、メーカー画面・メーカーポータルでも「キャンセル済み」として表示されます（発注資料の対象からも外れます）。

```
POST /api/v1/external/orders/{order_number}/cancel
```

| 項目 | 内容 |
|------|------|
| メソッド | POST |
| URL | `/api/v1/external/orders/{order_number}/cancel` |
| 認証 | API Key（`X-API-Key`ヘッダー） |
| レスポンス | 200 OK（成功時） |

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|:---:|------|
| order_number | string | ○ | 注文番号（受注作成時に指定したもの） |

### レスポンス例

```json
{
  "order_number": "0000001",
  "status": "cancelled",
  "cancelled_at": "2024-01-15T12:00:00+09:00"
}
```

### レスポンスフィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| order_number | string | 注文番号 |
| status | string | 取り消し後のステータス（常に`cancelled`） |
| cancelled_at | datetime | 取り消し日時 |

### エラー例

#### 注文が見つからない（404 Not Found）

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "order with id ORD-INVALID not found"
  }
}
```

#### 取り消し不可ステータス（409 Conflict）

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "発注中の注文のみ取り消せます"
  }
}
```

### cURL例

```bash
curl -X POST "https://api.example.com/api/v1/external/orders/0000001/cancel" \
  -H "X-API-Key: your-api-key-here"
```

---

## エラーハンドリング

### エラーレスポンス形式

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーメッセージ",
    "details": {}
  }
}
```

### エラーコード一覧

| HTTPステータス | code | 説明 | 対処法 |
|---------------|------|------|--------|
| 400 | VALIDATION_ERROR | リクエストパラメータ不正（属性値不正など） | リクエスト内容を確認 |
| 401 | UNAUTHORIZED | 認証失敗 | APIキーを確認 |
| 404 | NOT_FOUND | 商品マスタ・注文が見つからない | product_type / order_number を確認 |
| 409 | DUPLICATE | 受注番号の重複 | order_number を変更 |
| 409 | CONFLICT | 状態競合（取り消し不可な注文など） | 注文の現在ステータスを確認 |
| 422 | （detail形式） | 入力形式エラー（`error` エンベロープではなく `detail` 配列で返却） | リクエスト形式を確認 |
| 500 | INTERNAL_ERROR | サーバーエラー | 管理者に連絡 |

### エラー例

#### 受注番号重複（409 Conflict）

```json
{
  "error": {
    "code": "DUPLICATE",
    "message": "Order with order_number '0000001' already exists"
  }
}
```

#### 商品マスタが見つからない（404 Not Found）

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Product with id tshirt not found"
  }
}
```

#### Tシャツ：size/color/positionが未指定（400 Bad Request）

Tシャツに対して、`size`、`color`、`position` を未指定で送信した場合：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "size is required for T-shirt (uid: 0000011)"
  }
}
```

#### Tシャツ：無効な属性値（400 Bad Request）

Tシャツに対して、許可されていない値を指定した場合：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid size 'XXL'. Valid: ['S', 'M', 'L', 'XL'] (uid: 0000011)"
  }
}
```

#### バリデーションエラー（422 Unprocessable Entity）

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "customer", "email"],
      "msg": "value is not a valid email address",
      "input": "invalid-email"
    }
  ]
}
```

---

## データ定義

### 製造種類（product_type）

`product_type` はリクエストの各明細で直接指定します。POD管理システムは `product_type` に対応する商品マスタを検索して明細に紐づけます。

| 値 | 説明 |
|----|------|
| acrylic_keychain | アクリルキーホルダー |
| acrylic_stand | アクリルスタンド |
| sticker | ステッカー |
| tote_bag | トートバッグ |
| tshirt | Tシャツ |

### 受注ステータス（status）

受注作成時は必ず `ordered` で登録されます。

| 値 | 説明 |
|----|------|
| preparing_order | 発注準備中（製造データ未準備。主にv2で使用） |
| ordered | 発注済み（v1の初期ステータス） |
| manufacturing | 製造中 |
| delivered | 納入済み |
| shipped | 発送完了（最終ステータス） |
| cancelled | 取り消し済み |

### Tシャツ属性値

Tシャツ（`product_type: tshirt`）の場合、以下の値のみ許可されます。

#### サイズ（size）

| 値 | 説明 |
|----|------|
| S | Sサイズ |
| M | Mサイズ |
| L | Lサイズ |
| XL | XLサイズ |

#### カラー（color）

| 値 | 説明 |
|----|------|
| 白 | ホワイト |

#### プリント位置（position）

| 値 | 説明 |
|----|------|
| 正面 | フロントプリント |

### アクリルキーホルダー属性値

アクリルキーホルダー（`product_type: acrylic_keychain`）の場合、以下の値のみ許可されます。

#### サイズ（size）

| 値 | 説明 | 原価 |
|----|------|------|
| 50x50mm | 50x50mm | 285円 |
| 70x70mm | 70x70mm | 350円 |
| 100x100mm | 100x100mm | 475円 |

#### カラー（color）※任意

| 値 | 説明 |
|----|------|
| アクリル | アクリル素材 |

### アクリルスタンド属性値

アクリルスタンド（`product_type: acrylic_stand`）の場合、以下の値のみ許可されます。

#### サイズ（size）

| 値 | 説明 | 原価 |
|----|------|------|
| 50x50mm | 50x50mm | 310円 |
| 70x70mm | 70x70mm | 345円 |
| 100x100mm | 100x100mm | 735円 |

#### カラー（color）※任意

| 値 | 説明 |
|----|------|
| アクリル | アクリル素材 |

### ステッカー属性値

ステッカー（`product_type: sticker`）の場合、以下の値のみ許可されます。

#### サイズ（size）

| 値 | 説明 | 原価 |
|----|------|------|
| 50x50mm | 50x50mm | 50円 |
| 70x70mm | 70x70mm | 59円 |
| 100x100mm | 100x100mm | 79円 |

#### カラー（color）

| 値 | 説明 |
|----|------|
| ホワイト | 白 |

### トートバッグ属性値

トートバッグ（`product_type: tote_bag`）の場合、以下の値のみ許可されます。

#### サイズ（size）

| 値 | 説明 |
|----|------|
| M | Mサイズ |

#### カラー（color）

| 値 | 説明 |
|----|------|
| ナチュラル | ナチュラルカラー |

#### プリント位置（position）

| 値 | 説明 |
|----|------|
| 正面 | フロントプリント |

---

## 商品属性取得API

指定した商品タイプの選択可能な属性（サイズ、色、位置）を取得します。

```
GET /api/v1/external/product-options/{product_type}
```

| 項目 | 内容 |
|------|------|
| メソッド | GET |
| URL | `/api/v1/external/product-options/{product_type}` |
| 認証 | API Key（`X-API-Key`ヘッダー） |
| レスポンス | 200 OK（成功時） |

### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|:---:|------|
| product_type | string | ○ | 製造種類（`tshirt`, `acrylic_keychain`, `acrylic_stand`, `sticker`, `tote_bag`） |

### レスポンス例

#### Tシャツの場合

```json
{
  "product_type": "tshirt",
  "size": ["S", "M", "L", "XL"],
  "color": ["白"],
  "position": ["正面"]
}
```

#### アクリルキーホルダーの場合

```json
{
  "product_type": "acrylic_keychain",
  "size": ["50x50mm", "70x70mm", "100x100mm"],
  "color": ["アクリル"],
  "position": []
}
```

#### アクリルスタンドの場合

```json
{
  "product_type": "acrylic_stand",
  "size": ["50x50mm", "70x70mm", "100x100mm"],
  "color": ["アクリル"],
  "position": []
}
```

#### ステッカーの場合

```json
{
  "product_type": "sticker",
  "size": ["50x50mm", "70x70mm", "100x100mm"],
  "color": ["ホワイト"],
  "position": []
}
```

#### トートバッグの場合

```json
{
  "product_type": "tote_bag",
  "size": ["M"],
  "color": ["ナチュラル"],
  "position": ["正面"]
}
```

### レスポンスフィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| product_type | string | 製造種類 |
| size | array[string] | 選択可能なサイズのリスト |
| color | array[string] | 選択可能なカラーのリスト |
| position | array[string] | 選択可能なプリント位置のリスト |

### エラー例

#### 無効・未対応の商品タイプ（422 Unprocessable Entity）

`product_type` に enum 定義外の値（例: `mug`）を指定した場合、パスパラメータ検証で 422 が返ります。

```json
{
  "detail": [
    {
      "type": "enum",
      "loc": ["path", "product_type"],
      "msg": "Input should be 'acrylic_keychain', 'acrylic_stand', 'sticker', 'tote_bag' or 'tshirt'",
      "input": "mug"
    }
  ]
}
```

### cURL例

```bash
# Tシャツ
curl -X GET "https://api.example.com/api/v1/external/product-options/tshirt" \
  -H "X-API-Key: your-api-key-here"

# アクリルキーホルダー
curl -X GET "https://api.example.com/api/v1/external/product-options/acrylic_keychain" \
  -H "X-API-Key: your-api-key-here"

# アクリルスタンド
curl -X GET "https://api.example.com/api/v1/external/product-options/acrylic_stand" \
  -H "X-API-Key: your-api-key-here"

# ステッカー
curl -X GET "https://api.example.com/api/v1/external/product-options/sticker" \
  -H "X-API-Key: your-api-key-here"

# トートバッグ
curl -X GET "https://api.example.com/api/v1/external/product-options/tote_bag" \
  -H "X-API-Key: your-api-key-here"
```

---

## 価格取得API

指定した商品タイプと属性の組み合わせで価格を取得します。

```
POST /api/v1/external/price-calculation
```

| 項目 | 内容 |
|------|------|
| メソッド | POST |
| URL | `/api/v1/external/price-calculation` |
| 認証 | API Key（`X-API-Key`ヘッダー） |
| Content-Type | `application/json` |
| レスポンス | 200 OK（成功時） |

### リクエストボディ

```json
{
  "product_type": "tshirt",
  "size": "M",
  "color": "白",
  "position": "正面",
  "quantity": 2
}
```

### パラメータ詳細

| フィールド | 型 | 必須 | 説明 | 制約 |
|-----------|-----|:---:|------|------|
| product_type | string | ○ | 製造種類 | `tshirt`, `acrylic_keychain`, `acrylic_stand`, `sticker`, `tote_bag` |
| size | string | ○ | サイズ | 商品タイプにより異なる（下記参照） |
| color | string | 条件付 | カラー | 商品タイプにより異なる |
| position | string | 条件付 | プリント位置 | Tシャツ・トートバッグ: 正面 |
| quantity | integer | - | 数量 | 1以上（デフォルト: 1） |

**商品タイプ別の有効値**:
- `tshirt`: size=S/M/L/XL, color=白, position=正面
- `acrylic_keychain`: size=50x50mm/70x70mm/100x100mm
- `acrylic_stand`: size=50x50mm/70x70mm/100x100mm
- `sticker`: size=50x50mm/70x70mm/100x100mm, color=ホワイト
- `tote_bag`: size=M, color=ナチュラル, position=正面

### レスポンス例

```json
{
  "product_type": "tshirt",
  "size": "M",
  "color": "白",
  "position": "正面",
  "quantity": 2,
  "unit_price": 870,
  "total_price": 1740
}
```

### レスポンスフィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| product_type | string | 製造種類 |
| size | string | サイズ |
| color | string \| null | カラー（商品タイプにより任意） |
| position | string \| null | プリント位置（商品タイプにより任意） |
| quantity | integer | 数量 |
| unit_price | integer | 単価（税込） |
| total_price | integer | 合計金額（unit_price × quantity） |

### エラー例

#### 無効な属性値（400 Bad Request）

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid size 'XXL'. Valid sizes: ['S', 'M', 'L', 'XL']"
  }
}
```

### cURL例

```bash
# Tシャツ（color, position必須）
curl -X POST "https://api.example.com/api/v1/external/price-calculation" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "product_type": "tshirt",
    "size": "M",
    "color": "白",
    "position": "正面",
    "quantity": 2
  }'

# アクリルキーホルダー（sizeのみ必須）
curl -X POST "https://api.example.com/api/v1/external/price-calculation" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "product_type": "acrylic_keychain",
    "size": "70x70mm",
    "quantity": 5
  }'

# ステッカー（size, color必須）
curl -X POST "https://api.example.com/api/v1/external/price-calculation" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "product_type": "sticker",
    "size": "100x100mm",
    "color": "ホワイト",
    "quantity": 10
  }'
```

---

## サンプルコード

### cURL

```bash
curl -X POST "https://api.example.com/api/v1/orders" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "order_number": "0000001",
    "customer": {
      "name": "山田太郎",
      "postal_code": "123-4567",
      "address_prefecture": "東京都",
      "address_city": "渋谷区〇〇町1-2-3",
      "address_building": "○○ビル101",
      "phone": "03-1234-5678",
      "email": "yamada@example.com"
    },
    "items": [
      {
        "uid": "0000011",
        "product_type": "tshirt",
        "product_name": "オリジナルTシャツ デザインA",
        "price": 2500,
        "quantity": 2,
        "size": "M",
        "position": "正面",
        "color": "白"
      }
    ]
  }'
```

### Python

```python
import requests

url = "https://api.example.com/api/v1/orders"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your-api-key-here"
}

payload = {
    "order_number": "0000001",
    "customer": {
        "name": "山田太郎",
        "postal_code": "123-4567",
        "address_prefecture": "東京都",
        "address_city": "渋谷区〇〇町1-2-3",
        "address_building": "○○ビル101",
        "phone": "03-1234-5678",
        "email": "yamada@example.com"
    },
    "items": [
        {
            "uid": "0000011",
            "product_type": "tshirt",
            "product_name": "オリジナルTシャツ デザインA",
            "price": 2500,
            "quantity": 2,
            "size": "M",
            "position": "正面",
            "color": "白"
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 201:
    order = response.json()
    print(f"受注作成成功: {order['id']}")
else:
    print(f"エラー: {response.status_code}")
    print(response.json())
```

### JavaScript (Node.js / fetch)

```javascript
const createOrder = async () => {
  const url = "https://api.example.com/api/v1/orders";

  const payload = {
    order_number: "0000001",
    customer: {
      name: "山田太郎",
      postal_code: "123-4567",
      address_prefecture: "東京都",
      address_city: "渋谷区〇〇町1-2-3",
      address_building: "○○ビル101",
      phone: "03-1234-5678",
      email: "yamada@example.com"
    },
    items: [
      {
        uid: "0000011",
        product_type: "tshirt",
        product_name: "オリジナルTシャツ デザインA",
        price: 2500,
        quantity: 2,
        size: "M",
        position: "正面",
        color: "白"
      }
    ]
  };

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": "your-api-key-here"
    },
    body: JSON.stringify(payload)
  });

  if (response.status === 201) {
    const order = await response.json();
    console.log(`受注作成成功: ${order.id}`);
    return order;
  } else {
    const error = await response.json();
    console.error(`エラー: ${response.status}`, error);
    throw new Error(error.error?.message || "Unknown error");
  }
};
```

### PHP

```php
<?php

$url = "https://api.example.com/api/v1/orders";
$apiKey = "your-api-key-here";

$payload = [
    "order_number" => "0000001",
    "customer" => [
        "name" => "山田太郎",
        "postal_code" => "123-4567",
        "address_prefecture" => "東京都",
        "address_city" => "渋谷区〇〇町1-2-3",
        "address_building" => "○○ビル101",
        "phone" => "03-1234-5678",
        "email" => "yamada@example.com"
    ],
    "items" => [
        [
            "uid" => "0000011",
            "product_type" => "tshirt",
            "product_name" => "オリジナルTシャツ デザインA",
            "price" => 2500,
            "quantity" => 2,
            "size" => "M",
            "position" => "正面",
            "color" => "白"
        ]
    ]
];

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "Content-Type: application/json",
    "X-API-Key: " . $apiKey
]);

$response = curl_exec($ch);
$statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($statusCode === 201) {
    $order = json_decode($response, true);
    echo "受注作成成功: " . $order["id"];
} else {
    echo "エラー: " . $statusCode . "\n";
    print_r(json_decode($response, true));
}
```

---

## 注意事項

1. **べき等性**: 同じ `order_number` での再送信はエラー（409）となります。リトライ時は新しい受注番号を使用してください。

2. **製造種類**: `product_type` はサポートされている商品タイプを指定してください（`tshirt`, `acrylic_keychain`, `acrylic_stand`, `sticker`, `tote_bag`）。

3. **製品番号**: `uid` は7桁数字形式（例: `0000001`）で指定してください。POD管理システムでは参照用として保存されます。

4. **Tシャツの属性**: Tシャツ（`product_type: tshirt`）の場合、`size`、`color`、`position` はすべて必須で、有効な値のみ許可されます。

5. **画像URL**: `design_image_url` および `thumbnail_image_url` は、外部からアクセス可能なURLを指定してください。

6. **受注日時**: `ordered_at` はリクエストでは指定できません（送信しても無視されます）。POD管理システムが受信時刻（JST）を自動採番し、レスポンスに ISO 8601 形式（例: `2024-01-15T10:30:00+09:00`）で返します。

7. **金額計算**: `total_price` はシステム側で自動計算されます（各商品の price × quantity の合計）。

---

## 変更履歴

| バージョン | 日付 | 内容 |
|-----------|------|------|
| 3.5.0 | 2026-07-17 | ドキュメントを実装準拠に更新。受注レスポンスに配送予定日 `estimated_shipping_date`、明細に `expected_delivery_date` / `status` / `product_code` / `manufacturing_data` を明記。`ordered_at` はサーバ採番のためリクエスト項目から削除。ステッカーサイズを3種に修正。v2受注API（`POST /api/v2/orders`）を追記。 |
| 3.4.0 | 2026-03-01 | 注文取り消しAPI追加 (FEAT-0023) |
| 3.3.0 | 2026-02-25 | order_numberおよびuidを7桁数字形式に変更。バリデーション追加。 |
| 3.2.0 | 2026-02-23 | ステッカーのカラーから「クリア」を削除。「ホワイト」のみの単一カラー体制に変更。(FEAT-0007) |
| 3.1.0 | 2026-02-14 | レスポンスに `source` および `order_source_id` フィールド追加。受注元管理がDB管理に完全移行。 |
| 3.0.0 | 2026-02-14 | **破壊的変更**: 住所フィールド正規化。`address` を削除し、`address_prefecture` + `address_city` を必須に。レスポンスの `customer_address` を `customer_full_address` に変更（自動生成）。 |
| 2.3.0 | 2026-02-14 | 住所分割フィールド追加（address_prefecture, address_city, address_building）。配送CSVエクスポート対応。 |
| 2.2.0 | 2026-02-13 | 注文ステータス取得API追加 |
| 2.1.0 | 2026-01-29 | 5商品対応: アクリルキーホルダー、アクリルスタンド、ステッカー、トートバッグ追加 |
| 2.0.0 | 2026-01-10 | **破壊的変更**: `product_id`を`product_type`に変更、商品属性取得API追加、価格取得API追加 |
| 1.2.0 | 2026-01-10 | Tシャツ属性のENUMバリデーション追加 |
| 1.1.0 | 2024-01-XX | `uid` フィールド追加、`product_type` を自動取得に変更 |
| 1.0.0 | 2024-01-XX | 初版リリース |
