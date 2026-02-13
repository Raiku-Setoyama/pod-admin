# 受注API仕様書

外部販売サイトからPOD管理システムへ受注データを連携するためのAPIドキュメントです。

## 目次

1. [概要](#概要)
2. [認証](#認証)
3. [エンドポイント一覧](#エンドポイント一覧)
4. [受注作成API](#受注作成api)
5. [注文ステータス取得API](#注文ステータス取得api)
6. [商品属性取得API](#商品属性取得api)
7. [価格取得API](#価格取得api)
8. [エラーハンドリング](#エラーハンドリング)
9. [データ定義](#データ定義)
10. [サンプルコード](#サンプルコード)

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
| `uid` | 外部販売サイトのオリジナル商品ID | `"my-original-tshirt-001"` |
| `product_type` | 製造種類（商品タイプ） | `"tshirt"` |

**例**: 外部サイトで販売している「オリジナルTシャツA」（uid: `EXT-001`）を、Tシャツ（product_type: `tshirt`）として製造する。

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
| `/api/v1/orders` | POST | 受注作成 |
| `/api/v1/external/orders/{order_number}/status` | GET | 注文ステータス取得 |
| `/api/v1/external/product-options/{product_type}` | GET | 商品属性取得 |
| `/api/v1/external/price-calculation` | POST | 価格取得 |

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
  "order_number": "ORD-2024-001",
  "ordered_at": "2024-01-15T10:30:00+09:00",
  "customer": {
    "name": "山田太郎",
    "postal_code": "123-4567",
    "address": "東京都渋谷区〇〇町1-2-3 ○○ビル101",
    "phone": "03-1234-5678",
    "email": "yamada@example.com"
  },
  "items": [
    {
      "uid": "my-original-tshirt-001",
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
| order_number | string | ○ | 受注番号（販売サイト側で採番） | 1-50文字、ユニーク |
| ordered_at | datetime | ○ | 受注日時（ISO 8601形式） | タイムゾーン付き |
| customer | object | ○ | 顧客情報 | 下記参照 |
| items | array | ○ | 受注明細（商品リスト） | 1件以上必須 |

#### customer（顧客情報）

| フィールド | 型 | 必須 | 説明 | 制約 |
|-----------|-----|:---:|------|------|
| name | string | ○ | 顧客名 | 1-100文字 |
| postal_code | string | ○ | 郵便番号 | 1-10文字 |
| address | string | ○ | 住所 | 1文字以上 |
| phone | string | ○ | 電話番号 | 1-20文字 |
| email | string | - | メールアドレス | Email形式 |

#### items（受注明細）

| フィールド | 型 | 必須 | 説明 | 制約 |
|-----------|-----|:---:|------|------|
| uid | string | ○ | 外部販売サイトのオリジナル商品ID | 1-100文字 |
| product_type | string | ○ | 製造種類（商品タイプ） | 有効値: tshirt, acrylic_keychain, acrylic_stand, sticker, tote_bag |
| product_name | string | ○ | 外部販売サイトの商品名 | 1-200文字 |
| price | integer | ○ | 単価（税込） | 0以上 |
| quantity | integer | ○ | 数量 | 1以上（デフォルト: 1） |
| size | string | 条件付 | サイズ | 最大50文字、Tシャツの場合は必須（有効値: S, M, L, XL） |
| position | string | 条件付 | 印刷位置 | 最大50文字、Tシャツの場合は必須（有効値: 正面） |
| color | string | 条件付 | カラー | 最大50文字、Tシャツの場合は必須（有効値: 白） |
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
  - `size`: `100x100mm`
  - `color`: `クリア`, `ホワイト`

- **トートバッグ** (`product_type: tote_bag`)
  - `size`: `M`
  - `color`: `ナチュラル`
  - `position`: `正面`

---

### 成功時（201 Created）

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "order_number": "ORD-2024-001",
  "status": "ordered",
  "customer_name": "山田太郎",
  "customer_postal_code": "123-4567",
  "customer_address": "東京都渋谷区〇〇町1-2-3 ○○ビル101",
  "customer_phone": "03-1234-5678",
  "customer_email": "yamada@example.com",
  "ordered_at": "2024-01-15T10:30:00+09:00",
  "total_price": 5000,
  "items": [
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "uid": "my-original-tshirt-001",
      "product_name": "オリジナルTシャツ デザインA",
      "product_type": "tshirt",
      "price": 2500,
      "quantity": 2,
      "size": "M",
      "position": "正面",
      "color": "白",
      "design_image_url": "https://example.com/designs/design1.png",
      "thumbnail_image_url": "https://example.com/thumbnails/thumb1.png",
      "created_at": "2024-01-15T10:30:00+09:00",
      "updated_at": "2024-01-15T10:30:00+09:00"
    }
  ],
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
| customer_name | string | 顧客名 |
| customer_postal_code | string | 郵便番号 |
| customer_address | string | 住所 |
| customer_phone | string | 電話番号 |
| customer_email | string \| null | メールアドレス |
| ordered_at | datetime | 受注日時 |
| total_price | integer | 合計金額（price × quantity の合計） |
| items | array | 受注明細 |
| created_at | datetime | 作成日時 |
| updated_at | datetime | 更新日時 |

#### items（レスポンス）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| id | string | 受注明細ID（UUID） |
| uid | string | 外部販売サイトのオリジナル商品ID |
| product_name | string | 外部販売サイトの商品名 |
| product_type | string | 製造種類（商品タイプ） |
| price | integer | 単価 |
| quantity | integer | 数量 |
| size | string \| null | サイズ |
| position | string \| null | 印刷位置 |
| color | string \| null | カラー |
| design_image_url | string \| null | デザイン画像URL |
| thumbnail_image_url | string \| null | サムネイル画像URL |
| created_at | datetime | 作成日時 |
| updated_at | datetime | 更新日時 |

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
  "order_number": "ORD-2024-001",
  "status": "manufacturing",
  "ordered_at": "2024-01-15T10:30:00+09:00",
  "updated_at": "2024-01-16T14:00:00+09:00"
}
```

### レスポンスフィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| order_number | string | 注文番号 |
| status | string | 現在のステータス（`ordered`, `manufacturing`, `delivered`, `shipped`） |
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
curl -X GET "https://api.example.com/api/v1/external/orders/ORD-2024-001/status" \
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
| 400 | VALIDATION_ERROR | リクエストパラメータ不正 | リクエスト内容を確認 |
| 401 | UNAUTHORIZED | 認証失敗 | APIキーを確認 |
| 404 | NOT_FOUND | 商品マスタが見つからない | product_id を確認 |
| 409 | DUPLICATE | 受注番号の重複 | order_number を変更 |
| 422 | VALIDATION_ERROR | バリデーションエラー | リクエスト形式を確認 |
| 500 | INTERNAL_ERROR | サーバーエラー | 管理者に連絡 |

### エラー例

#### 受注番号重複（409 Conflict）

```json
{
  "error": {
    "code": "DUPLICATE",
    "message": "Order with order_number 'ORD-2024-001' already exists"
  }
}
```

#### 商品マスタが見つからない（404 Not Found）

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Product with id 550e8400-e29b-41d4-a716-446655440000 not found"
  }
}
```

#### Tシャツ：size/color/positionが未指定（400 Bad Request）

Tシャツに対して、`size`、`color`、`position` を未指定で送信した場合：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "size is required for T-shirt (uid: my-original-tshirt-001)"
  }
}
```

#### Tシャツ：無効な属性値（400 Bad Request）

Tシャツに対して、許可されていない値を指定した場合：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid size 'XXL'. Valid: ['S', 'M', 'L', 'XL'] (uid: my-original-tshirt-001)"
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

レスポンスの `product_type` は、指定した `product_id` の商品マスタから自動的に取得されます。

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
| ordered | 発注中（初期ステータス） |
| manufacturing | 製造中 |
| delivered | 納入済み |
| shipped | 発送完了 |

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

| 値 | 説明 |
|----|------|
| 100x100mm | 100x100mm |

#### カラー（color）

| 値 | 説明 | 原価 |
|----|------|------|
| クリア | 透明 | 105円 |
| ホワイト | 白 | 79円 |

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
  "size": ["100x100mm"],
  "color": ["クリア", "ホワイト"],
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

#### 未サポートの商品タイプ（400 Bad Request）

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Product type 'mug' is not yet supported"
  }
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
- `sticker`: size=100x100mm, color=クリア/ホワイト
- `tote_bag`: size=M, color=ナチュラル, position=正面

### レスポンス例

```json
{
  "product_type": "tshirt",
  "size": "M",
  "color": "白",
  "position": "正面",
  "quantity": 2,
  "unit_price": 2500,
  "total_price": 5000
}
```

### レスポンスフィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| product_type | string | 製造種類 |
| size | string | サイズ |
| color | string \ null | カラー（商品タイプにより任意） |
| position | string \ null | プリント位置（商品タイプにより任意） |
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

#### 商品マスタが見つからない（404 Not Found）

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Product not found: T-shirt with size 'M' and color '白'"
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
    "color": "クリア",
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
    "order_number": "ORD-2024-001",
    "ordered_at": "2024-01-15T10:30:00+09:00",
    "customer": {
      "name": "山田太郎",
      "postal_code": "123-4567",
      "address": "東京都渋谷区〇〇町1-2-3",
      "phone": "03-1234-5678",
      "email": "yamada@example.com"
    },
    "items": [
      {
        "uid": "my-original-tshirt-001",
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
    "order_number": "ORD-2024-001",
    "ordered_at": "2024-01-15T10:30:00+09:00",
    "customer": {
        "name": "山田太郎",
        "postal_code": "123-4567",
        "address": "東京都渋谷区〇〇町1-2-3",
        "phone": "03-1234-5678",
        "email": "yamada@example.com"
    },
    "items": [
        {
            "uid": "my-original-tshirt-001",
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
    order_number: "ORD-2024-001",
    ordered_at: "2024-01-15T10:30:00+09:00",
    customer: {
      name: "山田太郎",
      postal_code: "123-4567",
      address: "東京都渋谷区〇〇町1-2-3",
      phone: "03-1234-5678",
      email: "yamada@example.com"
    },
    items: [
      {
        uid: "my-original-tshirt-001",
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
    "order_number" => "ORD-2024-001",
    "ordered_at" => "2024-01-15T10:30:00+09:00",
    "customer" => [
        "name" => "山田太郎",
        "postal_code" => "123-4567",
        "address" => "東京都渋谷区〇〇町1-2-3",
        "phone" => "03-1234-5678",
        "email" => "yamada@example.com"
    ],
    "items" => [
        [
            "uid" => "my-original-tshirt-001",
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

2. **製造種類**: `product_type` はサポートされている商品タイプを指定してください。現在は `tshirt` のみサポートしています。

3. **外部商品ID**: `uid` は外部販売サイトで管理しているオリジナル商品のIDを指定してください。POD管理システムでは参照用として保存されます。

4. **Tシャツの属性**: Tシャツ（`product_type: tshirt`）の場合、`size`、`color`、`position` はすべて必須で、有効な値のみ許可されます。

5. **画像URL**: `design_image_url` および `thumbnail_image_url` は、外部からアクセス可能なURLを指定してください。

6. **タイムゾーン**: `ordered_at` はISO 8601形式でタイムゾーン付きで指定してください（例: `2024-01-15T10:30:00+09:00`）。

7. **金額計算**: `total_price` はシステム側で自動計算されます（各商品の price × quantity の合計）。

---

## 変更履歴

| バージョン | 日付 | 内容 |
|-----------|------|------|
| 2.2.0 | 2026-02-13 | 注文ステータス取得API追加 |
| 2.1.0 | 2026-01-29 | 5商品対応: アクリルキーホルダー、アクリルスタンド、ステッカー、トートバッグ追加 |
| 2.0.0 | 2026-01-10 | **破壊的変更**: `product_id`を`product_type`に変更、商品属性取得API追加、価格取得API追加 |
| 1.2.0 | 2026-01-10 | Tシャツ属性のENUMバリデーション追加 |
| 1.1.0 | 2024-01-XX | `uid` フィールド追加、`product_type` を自動取得に変更 |
| 1.0.0 | 2024-01-XX | 初版リリース |
