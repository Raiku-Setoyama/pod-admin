# 外部販売サイト向け API 仕様書

## 概要

外部販売サイトから POD 管理システムへ連携するための REST API です。
すべてのエンドポイントは `/external` プレフィックスを持ち、API キー認証が必須です。

---

## 認証

すべてのリクエストに以下のヘッダーを付与してください。

| ヘッダー名 | 値 |
|---|---|
| `X-API-Key` | 発行された API キー |

API キーが未指定または無効な場合、`401 Unauthorized` を返します。

---

## エンドポイント一覧

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/external/product-options/{product_type}` | 商品オプション一覧取得 |
| POST | `/external/price-calculation` | 価格計算 |
| GET | `/external/orders/{order_number}/status` | 注文ステータス取得 |
| POST | `/external/orders/{order_number}/cancel` | 注文取り消し |

---

## 1. 商品オプション一覧取得

商品タイプ別のオプション（サイズ・カラー・印刷位置）の一覧を取得します。

### リクエスト

```
GET /external/product-options/{product_type}
```

#### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `product_type` | string | はい | 商品タイプ（例: `tshirt`） |

### レスポンス

**200 OK**

```json
{
  "product_type": "tshirt",
  "sizes": [
    { "key": "S", "label": "S" },
    { "key": "M", "label": "M" },
    { "key": "L", "label": "L" },
    { "key": "XL", "label": "XL" }
  ],
  "colors": [
    { "key": "white", "label": "ホワイト" },
    { "key": "black", "label": "ブラック" }
  ],
  "positions": [
    { "key": "front", "label": "前面" },
    { "key": "back", "label": "背面" }
  ]
}
```

#### レスポンスフィールド（ProductOptionsResponse）

| フィールド | 型 | 説明 |
|---|---|---|
| `product_type` | string | 商品タイプ |
| `sizes` | array | サイズ選択肢の配列 |
| `colors` | array | カラー選択肢の配列 |
| `positions` | array | 印刷位置選択肢の配列 |

各選択肢オブジェクト:

| フィールド | 型 | 説明 |
|---|---|---|
| `key` | string | 選択肢の識別キー |
| `label` | string | 表示用ラベル |

---

## 2. 価格計算

指定した商品設定の価格を計算します。

### リクエスト

```
POST /external/price-calculation
```

#### リクエストボディ

```json
{
  "product_type": "tshirt",
  "size": "M",
  "color": "white",
  "position": "front",
  "quantity": 10
}
```

| フィールド | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `product_type` | string | はい | - | 商品タイプ |
| `size` | string | はい | - | サイズ |
| `color` | string | いいえ | - | カラー |
| `position` | string | いいえ | - | 印刷位置 |
| `quantity` | integer | いいえ | `1` | 数量 |

### レスポンス

**200 OK**

```json
{
  "unit_price": 1500,
  "total_price": 15000
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `unit_price` | integer | 単価 |
| `total_price` | integer | 合計金額（`unit_price × quantity`） |

---

## 3. 注文ステータス取得

注文番号で注文のステータスを取得します。

### リクエスト

```
GET /external/orders/{order_number}/status
```

#### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `order_number` | string | はい | 注文番号 |

### レスポンス

**200 OK**

```json
{
  "order_number": "ORD-20260301-001",
  "status": "ordered",
  "ordered_at": "2026-03-01T10:00:00+09:00",
  "updated_at": "2026-03-01T10:00:00+09:00"
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `order_number` | string | 注文番号 |
| `status` | string | 注文ステータス |
| `ordered_at` | string (ISO 8601) | 注文日時 |
| `updated_at` | string (ISO 8601) | 最終更新日時 |

**404 Not Found** — 指定した注文番号が存在しない場合

```json
{
  "detail": "注文が見つかりません"
}
```

---

## 4. 注文取り消し

注文を取り消します。ステータスが「発注中（ordered）」の注文のみ取り消し可能です。

### リクエスト

```
POST /external/orders/{order_number}/cancel
```

#### パスパラメータ

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `order_number` | string | はい | 注文番号 |

### レスポンス

**200 OK**

```json
{
  "order_number": "ORD-20260301-001",
  "status": "cancelled",
  "cancelled_at": "2026-03-01T12:00:00+09:00"
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `order_number` | string | 注文番号 |
| `status` | string | 取り消し後のステータス（`cancelled`） |
| `cancelled_at` | string (ISO 8601) | 取り消し日時 |

**404 Not Found** — 指定した注文番号が存在しない場合

```json
{
  "detail": "注文が見つかりません"
}
```

**409 Conflict** — 発注中（ordered）以外のステータスの場合

```json
{
  "detail": "発注中の注文のみ取り消し可能です"
}
```
