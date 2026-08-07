"""商品のメーカー名（manufacturer_name）API統合テスト

FEAT-0016: 商品マスター一覧で各商品のメーカー名が正しく表示される

テスト対象: /api/v1/products エンドポイント
- AC-001: GET /products のレスポンスに各商品の manufacturer_name フィールドが含まれる
- AC-002: GET /products/{id} のレスポンスに manufacturer_name フィールドが含まれる
- AC-003: POST /products で作成した商品のレスポンスに manufacturer_name が含まれる
- AC-004: PATCH /products/{id} で更新した商品のレスポンスに manufacturer_name が含まれる
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

# APIプレフィックス
API_PREFIX = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_manufacturer(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
    """テスト用のメーカーを作成"""
    manufacturer_id = str(uuid4())

    await db_session.execute(
        text("""
            INSERT INTO manufacturers (
                id, name, email, phone, supported_products, unit_prices,
                lead_time_days, daily_order_limit, sharing_method, is_active,
                created_at, updated_at
            )
            VALUES (
                :id, :name, :email, :phone, :supported_products, :unit_prices,
                :lead_time_days, :daily_order_limit, :sharing_method, :is_active,
                NOW(), NOW()
            )
        """),
        {
            "id": manufacturer_id,
            "name": f"テストメーカー_{manufacturer_id[:8]}",
            "email": f"test-{manufacturer_id[:8]}@example.com",
            "phone": "03-1234-5678",
            "supported_products": ["acrylic_keychain", "sticker"],
            "unit_prices": "{}",
            "lead_time_days": 7,
            "daily_order_limit": 100,
            "sharing_method": "portal",
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {
        "id": manufacturer_id,
        "name": f"テストメーカー_{manufacturer_id[:8]}",
    }


@pytest.fixture
async def test_product(db_session: AsyncSession, test_manufacturer: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """テスト用の商品を作成（メーカーに紐づく）"""
    product_id = str(uuid4())
    unique_suffix = product_id[:8]

    await db_session.execute(
        text("""
            INSERT INTO products (
                id, product_type, size, position, color,
                manufacturer_id, cost, lead_time_days, order_limit,
                is_active, created_at, updated_at
            )
            VALUES (
                :id, :product_type, :size, :position, :color,
                :manufacturer_id, :cost, :lead_time_days, :order_limit,
                :is_active, NOW(), NOW()
            )
        """),
        {
            "id": product_id,
            "product_type": "acrylic_keychain",
            "size": f"50x50mm_{unique_suffix}",
            "position": f"center_{unique_suffix}",
            "color": f"clear_{unique_suffix}",
            "manufacturer_id": test_manufacturer["id"],
            "cost": 500,
            "lead_time_days": 7,
            "order_limit": 100,
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {
        "id": product_id,
        "manufacturer_id": test_manufacturer["id"],
        "manufacturer_name": test_manufacturer["name"],
    }


# ---------------------------------------------------------------------------
# AC-001: GET /products のレスポンスに manufacturer_name が含まれる
# ---------------------------------------------------------------------------

class TestListProductsManufacturerName:
    """AC-001: 商品一覧APIのmanufacturer_nameテスト"""

    @pytest.mark.asyncio
    async def test_ac001_list_products_includes_manufacturer_name(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_product: dict[str, Any],
    ) -> None:
        """AC-001: GET /products のレスポンスに各商品の manufacturer_name フィールドが含まれる

        given: メーカーAに紐づく商品が1件以上登録されている
        when: GET /api/v1/products を管理者トークンで呼び出す
        then: レスポンスの items 配列の各要素に manufacturer_name フィールドが含まれ、
              メーカーAの名前が設定されている
        """
        response = await client.get(
            f"{API_PREFIX}/products",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1

        # テストで作成した商品を探す
        test_item = None
        for item in data["items"]:
            if item["id"] == test_product["id"]:
                test_item = item
                break

        assert test_item is not None, (
            f"Test product {test_product['id']} not found in response items"
        )

        # manufacturer_name フィールドが存在し、正しい値であること
        assert "manufacturer_name" in test_item, (
            "manufacturer_name field should be present in product response"
        )
        assert test_item["manufacturer_name"] == test_product["manufacturer_name"], (
            f"Expected manufacturer_name to be '{test_product['manufacturer_name']}', "
            f"got '{test_item['manufacturer_name']}'"
        )


# ---------------------------------------------------------------------------
# AC-002: GET /products/{id} のレスポンスに manufacturer_name が含まれる
# ---------------------------------------------------------------------------

class TestGetProductManufacturerName:
    """AC-002: 商品詳細APIのmanufacturer_nameテスト"""

    @pytest.mark.asyncio
    async def test_ac002_get_product_includes_manufacturer_name(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_product: dict[str, Any],
    ) -> None:
        """AC-002: GET /products/{id} のレスポンスに manufacturer_name フィールドが含まれる

        given: メーカーAに紐づく商品が登録されている
        when: GET /api/v1/products/{id} を管理者トークンで呼び出す
        then: レスポンスに manufacturer_name フィールドが含まれ、メーカーAの名前が設定されている
        """
        product_id = test_product["id"]

        response = await client.get(
            f"{API_PREFIX}/products/{product_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # manufacturer_name フィールドが存在し、正しい値であること
        assert "manufacturer_name" in data, (
            "manufacturer_name field should be present in product response"
        )
        assert data["manufacturer_name"] == test_product["manufacturer_name"], (
            f"Expected manufacturer_name to be '{test_product['manufacturer_name']}', "
            f"got '{data['manufacturer_name']}'"
        )


# ---------------------------------------------------------------------------
# AC-003: POST /products で作成した商品のレスポンスに manufacturer_name が含まれる
# ---------------------------------------------------------------------------

class TestCreateProductManufacturerName:
    """AC-003: 商品作成APIのmanufacturer_nameテスト"""

    @pytest.mark.asyncio
    async def test_ac003_create_product_includes_manufacturer_name(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_manufacturer: dict[str, Any],
    ) -> None:
        """AC-003: POST /products で作成した商品のレスポンスに manufacturer_name が含まれる

        given: メーカーAが存在する
        when: POST /api/v1/products でメーカーAのIDを指定して商品を作成する
        then: 201レスポンスの manufacturer_name にメーカーAの名前が設定されている
        """
        unique_suffix = str(uuid4())[:8]
        create_data = {
            "product_type": "sticker",
            "size": f"100x100mm_{unique_suffix}",
            "position": f"top_{unique_suffix}",
            "color": f"white_{unique_suffix}",
            "manufacturer_id": test_manufacturer["id"],
            "cost": 300,
            "lead_time_days": 5,
            "order_limit": 50,
        }

        response = await client.post(
            f"{API_PREFIX}/products",
            json=create_data,
            headers=auth_headers,
        )

        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.json()}"
        )

        data = response.json()

        # manufacturer_name フィールドが存在し、正しい値であること
        assert "manufacturer_name" in data, (
            "manufacturer_name field should be present in create product response"
        )
        assert data["manufacturer_name"] == test_manufacturer["name"], (
            f"Expected manufacturer_name to be '{test_manufacturer['name']}', "
            f"got '{data['manufacturer_name']}'"
        )


# ---------------------------------------------------------------------------
# AC-004: PATCH /products/{id} で更新した商品のレスポンスに manufacturer_name が含まれる
# ---------------------------------------------------------------------------

class TestUpdateProductManufacturerName:
    """AC-004: 商品更新APIのmanufacturer_nameテスト"""

    @pytest.mark.asyncio
    async def test_ac004_update_product_includes_manufacturer_name(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_product: dict[str, Any],
    ) -> None:
        """AC-004: PATCH /products/{id} で更新した商品のレスポンスに manufacturer_name が含まれる

        given: メーカーAに紐づく商品が登録されている
        when: PATCH /api/v1/products/{id} で商品を更新する
        then: レスポンスの manufacturer_name にメーカーAの名前が設定されている
        """
        product_id = test_product["id"]
        update_data = {
            "cost": 600,
        }

        response = await client.patch(
            f"{API_PREFIX}/products/{product_id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.json()}"
        )

        data = response.json()

        # manufacturer_name フィールドが存在し、正しい値であること
        assert "manufacturer_name" in data, (
            "manufacturer_name field should be present in update product response"
        )
        assert data["manufacturer_name"] == test_product["manufacturer_name"], (
            f"Expected manufacturer_name to be '{test_product['manufacturer_name']}', "
            f"got '{data['manufacturer_name']}'"
        )

        # 更新した値も正しいこと
        assert data["cost"] == 600
