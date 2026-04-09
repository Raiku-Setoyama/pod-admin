# 商品属性 ENUM 統一 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 商品属性（size, color, position）の定義元を Python ENUM に統一し、DB 自由テキストとの二重管理を解消する。

**Architecture:** 新モジュール `product_attributes.py` に属性 ENUM と検証ロジックを集約。ProductService と OrderService が共通の `validate_product_attributes()` を使用。フロントエンドは新 API エンドポイントから選択肢を取得しドロップダウン表示。

**Tech Stack:** Python 3.12 / FastAPI / Pydantic 2 / React 19 / TypeScript 5 / React Hook Form + Zod

---

### Task 1: 属性レジストリモジュールの作成

**Files:**
- Create: `api/app/models/product_attributes.py`
- Test: `api/tests/unit/test_product_attributes.py`

- [ ] **Step 1: テストファイルを作成**

```python
"""商品属性レジストリのユニットテスト"""

import pytest

from app.models.product import ProductType
from app.models.product_attributes import (
    PRODUCT_ATTRIBUTES,
    ProductAttributeSpec,
    TshirtSize,
    TshirtColor,
    TshirtPosition,
    AcrylicKeychainSize,
    AcrylicKeychainColor,
    AcrylicStandSize,
    AcrylicStandColor,
    StickerSize,
    StickerColor,
    ToteBagSize,
    ToteBagColor,
    ToteBagPosition,
    get_attribute_spec,
    validate_product_attributes,
)
from app.utils.exceptions import ValidationError


class TestProductAttributeEnums:
    """属性 ENUM の値テスト"""

    def test_tshirt_sizes(self):
        assert [s.value for s in TshirtSize] == ["S", "M", "L", "XL"]

    def test_tshirt_colors(self):
        assert [c.value for c in TshirtColor] == ["白"]

    def test_tshirt_positions(self):
        assert [p.value for p in TshirtPosition] == ["正面"]

    def test_acrylic_keychain_sizes(self):
        assert [s.value for s in AcrylicKeychainSize] == ["50x50mm", "70x70mm", "100x100mm"]

    def test_sticker_sizes(self):
        assert [s.value for s in StickerSize] == ["50x50mm", "70x70mm", "100x100mm"]

    def test_tote_bag_positions(self):
        assert [p.value for p in ToteBagPosition] == ["正面"]


class TestProductAttributes:
    """PRODUCT_ATTRIBUTES レジストリのテスト"""

    def test_all_product_types_have_spec(self):
        for pt in ProductType:
            assert pt in PRODUCT_ATTRIBUTES, f"{pt} is missing from PRODUCT_ATTRIBUTES"

    def test_tshirt_spec(self):
        spec = PRODUCT_ATTRIBUTES[ProductType.TSHIRT]
        assert spec.sizes == ["S", "M", "L", "XL"]
        assert spec.colors == ["白"]
        assert spec.positions == ["正面"]
        assert spec.required_size is True
        assert spec.required_color is True
        assert spec.required_position is True

    def test_acrylic_keychain_spec(self):
        spec = PRODUCT_ATTRIBUTES[ProductType.ACRYLIC_KEYCHAIN]
        assert spec.sizes == ["50x50mm", "70x70mm", "100x100mm"]
        assert spec.required_size is True
        assert spec.required_color is False
        assert spec.required_position is False


class TestGetAttributeSpec:
    """get_attribute_spec() のテスト"""

    def test_returns_spec_for_valid_type(self):
        spec = get_attribute_spec(ProductType.TSHIRT)
        assert isinstance(spec, ProductAttributeSpec)

    def test_raises_for_unknown_type(self):
        with pytest.raises(ValidationError, match="Unknown product type"):
            get_attribute_spec("nonexistent")


class TestValidateProductAttributes:
    """validate_product_attributes() のテスト"""

    def test_valid_tshirt_attributes(self):
        validate_product_attributes(ProductType.TSHIRT, size="M", color="白", position="正面")

    def test_invalid_tshirt_size(self):
        with pytest.raises(ValidationError, match="Invalid size"):
            validate_product_attributes(ProductType.TSHIRT, size="XXL", color="白", position="正面")

    def test_missing_required_size(self):
        with pytest.raises(ValidationError, match="size is required"):
            validate_product_attributes(ProductType.TSHIRT, size=None, color="白", position="正面")

    def test_missing_required_color(self):
        with pytest.raises(ValidationError, match="color is required"):
            validate_product_attributes(ProductType.TSHIRT, size="M", color=None, position="正面")

    def test_optional_color_allowed_none(self):
        validate_product_attributes(ProductType.ACRYLIC_KEYCHAIN, size="50x50mm", color=None, position=None)

    def test_optional_color_still_validated_if_provided(self):
        with pytest.raises(ValidationError, match="Invalid color"):
            validate_product_attributes(ProductType.ACRYLIC_KEYCHAIN, size="50x50mm", color="赤", position=None)

    def test_valid_sticker_attributes(self):
        validate_product_attributes(ProductType.STICKER, size="50x50mm", color="ホワイト", position=None)

    def test_valid_tote_bag_attributes(self):
        validate_product_attributes(ProductType.TOTE_BAG, size="M", color="ナチュラル", position="正面")
```

- [ ] **Step 2: テスト実行 → FAIL 確認**

Run: `cd api && python -m pytest tests/unit/test_product_attributes.py -v`
Expected: ImportError (product_attributes module does not exist)

- [ ] **Step 3: product_attributes.py を実装**

```python
"""Product attribute registry.

Single source of truth for product attribute ENUMs and validation.
All product-specific size/color/position values are defined here.
"""

from dataclasses import dataclass, field
from enum import Enum

from app.models.product import ProductType
from app.utils.exceptions import ValidationError


# === T-shirt attributes ===

class TshirtSize(str, Enum):
    """Tシャツサイズ."""
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class TshirtColor(str, Enum):
    """Tシャツカラー."""
    WHITE = "白"


class TshirtPosition(str, Enum):
    """Tシャツプリント位置."""
    FRONT = "正面"


# === Acrylic Keychain attributes ===

class AcrylicKeychainSize(str, Enum):
    """アクリルキーホルダーサイズ."""
    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class AcrylicKeychainColor(str, Enum):
    """アクリルキーホルダーカラー."""
    ACRYLIC = "アクリル"


# === Acrylic Stand attributes ===

class AcrylicStandSize(str, Enum):
    """アクリルスタンドサイズ."""
    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class AcrylicStandColor(str, Enum):
    """アクリルスタンドカラー."""
    ACRYLIC = "アクリル"


# === Sticker attributes ===

class StickerSize(str, Enum):
    """ステッカーサイズ."""
    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class StickerColor(str, Enum):
    """ステッカーカラー."""
    WHITE = "ホワイト"


# === Tote Bag attributes ===

class ToteBagSize(str, Enum):
    """トートバッグサイズ."""
    M = "M"


class ToteBagColor(str, Enum):
    """トートバッグカラー."""
    NATURAL = "ナチュラル"


class ToteBagPosition(str, Enum):
    """トートバッグプリント位置."""
    FRONT = "正面"


# === Attribute Spec ===

@dataclass(frozen=True)
class ProductAttributeSpec:
    """Defines valid attribute values and requirements for a product type."""
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
    ProductType.ACRYLIC_KEYCHAIN: ProductAttributeSpec(
        sizes=[s.value for s in AcrylicKeychainSize],
        colors=[c.value for c in AcrylicKeychainColor],
        positions=[],
        required_size=True,
        required_color=False,
        required_position=False,
    ),
    ProductType.ACRYLIC_STAND: ProductAttributeSpec(
        sizes=[s.value for s in AcrylicStandSize],
        colors=[c.value for c in AcrylicStandColor],
        positions=[],
        required_size=True,
        required_color=False,
        required_position=False,
    ),
    ProductType.STICKER: ProductAttributeSpec(
        sizes=[s.value for s in StickerSize],
        colors=[c.value for c in StickerColor],
        positions=[],
        required_size=True,
        required_color=True,
        required_position=False,
    ),
    ProductType.TOTE_BAG: ProductAttributeSpec(
        sizes=[s.value for s in ToteBagSize],
        colors=[c.value for c in ToteBagColor],
        positions=[p.value for p in ToteBagPosition],
        required_size=True,
        required_color=True,
        required_position=True,
    ),
}


def get_attribute_spec(product_type: ProductType | str) -> ProductAttributeSpec:
    """Get attribute spec for a product type."""
    if isinstance(product_type, str):
        try:
            product_type = ProductType(product_type)
        except ValueError:
            raise ValidationError(f"Unknown product type: {product_type}")
    spec = PRODUCT_ATTRIBUTES.get(product_type)
    if spec is None:
        raise ValidationError(f"Unknown product type: {product_type}")
    return spec


def validate_product_attributes(
    product_type: ProductType | str,
    size: str | None,
    color: str | None,
    position: str | None,
    uid: str | None = None,
) -> None:
    """Validate product attributes against the registry.

    Args:
        product_type: The product type to validate against.
        size: Size value to validate.
        color: Color value to validate.
        position: Position value to validate.
        uid: Optional item UID for error messages (used by order validation).

    Raises:
        ValidationError: If any attribute is invalid or required but missing.
    """
    spec = get_attribute_spec(product_type)
    uid_suffix = f" (uid: {uid})" if uid else ""

    # Size validation
    if spec.required_size and not size:
        raise ValidationError(f"size is required for {product_type}{uid_suffix}")
    if size and spec.sizes and size not in spec.sizes:
        raise ValidationError(
            f"Invalid size '{size}'. Valid: {spec.sizes}{uid_suffix}"
        )

    # Color validation
    if spec.required_color and not color:
        raise ValidationError(f"color is required for {product_type}{uid_suffix}")
    if color and spec.colors and color not in spec.colors:
        raise ValidationError(
            f"Invalid color '{color}'. Valid: {spec.colors}{uid_suffix}"
        )

    # Position validation
    if spec.required_position and not position:
        raise ValidationError(f"position is required for {product_type}{uid_suffix}")
    if position and spec.positions and position not in spec.positions:
        raise ValidationError(
            f"Invalid position '{position}'. Valid: {spec.positions}{uid_suffix}"
        )
```

- [ ] **Step 4: テスト実行 → PASS 確認**

Run: `cd api && python -m pytest tests/unit/test_product_attributes.py -v`
Expected: All PASS

- [ ] **Step 5: コミット**

```bash
git add api/app/models/product_attributes.py api/tests/unit/test_product_attributes.py
git commit -m "feat: 商品属性レジストリモジュールを追加"
```

---

### Task 2: order.py から属性 ENUM を削除し、全 import を切り替え

**Files:**
- Modify: `api/app/models/order.py` — 属性 ENUM 定義を削除
- Modify: `api/app/services/order_service.py` — import 元を product_attributes に変更、個別バリデーションメソッドを共通化
- Modify: `api/app/services/external_service.py` — import 元を product_attributes に変更、get_product_options を簡素化、個別バリデーションを共通化
- Modify: `api/app/schemas/external.py` — import 元を product_attributes に変更
- Modify: `api/tests/unit/test_sticker_color_removal.py` — import 元を product_attributes に変更

- [ ] **Step 1: order.py から属性 ENUM を削除**

`api/app/models/order.py` の lines 35-117（`TshirtSize` から `ToteBagPosition` まで）を削除する。

- [ ] **Step 2: order_service.py の import と validate を置換**

import セクションを変更:
```python
# Before:
from app.models.order import (
    AcrylicKeychainSize,
    AcrylicStandSize,
    Order,
    OrderItem,
    OrderStatus,
    StickerColor,
    StickerSize,
    ToteBagColor,
    ToteBagPosition,
    ToteBagSize,
    TshirtColor,
    TshirtPosition,
    TshirtSize,
)

# After:
from app.models.order import (
    Order,
    OrderItem,
    OrderStatus,
)
from app.models.product_attributes import validate_product_attributes
```

`_validate_item_attributes()` メソッドを置換:
```python
def _validate_item_attributes(self, item_data: OrderItemCreate) -> None:
    """Validate item attributes based on product_type."""
    validate_product_attributes(
        product_type=item_data.product_type,
        size=item_data.size,
        color=item_data.color,
        position=item_data.position,
        uid=item_data.uid,
    )
```

個別バリデーションメソッド（`_validate_tshirt_attributes` 〜 `_validate_tote_bag_attributes`、lines 354-492）を全て削除する。

- [ ] **Step 3: external_service.py の import とバリデーションを置換**

import セクションを変更:
```python
# Before:
from app.models.order import (
    AcrylicKeychainColor,
    AcrylicKeychainSize,
    AcrylicStandColor,
    AcrylicStandSize,
    OrderStatus,
    StickerColor,
    StickerSize,
    ToteBagColor,
    ToteBagPosition,
    ToteBagSize,
    TshirtColor,
    TshirtPosition,
    TshirtSize,
)

# After:
from app.models.order import OrderStatus
from app.models.product_attributes import (
    PRODUCT_ATTRIBUTES,
    AcrylicKeychainSize,
    AcrylicStandSize,
    StickerSize,
    get_attribute_spec,
    validate_product_attributes,
)
```

`get_product_options()` を簡素化:
```python
def get_product_options(self, product_type: ProductType) -> ProductOptionsResponse:
    """Get available options for a product type."""
    spec = get_attribute_spec(product_type)
    return ProductOptionsResponse(
        product_type=product_type,
        size=spec.sizes,
        color=spec.colors,
        position=spec.positions,
    )
```

各 `_calculate_*_price()` メソッドの validate 部分を `validate_product_attributes()` 呼び出しに置換する。価格計算ロジック（`ACRYLIC_KEYCHAIN_PRICES` 等の辞書参照と `unit_price` 計算）はそのまま維持する。

例（`_calculate_tshirt_price`）:
```python
async def _calculate_tshirt_price(
    self, data: PriceCalculationRequest
) -> PriceCalculationResponse:
    """Calculate price for T-shirt."""
    validate_product_attributes(
        product_type=data.product_type,
        size=data.size,
        color=data.color,
        position=data.position,
    )
    unit_price = 870
    total_price = unit_price * data.quantity
    return PriceCalculationResponse(
        product_type=data.product_type,
        size=data.size,
        color=data.color,
        position=data.position,
        quantity=data.quantity,
        unit_price=unit_price,
        total_price=total_price,
    )
```

- [ ] **Step 4: schemas/external.py の import を修正**

```python
# Before:
from app.models.order import OrderStatus, TshirtColor, TshirtPosition, TshirtSize

# After:
from app.models.order import OrderStatus
```

（`TshirtColor` 等は `schemas/external.py` 内で実際には使用されていないため、削除のみ）

- [ ] **Step 5: test_sticker_color_removal.py の import を修正**

```python
# Before:
from app.models.order import StickerColor

# After:
from app.models.product_attributes import StickerColor
```

- [ ] **Step 6: 既存テストが通ることを確認**

Run: `cd api && python -m pytest tests/ -v --tb=short -q`
Expected: All existing tests PASS

- [ ] **Step 7: コミット**

```bash
git add api/app/models/order.py api/app/services/order_service.py api/app/services/external_service.py api/app/schemas/external.py api/tests/unit/test_sticker_color_removal.py
git commit -m "refactor: 全バリデーションを属性レジストリに統一"
```

---

### Task 3: ProductService にバリデーション追加

**Files:**
- Modify: `api/app/services/product_service.py`
- Create: `api/tests/unit/test_product_attribute_validation_in_service.py`

- [ ] **Step 1: テストファイルを作成**

```python
"""ProductService の属性バリデーションテスト"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.product import Product, ProductType
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product_service import ProductService
from app.utils.exceptions import ValidationError


class TestProductServiceAttributeValidation:
    """商品作成/更新時の属性バリデーション"""

    @pytest.fixture
    def mock_product_repo(self):
        repo = AsyncMock(spec=ProductRepository)
        repo.find_duplicate.return_value = None
        return repo

    @pytest.fixture
    def mock_manufacturer_repo(self):
        repo = AsyncMock()
        repo.find_by_id.return_value = MagicMock(id="mfr-1")
        return repo

    @pytest.fixture
    def service(self, mock_product_repo, mock_manufacturer_repo):
        return ProductService(
            product_repo=mock_product_repo,
            manufacturer_repo=mock_manufacturer_repo,
        )

    @pytest.mark.asyncio
    async def test_create_with_valid_tshirt_attributes(self, service, mock_product_repo):
        """有効なTシャツ属性で作成できる"""
        mock_product = MagicMock(spec=Product)
        mock_product.id = "new-id"
        mock_product.product_type = "tshirt"
        mock_product.size = "M"
        mock_product.position = "正面"
        mock_product.color = "白"
        mock_product.manufacturer_id = "mfr-1"
        mock_product.cost = 870
        mock_product.lead_time_days = 10
        mock_product.order_limit = None
        mock_product.is_active = True
        mock_product.created_at = "2026-01-01T00:00:00"
        mock_product.updated_at = "2026-01-01T00:00:00"
        mock_product_repo.create.return_value = mock_product

        data = ProductCreate(
            product_type=ProductType.TSHIRT,
            size="M",
            position="正面",
            color="白",
            manufacturer_id="mfr-1",
            cost=870,
            lead_time_days=10,
        )
        result = await service.create(data)
        assert result.id == "new-id"

    @pytest.mark.asyncio
    async def test_create_with_invalid_size_raises_error(self, service):
        """無効なサイズで作成するとエラー"""
        data = ProductCreate(
            product_type=ProductType.TSHIRT,
            size="XXL",
            position="正面",
            color="白",
            manufacturer_id="mfr-1",
            cost=870,
            lead_time_days=10,
        )
        with pytest.raises(ValidationError, match="Invalid size"):
            await service.create(data)

    @pytest.mark.asyncio
    async def test_create_with_invalid_color_raises_error(self, service):
        """無効なカラーで作成するとエラー"""
        data = ProductCreate(
            product_type=ProductType.TSHIRT,
            size="M",
            position="正面",
            color="ブラック",
            manufacturer_id="mfr-1",
            cost=870,
            lead_time_days=10,
        )
        with pytest.raises(ValidationError, match="Invalid color"):
            await service.create(data)

    @pytest.mark.asyncio
    async def test_create_acrylic_keychain_without_color_ok(self, service, mock_product_repo):
        """アクリルキーホルダーは color なしで作成可能"""
        mock_product = MagicMock(spec=Product)
        mock_product.id = "new-id"
        mock_product.product_type = "acrylic_keychain"
        mock_product.size = "50x50mm"
        mock_product.position = None
        mock_product.color = None
        mock_product.manufacturer_id = "mfr-1"
        mock_product.cost = 285
        mock_product.lead_time_days = 10
        mock_product.order_limit = None
        mock_product.is_active = True
        mock_product.created_at = "2026-01-01T00:00:00"
        mock_product.updated_at = "2026-01-01T00:00:00"
        mock_product_repo.create.return_value = mock_product

        data = ProductCreate(
            product_type=ProductType.ACRYLIC_KEYCHAIN,
            size="50x50mm",
            position=None,
            color=None,
            manufacturer_id="mfr-1",
            cost=285,
            lead_time_days=10,
        )
        result = await service.create(data)
        assert result.id == "new-id"

    @pytest.mark.asyncio
    async def test_update_with_invalid_size_raises_error(self, service, mock_product_repo):
        """更新時に無効なサイズだとエラー"""
        product = MagicMock(spec=Product)
        product.id = "prod-id"
        product.product_type = "tshirt"
        product.size = "M"
        product.position = "正面"
        product.color = "白"
        product.manufacturer_id = "mfr-1"
        mock_product_repo.find_by_id.return_value = product

        data = ProductUpdate(size="XXL")
        with pytest.raises(ValidationError, match="Invalid size"):
            await service.update("prod-id", data)
```

- [ ] **Step 2: テスト実行 → FAIL 確認**

Run: `cd api && python -m pytest tests/unit/test_product_attribute_validation_in_service.py -v`
Expected: FAIL (ProductService doesn't validate attributes yet)

- [ ] **Step 3: ProductService に validate_product_attributes 呼び出しを追加**

`api/app/services/product_service.py` の `create()` メソッドに追加（manufacturer チェックの後、duplicate チェックの前）:
```python
from app.models.product_attributes import validate_product_attributes

# In create():
validate_product_attributes(
    product_type=data.product_type,
    size=data.size,
    color=data.color,
    position=data.position,
)

# In update() — after computing final_* values:
validate_product_attributes(
    product_type=final_product_type,
    size=final_size,
    color=final_color,
    position=final_position,
)
```

- [ ] **Step 4: テスト実行 → PASS 確認**

Run: `cd api && python -m pytest tests/unit/test_product_attribute_validation_in_service.py -v`
Expected: All PASS

- [ ] **Step 5: 全テスト実行 → PASS 確認**

Run: `cd api && python -m pytest tests/ -v --tb=short -q`
Expected: All PASS

- [ ] **Step 6: コミット**

```bash
git add api/app/services/product_service.py api/tests/unit/test_product_attribute_validation_in_service.py
git commit -m "feat: 商品マスタ登録/更新に属性バリデーションを追加"
```

---

### Task 4: 属性 API エンドポイント追加

**Files:**
- Modify: `api/app/routers/products.py`
- Modify: `api/app/schemas/product.py`
- Create: `api/tests/unit/test_product_attributes_endpoint.py`

- [ ] **Step 1: テストファイルを作成**

```python
"""属性 API エンドポイントのテスト"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.config import settings
from app.dependencies import get_current_admin
from app.models.user import User, UserRole

API_PREFIX = settings.API_V1_PREFIX


def get_mock_admin():
    return User(
        id="test-admin-id",
        email="admin@test.com",
        name="Test Admin",
        role=UserRole.ADMIN,
        password_hash="dummy",
        is_active=True,
    )


@pytest.fixture
async def auth_client():
    app.dependency_overrides[get_current_admin] = get_mock_admin
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestProductAttributesEndpoint:
    @pytest.mark.asyncio
    async def test_get_tshirt_attributes(self, auth_client):
        response = await auth_client.get(f"{API_PREFIX}/products/attributes/tshirt")
        assert response.status_code == 200
        data = response.json()
        assert data["product_type"] == "tshirt"
        assert data["sizes"] == ["S", "M", "L", "XL"]
        assert data["colors"] == ["白"]
        assert data["positions"] == ["正面"]
        assert data["required_size"] is True
        assert data["required_color"] is True
        assert data["required_position"] is True

    @pytest.mark.asyncio
    async def test_get_acrylic_keychain_attributes(self, auth_client):
        response = await auth_client.get(f"{API_PREFIX}/products/attributes/acrylic_keychain")
        assert response.status_code == 200
        data = response.json()
        assert data["sizes"] == ["50x50mm", "70x70mm", "100x100mm"]
        assert data["required_color"] is False

    @pytest.mark.asyncio
    async def test_get_invalid_product_type_returns_422(self, auth_client):
        response = await auth_client.get(f"{API_PREFIX}/products/attributes/invalid_type")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_all_attributes(self, auth_client):
        response = await auth_client.get(f"{API_PREFIX}/products/attributes")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        types = [item["product_type"] for item in data]
        assert "tshirt" in types
        assert "acrylic_keychain" in types
```

- [ ] **Step 2: テスト実行 → FAIL 確認**

Run: `cd api && python -m pytest tests/unit/test_product_attributes_endpoint.py -v`
Expected: FAIL (404 — endpoint does not exist)

- [ ] **Step 3: スキーマ追加**

`api/app/schemas/product.py` に追加:
```python
class ProductAttributeSpecResponse(BaseModel):
    """Product attribute spec response."""
    product_type: str
    sizes: list[str]
    colors: list[str]
    positions: list[str]
    required_size: bool
    required_color: bool
    required_position: bool
```

- [ ] **Step 4: エンドポイント追加**

`api/app/routers/products.py` に追加（`list_products` の前に配置して `/attributes` がルートマッチで `/{product_id}` に取られないようにする）:
```python
from app.models.product_attributes import PRODUCT_ATTRIBUTES, get_attribute_spec
from app.schemas.product import ProductAttributeSpecResponse

@router.get("/attributes", response_model=list[ProductAttributeSpecResponse])
async def list_product_attributes(
    current_user: Annotated[User, Depends(get_current_admin)],
) -> list[ProductAttributeSpecResponse]:
    """List attribute specs for all product types."""
    return [
        ProductAttributeSpecResponse(
            product_type=pt.value,
            sizes=spec.sizes,
            colors=spec.colors,
            positions=spec.positions,
            required_size=spec.required_size,
            required_color=spec.required_color,
            required_position=spec.required_position,
        )
        for pt, spec in PRODUCT_ATTRIBUTES.items()
    ]

@router.get("/attributes/{product_type}", response_model=ProductAttributeSpecResponse)
async def get_product_attributes(
    product_type: ProductType,
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductAttributeSpecResponse:
    """Get attribute spec for a specific product type."""
    spec = get_attribute_spec(product_type)
    return ProductAttributeSpecResponse(
        product_type=product_type.value,
        sizes=spec.sizes,
        colors=spec.colors,
        positions=spec.positions,
        required_size=spec.required_size,
        required_color=spec.required_color,
        required_position=spec.required_position,
    )
```

**注意:** `/attributes` と `/attributes/{product_type}` のルートは `/{product_id}` より前に定義する。

- [ ] **Step 5: テスト実行 → PASS 確認**

Run: `cd api && python -m pytest tests/unit/test_product_attributes_endpoint.py -v`
Expected: All PASS

- [ ] **Step 6: コミット**

```bash
git add api/app/routers/products.py api/app/schemas/product.py api/tests/unit/test_product_attributes_endpoint.py
git commit -m "feat: 商品属性エンドポイント追加"
```

---

### Task 5: フロントエンド — 型定義と API クライアント

**Files:**
- Modify: `web/src/types/api/index.ts`

- [ ] **Step 1: ProductAttributeSpec 型を追加**

`web/src/types/api/index.ts` の `Product` 定義の後に追加:
```typescript
export interface ProductAttributeSpec {
  product_type: ProductType;
  sizes: string[];
  colors: string[];
  positions: string[];
  required_size: boolean;
  required_color: boolean;
  required_position: boolean;
}
```

- [ ] **Step 2: コミット**

```bash
git add web/src/types/api/index.ts
git commit -m "feat: フロントエンドに商品属性型定義を追加"
```

---

### Task 6: フロントエンド — 商品フォームのドロップダウン化

**Files:**
- Modify: `web/src/features/products/components/product-form.tsx`

- [ ] **Step 1: 属性 API を取得してドロップダウンに変更**

`product-form.tsx` を以下のように変更:

1. 属性 API 用の SWR フックを追加:
```typescript
import type { Product, ProductType, Manufacturer, ManufacturerListResponse, ProductAttributeSpec } from "@/types/api";

// フォーム内部で:
const selectedProductType = form.watch("product_type");

const { data: attributeSpec } = useSWR<ProductAttributeSpec>(
  selectedProductType ? `/products/attributes/${selectedProductType}` : null,
  (url: string) => apiClient<ProductAttributeSpec>(url)
);
```

2. size/color/position フィールドを `Select` に変更（選択肢がない場合は非表示）:
```tsx
{attributeSpec && attributeSpec.sizes.length > 0 && (
  <FormField
    control={form.control}
    name="size"
    render={({ field }) => (
      <FormItem>
        <FormLabel>
          サイズ{attributeSpec.required_size ? "（必須）" : "（任意）"}
        </FormLabel>
        <Select onValueChange={field.onChange} value={field.value || ""}>
          <FormControl>
            <SelectTrigger>
              <SelectValue placeholder="サイズを選択" />
            </SelectTrigger>
          </FormControl>
          <SelectContent>
            {attributeSpec.sizes.map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <FormMessage />
      </FormItem>
    )}
  />
)}
```

color フィールド:
```tsx
{attributeSpec && attributeSpec.colors.length > 0 && (
  <FormField
    control={form.control}
    name="color"
    render={({ field }) => (
      <FormItem>
        <FormLabel>
          カラー{attributeSpec.required_color ? "（必須）" : "（任意）"}
        </FormLabel>
        <Select onValueChange={field.onChange} value={field.value || ""}>
          <FormControl>
            <SelectTrigger>
              <SelectValue placeholder="カラーを選択" />
            </SelectTrigger>
          </FormControl>
          <SelectContent>
            {attributeSpec.colors.map((c) => (
              <SelectItem key={c} value={c}>{c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <FormMessage />
      </FormItem>
    )}
  />
)}
```

position フィールド:
```tsx
{attributeSpec && attributeSpec.positions.length > 0 && (
  <FormField
    control={form.control}
    name="position"
    render={({ field }) => (
      <FormItem>
        <FormLabel>
          印刷位置{attributeSpec.required_position ? "（必須）" : "（任意）"}
        </FormLabel>
        <Select onValueChange={field.onChange} value={field.value || ""}>
          <FormControl>
            <SelectTrigger>
              <SelectValue placeholder="印刷位置を選択" />
            </SelectTrigger>
          </FormControl>
          <SelectContent>
            {attributeSpec.positions.map((p) => (
              <SelectItem key={p} value={p}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <FormMessage />
      </FormItem>
    )}
  />
)}
```

3. product_type 変更時に size/color/position をリセット:
```typescript
// useEffect で product_type 変更時にリセット
import { useEffect } from "react";

useEffect(() => {
  if (!product) {  // 新規作成時のみリセット
    form.setValue("size", "");
    form.setValue("color", "");
    form.setValue("position", "");
  }
}, [selectedProductType]);
```

- [ ] **Step 2: ビルド確認**

Run: `cd web && npx next build`
Expected: Build succeeds

- [ ] **Step 3: コミット**

```bash
git add web/src/features/products/components/product-form.tsx
git commit -m "feat: 商品フォームの属性入力をドロップダウンに変更"
```

---

### Task 7: リグレッション確認と既存テスト更新

**Files:**
- Possibly modify: existing test files that import from `order.py`

- [ ] **Step 1: order.py の ENUM を import している箇所を特定**

```bash
cd api && grep -r "from app.models.order import.*Size\|from app.models.order import.*Color\|from app.models.order import.*Position" api/ tests/ --include="*.py"
```

- [ ] **Step 2: 残りの import を product_attributes に更新**

見つかったファイルの import を `app.models.product_attributes` に変更する。（Task 2 で主要なファイルは更新済み。ここでは漏れを検出・修正する。）

- [ ] **Step 3: 全テスト実行**

Run: `cd api && python -m pytest tests/ -v --tb=short -q`
Expected: All PASS

- [ ] **Step 4: フロントエンドの lint/型チェック**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: コミット**

```bash
git add -A
git commit -m "fix: 属性ENUM移動に伴うimport修正"
```
