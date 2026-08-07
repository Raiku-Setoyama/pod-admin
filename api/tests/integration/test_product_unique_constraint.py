"""商品マスタ ユニーク制約の統合テスト

FEAT-0008: 商品マスタ（productsテーブル）に product_type / size / position / color の
4カラム複合ユニーク制約を追加する。

このテストは、APIに重複する商品仕様を送信した場合に
409 Conflict エラーが返されることを検証します。
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_admin
from app.main import app
from app.models.manufacturer import Manufacturer, SharingMethod
from app.models.product import Product
from app.models.user import User, UserRole


# 認証をバイパスするためのモックユーザー
def get_mock_admin() -> Any:
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
async def auth_client() -> AsyncIterator[Any]:
    """認証をバイパスしたHTTPクライアント"""
    app.dependency_overrides[get_current_admin] = get_mock_admin

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_manufacturer(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
    """テスト用メーカーを作成"""
    manufacturer = Manufacturer(
        id=str(uuid4()),
        name=f"Test Manufacturer {str(uuid4())[:8]}",
        email=f"test-{str(uuid4())[:8]}@example.com",
        phone="03-0000-0000",
        supported_products=["tshirt", "sticker", "acrylic_keychain"],
        unit_prices={"tshirt": 870, "sticker": 79, "acrylic_keychain": 350},
        lead_time_days=10,
        daily_order_limit=200,
        sharing_method=SharingMethod.PORTAL.value,
        is_active=True,
    )
    db_session.add(manufacturer)
    await db_session.flush()
    await db_session.commit()

    yield {"id": manufacturer.id}


@pytest.fixture
async def test_product(db_session: AsyncSession, test_manufacturer: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """テスト用の商品を作成（ユニークな値を使用）"""
    # テストごとにユニークな値を使用して既存データとの衝突を避ける
    unique_suffix = str(uuid4())[:8]
    size = f"TEST-{unique_suffix}"
    position = f"テスト位置-{unique_suffix}"
    color = f"テスト色-{unique_suffix}"

    product = Product(
        id=str(uuid4()),
        product_type="tshirt",
        size=size,
        position=position,
        color=color,
        manufacturer_id=test_manufacturer["id"],
        cost=870,
        lead_time_days=10,
        is_active=True,
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.commit()

    yield {
        "id": product.id,
        "manufacturer_id": test_manufacturer["id"],
        "product_type": "tshirt",
        "size": size,
        "position": position,
        "color": color,
    }


@pytest.fixture
async def test_product_pair(db_session: AsyncSession, test_manufacturer: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """テスト用の商品ペア（2つの異なるサイズ）を作成"""
    unique_suffix = str(uuid4())[:8]
    size_a = f"PAIR-A-{unique_suffix}"
    size_b = f"PAIR-B-{unique_suffix}"
    position = f"ペア位置-{unique_suffix}"
    color = f"ペア色-{unique_suffix}"

    product_a = Product(
        id=str(uuid4()),
        product_type="tshirt",
        size=size_a,
        position=position,
        color=color,
        manufacturer_id=test_manufacturer["id"],
        cost=870,
        lead_time_days=10,
        is_active=True,
    )
    product_b = Product(
        id=str(uuid4()),
        product_type="tshirt",
        size=size_b,
        position=position,
        color=color,
        manufacturer_id=test_manufacturer["id"],
        cost=870,
        lead_time_days=10,
        is_active=True,
    )
    db_session.add(product_a)
    db_session.add(product_b)
    await db_session.flush()
    await db_session.commit()

    yield {
        "product_a": {
            "id": product_a.id,
            "size": size_a,
        },
        "product_b": {
            "id": product_b.id,
            "size": size_b,
        },
        "manufacturer_id": test_manufacturer["id"],
        "position": position,
        "color": color,
    }


class TestProductUniqueConstraintAPI:
    """商品マスタ ユニーク制約の統合テスト"""

    @pytest.mark.asyncio
    async def test_ac007_create_duplicate_returns_409(
        self, auth_client: AsyncClient, test_product: dict[str, Any]
    ) -> None:
        """AC-007: API経由で重複作成すると409エラーレスポンスが返ること

        given: 商品マスタにテスト用の商品が存在する
        when: 同じ仕様で POST /api/v1/products を実行する
        then: 409 Conflict レスポンスが返り、エラーメッセージに重複を示す内容が含まれる
        """
        duplicate_data = {
            "product_type": test_product["product_type"],
            "size": test_product["size"],
            "position": test_product["position"],
            "color": test_product["color"],
            "manufacturer_id": test_product["manufacturer_id"],
            "cost": 900,
            "lead_time_days": 7,
        }

        response = await auth_client.post(
            f"{API_PREFIX}/products", json=duplicate_data
        )

        assert response.status_code == 409, (
            f"Expected 409 for duplicate product, "
            f"but got {response.status_code}: {response.json()}"
        )

        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == "DUPLICATE_PRODUCT"

    @pytest.mark.asyncio
    async def test_ac007_create_different_spec_succeeds(
        self, auth_client: AsyncClient, test_product: dict[str, Any]
    ) -> None:
        """異なる仕様の商品は正常に作成できること

        given: テスト用の商品が存在する
        when: 異なる size で新規作成する
        then: 201 Created が返る
        """
        new_data = {
            "product_type": test_product["product_type"],
            "size": f"DIFF-{str(uuid4())[:8]}",
            "position": test_product["position"],
            "color": test_product["color"],
            "manufacturer_id": test_product["manufacturer_id"],
            "cost": 870,
            "lead_time_days": 10,
        }

        response = await auth_client.post(
            f"{API_PREFIX}/products", json=new_data
        )

        assert response.status_code == 201, (
            f"Expected 201 for new product with different spec, "
            f"but got {response.status_code}: {response.json()}"
        )

    @pytest.mark.asyncio
    async def test_ac008_update_to_duplicate_returns_409(
        self, auth_client: AsyncClient, test_product_pair: dict[str, Any]
    ) -> None:
        """AC-008: API経由で重複更新すると409エラーレスポンスが返ること

        given:
          商品A: product_type=tshirt, size=PAIR-A-xxx
          商品B: product_type=tshirt, size=PAIR-B-xxx (同じ position/color)
        when: 商品Bの size を 商品Aと同じに更新する
        then: 409 Conflict レスポンスが返る
        """
        product_b_id = test_product_pair["product_b"]["id"]
        # 商品Aと同じsizeに更新
        update_data = {"size": test_product_pair["product_a"]["size"]}

        response = await auth_client.patch(
            f"{API_PREFIX}/products/{product_b_id}", json=update_data
        )

        assert response.status_code == 409, (
            f"Expected 409 for duplicate update, "
            f"but got {response.status_code}: {response.json()}"
        )

        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == "DUPLICATE_PRODUCT"

    @pytest.mark.asyncio
    async def test_update_self_no_conflict(
        self, auth_client: AsyncClient, test_product: dict[str, Any]
    ) -> None:
        """自分自身の仕様と同じ更新は成功すること

        given: テスト用の商品が存在する
        when: 商品の cost のみを PATCH で変更する
        then: 200 OK が返る
        """
        product_id = test_product["id"]
        update_data = {"cost": 900}

        response = await auth_client.patch(
            f"{API_PREFIX}/products/{product_id}", json=update_data
        )

        assert response.status_code == 200, (
            f"Expected 200 for self-update with no spec change, "
            f"but got {response.status_code}: {response.json()}"
        )

        data = response.json()
        assert data["cost"] == 900

    @pytest.mark.asyncio
    async def test_create_with_null_position_and_color(
        self, auth_client: AsyncClient, test_manufacturer: dict[str, Any]
    ) -> None:
        """position と color が NULL の商品を作成できること"""
        unique_size = f"NULL-TEST-{str(uuid4())[:8]}"
        new_data = {
            "product_type": "acrylic_keychain",
            "size": unique_size,
            "position": None,
            "color": None,
            "manufacturer_id": test_manufacturer["id"],
            "cost": 285,
            "lead_time_days": 10,
        }

        response = await auth_client.post(
            f"{API_PREFIX}/products", json=new_data
        )

        assert response.status_code == 201, (
            f"Expected 201 for product with null position/color, "
            f"but got {response.status_code}: {response.json()}"
        )

    @pytest.mark.asyncio
    async def test_create_duplicate_with_null_fields_returns_409(
        self, auth_client: AsyncClient, test_manufacturer: dict[str, Any], db_session: AsyncSession
    ) -> None:
        """position と color が NULL の重複商品を作成すると409が返ること"""
        # ユニークなサイズを使用
        unique_size = f"DUP-NULL-{str(uuid4())[:8]}"

        # 事前にNULLフィールドの商品を作成
        product = Product(
            id=str(uuid4()),
            product_type="acrylic_keychain",
            size=unique_size,
            position=None,
            color=None,
            manufacturer_id=test_manufacturer["id"],
            cost=350,
            lead_time_days=10,
            is_active=True,
        )
        db_session.add(product)
        await db_session.flush()
        await db_session.commit()

        # 同じ仕様（NULL含む）で作成を試みる
        duplicate_data = {
            "product_type": "acrylic_keychain",
            "size": unique_size,
            "position": None,
            "color": None,
            "manufacturer_id": test_manufacturer["id"],
            "cost": 400,
            "lead_time_days": 7,
        }

        response = await auth_client.post(
            f"{API_PREFIX}/products", json=duplicate_data
        )

        assert response.status_code == 409, (
            f"Expected 409 for duplicate product with null fields, "
            f"but got {response.status_code}: {response.json()}"
        )
