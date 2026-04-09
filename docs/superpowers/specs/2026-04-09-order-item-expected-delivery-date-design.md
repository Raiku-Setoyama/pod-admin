# OrderItem 納品予定日 DB永続化 設計書

## 概要

注文の商品ごとのメーカーからの納品予定日（`expected_delivery_date`）を `order_items` テーブルに永続化する。計算は注文作成時に1回のみ行い、確定値として保存する。

## 用語定義

| 用語 | 英語フィールド名 | 意味 |
|------|------------------|------|
| 納品予定日 | expected_delivery_date | メーカーからTOSYOへの納品予定日。`ordered_at` から `lead_time_days` 営業日後で算出 |

## 計算ロジック

```
expected_delivery_date = add_business_days(ordered_at.date(), lead_time_days, company_holidays)
```

### ルール
- `ordered_at` の**翌日**から営業日をカウント開始
- 土日を除外
- 日本の祝日を除外（`jpholiday` ライブラリ使用）
- TOSYO独自休日を除外（`company_holidays` テーブルから取得）
- `lead_time_days` が 0 の場合は `ordered_at.date()` をそのまま返す
- 計算は注文作成時に1回のみ。以降は再計算しない（確定値）

### 例
- 受注日: 2026-04-09（木）、lead_time_days: 3
  - 翌日 4/10（金）→ 1日目
  - 4/11（土）→ スキップ
  - 4/12（日）→ スキップ
  - 4/13（月）→ 2日目
  - 4/14（火）→ 3日目
  - **納品予定日: 2026-04-14**

## データモデル変更

### `order_items` テーブルにカラム追加

| カラム | 型 | 説明 |
|--------|------|------|
| expected_delivery_date | DATE, nullable | メーカーからの納品予定日 |

- NULLable（既存データはNULL）
- 既存データの再計算は行わない

### 新規テーブル: `company_holidays`

| カラム | 型 | 説明 |
|--------|------|------|
| id | UUID (PK) | |
| date | DATE UNIQUE | 休日の日付 |
| name | VARCHAR(100) | 休日名（例: 夏季休暇） |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

## バックエンド構成

| 区分 | ファイル | 内容 |
|------|---------|------|
| Model | `app/models/company_holiday.py` | CompanyHolidayモデル |
| Model | `app/models/order.py` | OrderItemに`expected_delivery_date`追加 |
| Repository | `app/repositories/company_holiday_repository.py` | 独自休日の取得 |
| Utils | `app/utils/business_day_calculator.py` | `add_business_days()` |
| Migration | alembic版 | カラム追加 + テーブル作成 |

### 計算タイミング

`OrderService.create()` 内で:
1. `company_holidays` テーブルから休日一覧を取得
2. 各OrderItemについて `add_business_days(ordered_at.date(), product.lead_time_days, holidays)` を計算
3. `expected_delivery_date` を設定して保存

## 依存パッケージ

- `jpholiday` (Python) - 日本の祝日判定

## テスト計画

1. `business_day_calculator` のユニットテスト
   - 土日除外
   - 祝日除外
   - 独自休日除外
   - 連休をまたぐケース
   - lead_time_days が 0 の場合
2. 注文作成時の `expected_delivery_date` 計算テスト

## スコープ外

- `company_holidays` のCRUD APIエンドポイント（別タスク）
- `estimated_shipping_date`（配送予定日）の変更
- フロントエンドの表示変更
- 既存データの再計算
