"""Unit tests for ProductAttributeService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.product_attribute import (
    ProductAttributeOption,
    ProductAttributeRequirement,
)
from app.schemas.product_attribute import ProductAttributeOptionCreate
from app.services.product_attribute_service import ProductAttributeService
from app.utils.exceptions import ValidationError


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_repo):
    return ProductAttributeService(mock_repo)


def _make_option(product_type: str, attr_name: str, attr_value: str) -> MagicMock:
    opt = MagicMock(spec=ProductAttributeOption)
    opt.product_type = product_type
    opt.attribute_name = attr_name
    opt.attribute_value = attr_value
    opt.is_active = True
    return opt


def _make_requirement(
    product_type: str,
    required_size: bool = True,
    required_color: bool = False,
    required_position: bool = False,
) -> MagicMock:
    req = MagicMock(spec=ProductAttributeRequirement)
    req.product_type = product_type
    req.required_size = required_size
    req.required_color = required_color
    req.required_position = required_position
    return req


class TestValidateAttributes:
    """Tests for validate_attributes()."""

    @pytest.mark.asyncio
    async def test_valid_tshirt_attributes(self, service, mock_repo):
        """全属性が正しい場合、エラーなし."""
        mock_repo.find_requirement.return_value = _make_requirement(
            "tshirt", required_size=True, required_color=True, required_position=True
        )
        mock_repo.find_options.side_effect = [
            [_make_option("tshirt", "size", "M")],
            [_make_option("tshirt", "color", "白")],
            [_make_option("tshirt", "position", "正面")],
        ]

        # Should not raise
        await service.validate_attributes("tshirt", size="M", color="白", position="正面")

    @pytest.mark.asyncio
    async def test_missing_required_size_raises(self, service, mock_repo):
        """必須の size が未指定の場合、ValidationError."""
        mock_repo.find_requirement.return_value = _make_requirement(
            "tshirt", required_size=True
        )

        with pytest.raises(ValidationError, match="size is required"):
            await service.validate_attributes("tshirt", size=None, color=None, position=None)

    @pytest.mark.asyncio
    async def test_invalid_size_value_raises(self, service, mock_repo):
        """無効な size 値の場合、ValidationError."""
        mock_repo.find_requirement.return_value = _make_requirement(
            "tshirt", required_size=True
        )
        mock_repo.find_options.return_value = [
            _make_option("tshirt", "size", "S"),
            _make_option("tshirt", "size", "M"),
        ]

        with pytest.raises(ValidationError, match="Invalid size 'XXL'"):
            await service.validate_attributes("tshirt", size="XXL", color=None, position=None)

    @pytest.mark.asyncio
    async def test_optional_color_skipped_when_none(self, service, mock_repo):
        """color が任意で未指定の場合、バリデーションスキップ."""
        mock_repo.find_requirement.return_value = _make_requirement(
            "acrylic_keychain", required_size=True, required_color=False
        )
        mock_repo.find_options.return_value = [
            _make_option("acrylic_keychain", "size", "50x50mm"),
        ]

        # Should not raise
        await service.validate_attributes(
            "acrylic_keychain", size="50x50mm", color=None, position=None
        )

    @pytest.mark.asyncio
    async def test_unknown_product_type_raises(self, service, mock_repo):
        """要件が未登録の product_type の場合、ValidationError."""
        mock_repo.find_requirement.return_value = None

        with pytest.raises(ValidationError, match="No attribute requirements"):
            await service.validate_attributes("unknown_type", size="M", color=None, position=None)


class TestGetAttributeSpec:
    """Tests for get_attribute_spec()."""

    @pytest.mark.asyncio
    async def test_returns_combined_spec(self, service, mock_repo):
        """オプションと要件を結合して返す."""
        mock_repo.find_requirement.return_value = _make_requirement(
            "tshirt", required_size=True, required_color=True, required_position=True
        )
        mock_repo.find_options.return_value = [
            _make_option("tshirt", "size", "S"),
            _make_option("tshirt", "size", "M"),
            _make_option("tshirt", "color", "白"),
            _make_option("tshirt", "position", "正面"),
        ]

        spec = await service.get_attribute_spec("tshirt")

        assert spec.product_type == "tshirt"
        assert spec.sizes == ["S", "M"]
        assert spec.colors == ["白"]
        assert spec.positions == ["正面"]
        assert spec.required_size is True
        assert spec.required_color is True
        assert spec.required_position is True


class TestCreateOption:
    """Tests for create_option()."""

    @pytest.mark.asyncio
    async def test_duplicate_raises(self, service, mock_repo):
        """同じ組み合わせが既に存在する場合、エラー."""
        mock_repo.find_option_by_value.return_value = _make_option(
            "tshirt", "size", "XXL"
        )
        data = ProductAttributeOptionCreate(
            product_type="tshirt",
            attribute_name="size",
            attribute_value="XXL",
        )

        with pytest.raises(ValidationError, match="already exists"):
            await service.create_option(data)

    @pytest.mark.asyncio
    async def test_create_success(self, service, mock_repo):
        """正常に作成."""
        mock_repo.find_option_by_value.return_value = None
        created = _make_option("tshirt", "size", "XXL")
        created.id = "test-id"
        created.display_order = 0
        created.created_at = "2026-01-01T00:00:00Z"
        created.updated_at = "2026-01-01T00:00:00Z"
        mock_repo.create_option.return_value = created

        data = ProductAttributeOptionCreate(
            product_type="tshirt",
            attribute_name="size",
            attribute_value="XXL",
        )
        result = await service.create_option(data)

        assert result.attribute_value == "XXL"
        mock_repo.create_option.assert_called_once()
