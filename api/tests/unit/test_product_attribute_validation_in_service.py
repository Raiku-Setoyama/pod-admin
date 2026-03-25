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
