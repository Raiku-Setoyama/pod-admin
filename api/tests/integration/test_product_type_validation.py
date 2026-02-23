"""商品種別バリデーションの統合テスト

FEAT-0002: 商品種別を5種類に限定（マグカップ削除）

このテストは、APIに無効な商品種別（"mug"）を送信した場合に
バリデーションエラーが返されることを検証します。
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.config import settings
from app.dependencies import get_current_admin
from app.models.user import User, UserRole


# 認証をバイパスするためのモックユーザー
def get_mock_admin():
    """テスト用のモック管理者ユーザーを返す"""
    return User(
        id="test-admin-id",
        email="admin@test.com",
        name="Test Admin",
        role=UserRole.ADMIN,
        password_hash="dummy",
        is_active=True,
    )


# APIプレフィックス
API_PREFIX = settings.API_V1_PREFIX


@pytest.fixture
def valid_product_data():
    """有効な商品データ"""
    return {
        "product_type": "acrylic_keychain",
        "size": "50x50mm",
        "position": "center",
        "color": "clear",
        "manufacturer_id": "00000000-0000-0000-0000-000000000001",
        "cost": 500,
        "lead_time_days": 7,
        "order_limit": 100,
    }


@pytest.fixture
async def auth_client():
    """認証をバイパスしたHTTPクライアント"""
    # 認証依存関係をオーバーライド
    app.dependency_overrides[get_current_admin] = get_mock_admin

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # オーバーライドをクリア
    app.dependency_overrides.clear()


class TestProductTypeValidation:
    """商品種別バリデーションの統合テスト"""

    @pytest.mark.asyncio
    async def test_create_product_with_mug_returns_validation_error(
        self, auth_client: AsyncClient, valid_product_data: dict
    ):
        """product_type に "mug" を指定するとバリデーションエラーが返される"""
        # "mug" を指定
        valid_product_data["product_type"] = "mug"

        response = await auth_client.post(
            f"{API_PREFIX}/products", json=valid_product_data
        )

        # バリデーションエラー（422 Unprocessable Entity）を期待
        assert response.status_code == 422, (
            f"Expected 422 for invalid product_type 'mug', "
            f"but got {response.status_code}: {response.json()}"
        )

        # エラーレスポンスの内容を確認
        error_data = response.json()
        assert "detail" in error_data

        # エラーが product_type フィールドに関するものであることを確認
        errors = error_data["detail"]
        product_type_errors = [
            e for e in errors if "product_type" in str(e.get("loc", []))
        ]
        assert len(product_type_errors) > 0, (
            "Expected validation error for 'product_type' field"
        )

    @pytest.mark.asyncio
    async def test_update_product_with_mug_returns_validation_error(
        self, auth_client: AsyncClient
    ):
        """product_type に "mug" を指定して更新するとバリデーションエラーが返される"""
        # 存在するかどうかに関わらず、バリデーションエラーが先に返される
        update_data = {"product_type": "mug"}

        response = await auth_client.patch(
            f"{API_PREFIX}/products/00000000-0000-0000-0000-000000000001",
            json=update_data,
        )

        # バリデーションエラー（422 Unprocessable Entity）を期待
        assert response.status_code == 422, (
            f"Expected 422 for invalid product_type 'mug', "
            f"but got {response.status_code}: {response.json()}"
        )

    @pytest.mark.asyncio
    async def test_create_product_with_valid_types_passes_validation(
        self, auth_client: AsyncClient, valid_product_data: dict
    ):
        """許可された商品種別ではバリデーションエラーにならない"""
        valid_types = [
            "acrylic_keychain",
            "acrylic_stand",
            "sticker",
            "tote_bag",
            "tshirt",
        ]

        for product_type in valid_types:
            valid_product_data["product_type"] = product_type

            response = await auth_client.post(
                f"{API_PREFIX}/products", json=valid_product_data
            )

            # バリデーションは通過する（DBエラーなど他のエラーは許容）
            # 422 で product_type に関するエラーがあれば失敗
            if response.status_code == 422:
                error_data = response.json()
                errors = error_data.get("detail", [])
                product_type_errors = [
                    e for e in errors if "product_type" in str(e.get("loc", []))
                ]
                assert len(product_type_errors) == 0, (
                    f"Unexpected validation error for valid product_type "
                    f"'{product_type}': {errors}"
                )

    @pytest.mark.asyncio
    async def test_list_products_with_mug_filter_returns_validation_error(
        self, auth_client: AsyncClient
    ):
        """product_type クエリパラメータに "mug" を指定するとバリデーションエラーが返される"""
        response = await auth_client.get(
            f"{API_PREFIX}/products", params={"product_type": "mug"}
        )

        # バリデーションエラー（422 Unprocessable Entity）を期待
        assert response.status_code == 422, (
            f"Expected 422 for invalid product_type filter 'mug', "
            f"but got {response.status_code}: {response.json()}"
        )
