"""ProductService / ProductResponse の manufacturer_name ユニットテスト

FEAT-0016: 商品マスター一覧で各商品のメーカー名が正しく表示される

テスト対象:
- AC-005: ProductResponseスキーマに manufacturer_name フィールドが定義されている
- AC-006: ProductService.list() が manufacturer_name を含むレスポンスを返す
- AC-007: ProductService.get_by_id() が manufacturer_name を含むレスポンスを返す
- AC-008: manufacturer リレーションが None の場合、manufacturer_name は null になる
"""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.product import ProductType
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse
from app.services.product_service import ProductService

# ---------------------------------------------------------------------------
# Helper: mock Product model factory
# ---------------------------------------------------------------------------

def _make_product(
    *,
    id: str | None = None,
    product_type: str = ProductType.ACRYLIC_KEYCHAIN.value,
    size: str = "50x50mm",
    position: str | None = "center",
    color: str | None = "clear",
    manufacturer_id: str | None = None,
    cost: int = 500,
    lead_time_days: int = 7,
    order_limit: int | None = 100,
    is_active: bool = True,
    manufacturer_name: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> MagicMock:
    """Create a mock Product model instance with optional manufacturer relation."""
    product = MagicMock()
    product.id = id or str(uuid4())
    product.product_type = product_type
    product.size = size
    product.position = position
    product.color = color
    product.manufacturer_id = manufacturer_id or str(uuid4())
    product.cost = cost
    product.lead_time_days = lead_time_days
    product.order_limit = order_limit
    product.is_active = is_active
    product.created_at = created_at or datetime(2026, 1, 1, 0, 0, 0)
    product.updated_at = updated_at or datetime(2026, 1, 1, 0, 0, 0)

    # manufacturer リレーション
    if manufacturer_name is not None:
        manufacturer = MagicMock()
        manufacturer.name = manufacturer_name
        product.manufacturer = manufacturer
    else:
        product.manufacturer = None

    return product


# ---------------------------------------------------------------------------
# AC-005: ProductResponseスキーマに manufacturer_name フィールドが定義されている
# ---------------------------------------------------------------------------

class TestProductResponseSchema:
    """AC-005: ProductResponse スキーマのテスト"""

    def test_ac005_product_response_has_manufacturer_name_field(self) -> None:
        """AC-005: ProductResponseスキーマに manufacturer_name フィールドが定義されている

        given: ProductResponseスキーマが定義されている
        when: manufacturer_name フィールドの存在を確認する
        then: manufacturer_name: Optional[str]（デフォルト null）が定義されている
        """
        # フィールドが存在することを確認
        assert "manufacturer_name" in ProductResponse.model_fields, (
            "ProductResponse should have 'manufacturer_name' field"
        )

        # フィールドのデフォルト値が None であることを確認
        field_info = ProductResponse.model_fields["manufacturer_name"]
        assert field_info.default is None, (
            "manufacturer_name should have default value of None"
        )

    def test_ac005_product_response_manufacturer_name_accepts_string(self) -> None:
        """manufacturer_name に文字列を設定できる

        given: ProductResponseのデータにmanufacturer_name文字列が含まれている
        when: ProductResponseを構築する
        then: manufacturer_nameが文字列として設定される
        """
        data = {
            "id": str(uuid4()),
            "product_type": ProductType.ACRYLIC_KEYCHAIN,
            "size": "50x50mm",
            "position": "center",
            "color": "clear",
            "manufacturer_id": str(uuid4()),
            "cost": 500,
            "lead_time_days": 7,
            "order_limit": 100,
            "is_active": True,
            "manufacturer_name": "テストメーカー",
            "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 1, 1),
        }

        response = ProductResponse(**data)
        assert response.manufacturer_name == "テストメーカー"

    def test_ac005_product_response_manufacturer_name_defaults_to_none(self) -> None:
        """manufacturer_name を省略した場合 None になる

        given: ProductResponseのデータにmanufacturer_nameが含まれていない
        when: ProductResponseを構築する
        then: manufacturer_nameがNoneになる
        """
        data = {
            "id": str(uuid4()),
            "product_type": ProductType.ACRYLIC_KEYCHAIN,
            "size": "50x50mm",
            "position": "center",
            "color": "clear",
            "manufacturer_id": str(uuid4()),
            "cost": 500,
            "lead_time_days": 7,
            "order_limit": 100,
            "is_active": True,
            "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 1, 1),
        }

        response = ProductResponse(**data)
        assert response.manufacturer_name is None


# ---------------------------------------------------------------------------
# AC-006: ProductService.list() が manufacturer_name を含むレスポンスを返す
# ---------------------------------------------------------------------------

class TestProductServiceList:
    """AC-006: ProductService.list() のテスト"""

    @pytest.fixture
    def mock_product_repo(self) -> Any:
        """モック ProductRepository"""
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self) -> Any:
        """モック ManufacturerRepository"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_product_repo: Any, mock_manufacturer_repo: Any) -> Any:
        """テスト対象のサービスインスタンス"""
        return ProductService(mock_product_repo, mock_manufacturer_repo)

    @pytest.mark.asyncio
    async def test_ac006_list_returns_manufacturer_name(
        self,
        service: ProductService,
        mock_product_repo: AsyncMock,
    ) -> None:
        """AC-006: ProductService.list() が manufacturer_name を含むレスポンスを返す

        given: manufacturer.name = "テストメーカー" のリレーションを持つ Product がリポジトリから返される
        when: ProductService.list() を呼び出す
        then: 各 ProductResponse の manufacturer_name に "テストメーカー" が設定されている
        """
        product = _make_product(manufacturer_name="テストメーカー")
        mock_product_repo.find_all.return_value = ([product], 1)

        result = await service.list(page=1, limit=20)

        assert isinstance(result, ProductListResponse)
        assert len(result.items) == 1
        assert result.items[0].manufacturer_name == "テストメーカー"

    @pytest.mark.asyncio
    async def test_ac006_list_returns_multiple_products_with_manufacturer_names(
        self,
        service: ProductService,
        mock_product_repo: AsyncMock,
    ) -> None:
        """複数商品それぞれに正しい manufacturer_name が返される

        given: 異なるメーカーに紐づく商品が2件ある
        when: ProductService.list() を呼び出す
        then: 各商品のmanufacturer_nameにそれぞれのメーカー名が設定される
        """
        product1 = _make_product(manufacturer_name="メーカーA")
        product2 = _make_product(manufacturer_name="メーカーB")
        mock_product_repo.find_all.return_value = ([product1, product2], 2)

        result = await service.list(page=1, limit=20)

        assert len(result.items) == 2
        assert result.items[0].manufacturer_name == "メーカーA"
        assert result.items[1].manufacturer_name == "メーカーB"


# ---------------------------------------------------------------------------
# AC-007: ProductService.get_by_id() が manufacturer_name を含むレスポンスを返す
# ---------------------------------------------------------------------------

class TestProductServiceGetById:
    """AC-007: ProductService.get_by_id() のテスト"""

    @pytest.fixture
    def mock_product_repo(self) -> Any:
        """モック ProductRepository"""
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self) -> Any:
        """モック ManufacturerRepository"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_product_repo: Any, mock_manufacturer_repo: Any) -> Any:
        """テスト対象のサービスインスタンス"""
        return ProductService(mock_product_repo, mock_manufacturer_repo)

    @pytest.mark.asyncio
    async def test_ac007_get_by_id_returns_manufacturer_name(
        self,
        service: ProductService,
        mock_product_repo: AsyncMock,
    ) -> None:
        """AC-007: ProductService.get_by_id() が manufacturer_name を含むレスポンスを返す

        given: manufacturer.name = "テストメーカー" のリレーションを持つ Product がリポジトリから返される
        when: ProductService.get_by_id() を呼び出す
        then: ProductResponse の manufacturer_name に "テストメーカー" が設定されている
        """
        product_id = str(uuid4())
        product = _make_product(id=product_id, manufacturer_name="テストメーカー")
        mock_product_repo.find_by_id.return_value = product

        result = await service.get_by_id(product_id)

        assert isinstance(result, ProductResponse)
        assert result.manufacturer_name == "テストメーカー"


# ---------------------------------------------------------------------------
# AC-008: manufacturer リレーションが None の場合、manufacturer_name は null
# ---------------------------------------------------------------------------

class TestProductManufacturerNameNull:
    """AC-008: manufacturer リレーションが None の場合のテスト"""

    @pytest.fixture
    def mock_product_repo(self) -> Any:
        """モック ProductRepository"""
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self) -> Any:
        """モック ManufacturerRepository"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_product_repo: Any, mock_manufacturer_repo: Any) -> Any:
        """テスト対象のサービスインスタンス"""
        return ProductService(mock_product_repo, mock_manufacturer_repo)

    @pytest.mark.asyncio
    async def test_ac008_manufacturer_none_returns_null_name(
        self,
        service: ProductService,
        mock_product_repo: AsyncMock,
    ) -> None:
        """AC-008: manufacturer リレーションが None の場合、manufacturer_name は null になる

        given: manufacturer リレーションが None の Product オブジェクトがある
        when: ProductService.get_by_id() を呼び出す
        then: manufacturer_name が None になる
        """
        product_id = str(uuid4())
        product = _make_product(id=product_id, manufacturer_name=None)
        mock_product_repo.find_by_id.return_value = product

        result = await service.get_by_id(product_id)

        assert isinstance(result, ProductResponse)
        assert result.manufacturer_name is None

    @pytest.mark.asyncio
    async def test_ac008_list_with_manufacturer_none_returns_null_name(
        self,
        service: ProductService,
        mock_product_repo: AsyncMock,
    ) -> None:
        """一覧取得時も manufacturer が None の場合は manufacturer_name が null になる

        given: manufacturer リレーションが None の Product がリポジトリから返される
        when: ProductService.list() を呼び出す
        then: ProductResponse の manufacturer_name が None になる
        """
        product = _make_product(manufacturer_name=None)
        mock_product_repo.find_all.return_value = ([product], 1)

        result = await service.list(page=1, limit=20)

        assert len(result.items) == 1
        assert result.items[0].manufacturer_name is None

    @pytest.mark.asyncio
    async def test_ac008_create_returns_manufacturer_name(
        self,
        service: ProductService,
        mock_product_repo: AsyncMock,
        mock_manufacturer_repo: AsyncMock,
    ) -> None:
        """商品作成後のレスポンスにも manufacturer_name が含まれる

        given: メーカー "テストメーカー" が存在する
        when: ProductService.create() で商品を作成する
        then: レスポンスの manufacturer_name に "テストメーカー" が設定されている
        """
        manufacturer_id = str(uuid4())
        manufacturer = MagicMock()
        manufacturer.id = manufacturer_id
        manufacturer.name = "テストメーカー"
        mock_manufacturer_repo.find_by_id.return_value = manufacturer

        # find_duplicate が None を返す（重複なし）
        mock_product_repo.find_duplicate.return_value = None

        # create が manufacturer リレーション付きの Product を返す
        created_product = _make_product(
            manufacturer_id=manufacturer_id,
            manufacturer_name="テストメーカー",
        )
        mock_product_repo.create.return_value = created_product

        data = ProductCreate(
            product_type=ProductType.ACRYLIC_KEYCHAIN,
            size="50x50mm",
            position="center",
            color="clear",
            manufacturer_id=manufacturer_id,
            cost=500,
            lead_time_days=7,
            order_limit=100,
        )

        result = await service.create(data)

        assert isinstance(result, ProductResponse)
        assert result.manufacturer_name == "テストメーカー"

    @pytest.mark.asyncio
    async def test_ac008_update_returns_manufacturer_name(
        self,
        service: ProductService,
        mock_product_repo: AsyncMock,
        mock_manufacturer_repo: AsyncMock,
    ) -> None:
        """商品更新後のレスポンスにも manufacturer_name が含まれる

        given: メーカー "テストメーカー" に紐づく商品が存在する
        when: ProductService.update() で商品を更新する
        then: レスポンスの manufacturer_name に "テストメーカー" が設定されている
        """
        product_id = str(uuid4())
        manufacturer_id = str(uuid4())

        existing_product = _make_product(
            id=product_id,
            manufacturer_id=manufacturer_id,
            manufacturer_name="テストメーカー",
        )
        mock_product_repo.find_by_id.return_value = existing_product

        # find_duplicate が None を返す（重複なし）
        mock_product_repo.find_duplicate.return_value = None

        # update が manufacturer リレーション付きの Product を返す
        updated_product = _make_product(
            id=product_id,
            manufacturer_id=manufacturer_id,
            manufacturer_name="テストメーカー",
            cost=600,
        )
        mock_product_repo.update.return_value = updated_product

        from app.schemas.product import ProductUpdate

        data = ProductUpdate(cost=600)

        result = await service.update(product_id, data)

        assert isinstance(result, ProductResponse)
        assert result.manufacturer_name == "テストメーカー"
