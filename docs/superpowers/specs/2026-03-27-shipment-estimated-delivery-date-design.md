# 配送予定日表示機能 設計書

## 概要

配送一覧に「配送予定日」カラムを追加し、各配送の配送予定日を自動計算・表示する。
発送準備日数は設定ページで変更可能とし、営業日計算では土日祝日・独自休日を除外する。

## 用語定義

| 用語 | 英語フィールド名 | 意味 |
|------|------------------|------|
| 納品予定日 | expected_delivery_date | メーカーからTOSYOへの納品予定日。`ordered_at + lead_time_days`（暦日）で算出 |
| 配送予定日 | estimated_shipping_date | TOSYOから顧客への出荷予定日。納品予定日 + 発送準備日数（営業日）で算出 |
| 発送準備日数 | shipping_preparation_days | TOSYOでの梱包・発送準備に必要な営業日数。デフォルト5日 |

UIラベルは「配送予定日」を使用する（ユーザー要件に準拠）。

## 計算ロジック

```
配送予定日 = add_business_days(
  MAX(配送に含まれる全注文の全商品の納品予定日),
  発送準備日数
)
```

### 納品予定日の取得パス

```
Shipment → ShipmentItem[] → Order → OrderItem[] → Product.lead_time_days
                                  → Order.ordered_at
納品予定日 = Order.ordered_at.date() + timedelta(days=Product.lead_time_days)
```

具体的なリレーション:
- `OrderItem.product_id` → `Product.id` (FK)
- `Product.lead_time_days` (integer, 暦日数)
- 各OrderItemの納品予定日 = `order.ordered_at.date() + timedelta(days=order_item.product.lead_time_days)`

### 営業日加算の起算ルール

- `latest_delivery_date`（最遅納品予定日）の**翌日**から営業日をカウント開始する
- 最遅納品予定日当日は発送準備日数にカウントしない
- 例: 最遅納品予定日が金曜日、発送準備日数5営業日の場合 → 翌週の金曜日が配送予定日

### Noneになるケース

`estimated_shipping_date` が `null` になるのは以下の場合:
- Shipmentに紐づくOrderItemが0件の場合
- OrderItemに紐づくProductが存在しない場合（データ不整合）
- 既に出荷済み（shipped）のShipmentでは計算は行うが、実際の出荷日(`shipped_at`)を優先表示してもよい（UIで判断）

## アーキテクチャ

### 新規テーブル

#### 1. `system_settings` テーブル
汎用的なキー/バリュー設定テーブル。

| カラム | 型 | 説明 |
|--------|------|------|
| id | UUID (PK) | |
| key | VARCHAR(100) UNIQUE | 設定キー |
| value | TEXT | 設定値（JSON文字列） |
| description | VARCHAR(255) | 説明 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

初期データ: `key="shipping_preparation_days"`, `value="5"`, `description="発送準備日数"`

#### 2. `company_holidays` テーブル
TOSYO独自休日管理テーブル。年ごとに個別の日付を登録する運用（繰り返しパターンはスコープ外）。

| カラム | 型 | 説明 |
|--------|------|------|
| id | UUID (PK) | |
| date | DATE UNIQUE | 休日の日付 |
| name | VARCHAR(100) | 休日名（例: 夏季休暇） |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### バックエンド構成

#### Models
- `api/app/models/system_setting.py` - SystemSetting モデル
- `api/app/models/company_holiday.py` - CompanyHoliday モデル

#### Repositories
- `api/app/repositories/system_setting_repository.py` - 設定CRUD
- `api/app/repositories/company_holiday_repository.py` - 独自休日CRUD

#### Services
- `api/app/services/settings_service.py` - 設定管理サービス（発送準備日数の取得・更新、独自休日CRUD）

#### Utils
- `api/app/utils/business_day_calculator.py` - 営業日計算ユーティリティ
  - 日本の祝日判定（`jpholiday`パッケージ使用）
  - `add_business_days(start_date, days, company_holidays)` メソッド
  - `start_date` の翌日から営業日をカウント

#### Schemas
- `api/app/schemas/settings.py` - 設定API用Pydanticスキーマ

#### Routers
- `api/app/routers/settings.py` - 設定APIエンドポイント（管理者認証必須）

#### API エンドポイント

すべてのエンドポイントは管理者認証（`get_current_admin_user`）が必要。

| Method | Path | 説明 |
|--------|------|------|
| GET | /settings/shipping-preparation-days | 発送準備日数を取得 |
| PUT | /settings/shipping-preparation-days | 発送準備日数を更新 |
| GET | /settings/company-holidays | 独自休日一覧を取得 |
| POST | /settings/company-holidays | 独自休日を追加 |
| DELETE | /settings/company-holidays/{id} | 独自休日を削除 |

### 配送予定日の算出フロー

配送予定日はバックエンドの `ShipmentService.list_with_pending_orders()` 内で算出し、APIレスポンスに含める。

**パフォーマンス方針:**
- `shipping_preparation_days` と `company_holidays` はリクエストごとに1回ずつ取得し、全Shipment/PendingOrderで共有する
- OrderItem → Product の join は既存クエリに追加する（N+1を回避）
- 配送予定日はDBに永続化せず、リクエスト時に毎回計算する（設定変更が即時反映されるため）

#### 1. Shipmentの場合

```python
# 1回のクエリで全Shipmentの全OrderItemとProductをeager load
for shipment in shipments:
    delivery_dates = []
    for shipment_item in shipment.items:
        order = shipment_item.order
        for order_item in order.items:
            if order_item.product and order_item.product.lead_time_days:
                d = order.ordered_at.date() + timedelta(days=order_item.product.lead_time_days)
                delivery_dates.append(d)
    if delivery_dates:
        latest = max(delivery_dates)
        estimated = add_business_days(latest, prep_days, holidays)
    else:
        estimated = None
```

#### 2. PendingOrderの場合

```python
for order in pending_orders:
    delivery_dates = []
    for order_item in order.items:
        if order_item.product and order_item.product.lead_time_days:
            d = order.ordered_at.date() + timedelta(days=order_item.product.lead_time_days)
            delivery_dates.append(d)
    if delivery_dates:
        latest = max(delivery_dates)
        estimated = add_business_days(latest, prep_days, holidays)
    else:
        estimated = None
```

### レスポンススキーマ変更

`ShipmentResponse` に `estimated_shipping_date: date | None` フィールドを追加。
`PendingOrderResponse` に `estimated_shipping_date: date | None` フィールドを追加。

### フロントエンド変更

#### TypeScript型
- `Shipment` インターフェースに `estimated_shipping_date: string | null` を追加
- `PendingOrder` インターフェースに `estimated_shipping_date: string | null` を追加

#### 設定ページ用型
```typescript
interface SystemSetting {
  key: string;
  value: string;
  description: string;
}

interface CompanyHoliday {
  id: string;
  date: string;
  name: string;
}
```

#### 配送一覧テーブル
- `shipment-list.tsx` に「配送予定日」カラムを追加（「作成日」と「ステータス」の間に配置）
- 日付のみ表示（時刻なし）、フォーマット: `YYYY/MM/DD`
- 値がnullの場合は「-」を表示

#### 設定ページ
- `/web/src/app/(dashboard)/settings/page.tsx` を拡張
- 「配送設定」セクション: 発送準備日数の表示・編集（数値入力 + 保存ボタン）
- 「会社休日」セクション: 独自休日の一覧表示・追加（日付ピッカー + 休日名）・削除

### 依存パッケージ

- `jpholiday` (Python) - 日本の祝日判定ライブラリ
  - メンテナンスが安定しており、祝日法改正にも追従している
  - フォールバック: ライブラリが更新されない場合、独自休日テーブルに祝日を手動登録可能

## テスト計画

1. `business_day_calculator` のユニットテスト
   - 土日除外の正確性
   - 祝日除外の正確性（例: 元日、成人の日）
   - 独自休日除外の正確性
   - 連休をまたぐケース（GW、年末年始）
   - 発送準備日数が0の場合
   - 起算日が休日の場合
2. 設定APIのテスト
   - 発送準備日数のGET/PUT
   - 独自休日のCRUD
   - 認証が必要であること
3. 配送予定日計算の統合テスト
   - Shipmentの配送予定日が正しく算出されること
   - PendingOrderの配送予定日が正しく算出されること
   - OrderItemが0件の場合にnullが返ること

## スコープ外

- 配送予定日によるフィルタリング・ソート（将来的に追加可能）
- 配送予定日の手動上書き
- 通知機能（配送予定日が近づいた場合のアラートなど）
- 独自休日の繰り返しパターン（毎年同じ日を自動登録する機能）
- `jpholiday` パッケージのフォールバック自動化
