# 配送予定日の一覧表示・フィルター・設定ページ

## 概要

注文一覧に「配送予定日」カラムを追加し、フィルター項目としても使えるようにする。
配送予定日は注文作成時にDB永続化し、設定変更時には未出荷注文を自動再計算する。

## 計算ロジック

```
配送予定日 = MAX(各商品の expected_delivery_date) + 発送準備日数(営業日)
```

- 営業日 = 土日・祝日（jpholiday）・TOSYO独自休日を除外
- 既存の `add_business_days()` をそのまま利用

## データベース変更

### `orders` テーブル

| カラム | 型 | 説明 |
|--------|------|------|
| `estimated_shipping_date` | Date, nullable | 配送予定日 |

### `app_settings` テーブル（新規）

| カラム | 型 | 説明 |
|--------|------|------|
| `key` | String(100), PK | 設定キー |
| `value` | String(500) | 設定値 |
| `description` | String(200), nullable | 説明 |
| `updated_at` | DateTime(timezone=True) | 更新日時 |

初期データ: `key="shipping_preparation_days"`, `value="5"`, `description="発送準備日数"`

## バックエンド

### AppSetting モデル・リポジトリ・サービス

- `AppSetting` モデル
- `AppSettingRepository`: `find_by_key()`, `find_all()`, `upsert()`
- `AppSettingService`: `get_shipping_preparation_days()`, `update()` + 再計算トリガー

### CompanyHoliday CRUD 拡張

- `CompanyHolidayRepository` に `find_all()`, `create()`, `delete()` を追加
- `CompanyHolidayService`: CRUD + 再計算トリガー

### 再計算ロジック

対象: `status` が `ordered`, `manufacturing`, `delivered` の注文
トリガー: `shipping_preparation_days` 変更時、`company_holidays` 追加/削除時

1. 未出荷注文を一括取得
2. 各注文の `MAX(items.expected_delivery_date)` を取得
3. `add_business_days(max_date, shipping_preparation_days, company_holidays)` で再計算
4. 一括更新

### 注文一覧API拡張

- `OrderResponse` に `estimated_shipping_date: date | None` を追加
- フィルターパラメータ追加: `shipping_from`, `shipping_to`
- `OrderRepository.find_all()` にフィルター条件追加

### 新規APIエンドポイント

- `GET /settings` — 全設定取得
- `PUT /settings/{key}` — 設定更新
- `GET /company-holidays` — 休日一覧
- `POST /company-holidays` — 休日追加
- `DELETE /company-holidays/{id}` — 休日削除

## フロントエンド

### 注文一覧

- 「受注日」と「ステータス」の間に「配送予定日」カラム追加
- フィルターに配送予定日の DateRangePicker 追加

### 設定ページ拡張

- 発送準備日数の入力フィールド + 保存ボタン
- 会社休日の一覧テーブル + 追加フォーム + 削除ボタン

## 再計算の対象外

- `shipped`, `cancelled` ステータスの注文は再計算しない
- 配送予定日は全ステータスで表示する

## マイグレーション

- `orders.estimated_shipping_date` カラム追加
- `app_settings` テーブル作成 + 初期データ挿入
- データマイグレーション: 既存注文の `estimated_shipping_date` を計算して埋める
