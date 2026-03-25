# 商品属性の ENUM 統一設計

## 概要

商品属性（size, color, position）が DB の自由テキストカラムと Python ENUM の2重管理になっている問題を解決する。ENUM を唯一の定義元（Single Source of Truth）とし、バックエンド・フロントエンド双方で一貫した検証を行う。

## 現状の問題

| レイヤー | 管理方式 | 問題点 |
|---------|---------|--------|
| DB (products, order_items) | String(50) 自由テキスト | 制約なし、不正値が入りうる |
| Python ENUM (order.py) | 15個の商品別 ENUM | 受注バリデーションのみで使用 |
| フロントエンド (product-form.tsx) | テキスト入力 | 選択肢なし、ENUM と乖離 |

products テーブルに `size="Medium"` を入れても DB は受け入れるが、受注時に `TshirtSize("Medium")` でバリデーションエラーになる。

## 設計

### 1. 属性レジストリモジュール（バックエンド）

`api/app/models/product_attributes.py` を新設。

- 既存の属性 ENUM を `order.py` からここに移動
- `PRODUCT_ATTRIBUTES` 辞書を作成し、`ProductType` ごとの有効な属性を定義
- 各属性が必須か任意かも定義

```python
@dataclass(frozen=True)
class ProductAttributeSpec:
    sizes: list[str]
    colors: list[str]
    positions: list[str]
    required_size: bool = True
    required_color: bool = False
    required_position: bool = False

PRODUCT_ATTRIBUTES: dict[ProductType, ProductAttributeSpec] = {
    ProductType.TSHIRT: ProductAttributeSpec(
        sizes=[s.value for s in TshirtSize],
        colors=[c.value for c in TshirtColor],
        positions=[p.value for p in TshirtPosition],
        required_size=True,
        required_color=True,
        required_position=True,
    ),
    # ... 他の商品種別
}
```

ヘルパー関数:
- `get_attribute_spec(product_type) -> ProductAttributeSpec`
- `validate_product_attributes(product_type, size, color, position) -> None` (不正値で ValidationError)

### 2. ProductService にバリデーション追加

`ProductService.create()` と `update()` で `validate_product_attributes()` を呼ぶ。商品マスタ登録時にも ENUM に準拠した値のみ許可する。

### 3. OrderService のバリデーション簡素化

`order_service.py` の `_validate_tshirt_attributes()` 等の個別メソッド（約140行）を削除し、共通の `validate_product_attributes()` 呼び出しに置換。

### 4. 属性選択肢 API エンドポイント

`GET /products/attributes/{product_type}` を新設。

レスポンス例:
```json
{
  "product_type": "tshirt",
  "sizes": ["S", "M", "L", "XL"],
  "colors": ["白"],
  "positions": ["正面"],
  "required_size": true,
  "required_color": true,
  "required_position": true
}
```

### 5. フロントエンド更新

`product-form.tsx` の size/position/color フィールドを:
- テキスト入力 → `Select` ドロップダウンに変更
- `product_type` の変更に連動して選択肢を動的に切り替え
- API から選択肢を取得

### 6. DB カラムの型はそのまま

`String(50)` カラムはそのまま維持（Alembic マイグレーション不要）。バリデーションはアプリケーション層で完結させる。既存データは ENUM の値と一致しているはずだが、不一致があっても DB 側は変更しない。

## 変更対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `api/app/models/product_attributes.py` | **新規** 属性レジストリ |
| `api/app/models/order.py` | 属性 ENUM を削除（移動） |
| `api/app/services/product_service.py` | バリデーション追加 |
| `api/app/services/order_service.py` | 個別バリデーション → 共通化 |
| `api/app/routers/products.py` | 属性エンドポイント追加 |
| `api/app/schemas/product.py` | 属性レスポンススキーマ追加 |
| `web/src/types/api/index.ts` | ProductAttributeSpec 型追加 |
| `web/src/features/products/components/product-form.tsx` | ドロップダウン化 |

## テスト方針

- `product_attributes.py` のバリデーション関数のユニットテスト
- `ProductService` の create/update で不正属性が弾かれることのテスト
- `OrderService` の既存テストが引き続きパスすること
- 属性 API エンドポイントのテスト
