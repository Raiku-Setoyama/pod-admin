"""属性 API エンドポイントのテスト"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.dependencies import get_current_admin
from app.main import app
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
