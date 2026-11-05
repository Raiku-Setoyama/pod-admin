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
  "status": "shipped",
  "ordered_at": "2026-03-01T10:00:00+09:00",
  "updated_at": "2026-03-05T15:00:00+09:00",
  "shipment": {
    "carrier": "ヤマト運輸",
    "tracking_number": "1234-5678-9012",
    "shipped_at": "2026-03-05T15:00:00+09:00"
  }
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `order_number` | string | 注文番号 |
| `status` | string | 注文ステータス（下の「注文ステータス一覧」） |
| `ordered_at` | string (ISO 8601) | 注文日時 |
| `updated_at` | string (ISO 8601) | 注文の最終更新日時（配送情報の変更では変わらない） |
| `shipment` | object \| null | 配送情報（下の「配送情報」）。配送が無い、または伝票番号が未登録なら `null` |

#### 注文ステータス一覧

| 値 | 意味 |
|---|---|
| `preparing_order` | 発注準備中（製造データを準備している） |
| `ordered` | 発注済み |
| `manufacturing` | 製造中 |
| `delivered` | 納入済み（製造が終わり、配送準備中） |
| `shipped` | 発送済み |
| `cancelled` | キャンセル済み |

#### 配送情報（`shipment`）

| フィールド | 型 | 説明 |
|---|---|---|
| `carrier` | string \| null | 運送会社名。未登録なら `null` |
| `tracking_number` | string | 伝票番号（`shipment` があるときは必ず入る） |
| `shipped_at` | string (ISO 8601) \| null | 発送日時。伝票番号は登録済みでもまだ発送していなければ `null` |

- 伝票番号は発送前に登録されることがあります。そのため `status` が `shipped` でなくても `shipment` が返ることがあり、そのときは `shipped_at` が `null` です。
- 伝票番号・運送会社の登録や修正では `updated_at` は変わりません。変更を検知するときは `shipment` の中身も比べてください。
- 1 つの配送に複数の注文を同梱した場合は、どの注文番号で取得しても同じ配送情報を返します。
- 1 つの注文に配送が複数ある場合（通常は 1 注文 1 配送）は、伝票番号のある配送のうち発送日時が新しいもの（未発送は後ろ）、同じなら作成日時が新しいものを 1 件返します。
- `shipment` は後から追加した項目です。今後も項目が増えることがあるので、知らない項目は無視してください。

**404 Not Found** — 指定した注文番号が存在しない場合

```json
{
  "detail": "注文が見つかりません"
}
```

---

## 4. 注文取り消し

注文を取り消します。ステータスが「発注中（ordered）」の注文のみ取り消し可能です。
取り消すと配下の受注明細も全て「キャンセル済み（cancelled）」になり、メーカー側の画面でも取り消し済みとして扱われます。

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
