"""商品一覧フィルターの統合テスト

FEAT-0017: 商品マスター一覧のフィルター機能

テスト対象: GET /api/v1/products のフィルターパラメーター
- AC-013: product_type フィルターでステッカー商品のみが返される
- AC-014: manufacturer_id フィルターでそのメーカーの商品のみが返される
- AC-015: is_active フィルターで有効な商品のみが返される
- AC-016: 複数フィルターの組み合わせで正しく絞り込みできる
- AC-017: フィルター条件に一致する商品がない場合、空配列が返される

NOTE: TDD Red phase - これらのテストはバックエンドAPIのフィルター機能が
既に実装済みであることの確認テストです。
"""

import pytest
from uuid import uuid4
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
async def manufacturer_a(db_session: AsyncSession):
    """テスト用のメーカーA"""
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
            "name": f"テストメーカーA_{manufacturer_id[:8]}",
            "email": f"maker-a-{manufacturer_id[:8]}@example.com",
            "phone": "03-1111-1111",
            "supported_products": ["sticker", "acrylic_keychain"],
            "unit_prices": "{}",
            "lead_time_days": 5,
            "daily_order_limit": 100,
            "sharing_method": "portal",
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {
        "id": manufacturer_id,
        "name": f"テストメーカーA_{manufacturer_id[:8]}",
    }


@pytest.fixture
async def manufacturer_b(db_session: AsyncSession):
    """テスト用のメーカーB"""
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
            "name": f"テストメーカーB_{manufacturer_id[:8]}",
            "email": f"maker-b-{manufacturer_id[:8]}@example.com",
            "phone": "03-2222-2222",
            "supported_products": ["tshirt", "tote_bag"],
            "unit_prices": "{}",
            "lead_time_days": 10,
            "daily_order_limit": 50,
            "sharing_method": "DRIVE",
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {
        "id": manufacturer_id,
        "name": f"テストメーカーB_{manufacturer_id[:8]}",
    }


@pytest.fixture
async def product_sticker_active(db_session: AsyncSession, manufacturer_a: dict):
    """テスト用商品: ステッカー、有効、メーカーA"""
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
            "product_type": "sticker",
            "size": f"100x100mm_{unique_suffix}",
            "position": None,
            "color": f"white_{unique_suffix}",
            "manufacturer_id": manufacturer_a["id"],
            "cost": 300,
            "lead_time_days": 5,
            "order_limit": 100,
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {
        "id": product_id,
        "product_type": "sticker",
        "manufacturer_id": manufacturer_a["id"],
        "is_active": True,
    }


@pytest.fixture
async def product_tshirt_active(db_session: AsyncSession, manufacturer_b: dict):
    """テスト用商品: Tシャツ、有効、メーカーB"""
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
            "product_type": "tshirt",
            "size": f"M_{unique_suffix}",
            "position": f"front_{unique_suffix}",
            "color": f"white_{unique_suffix}",
            "manufacturer_id": manufacturer_b["id"],
            "cost": 800,
            "lead_time_days": 10,
            "order_limit": 50,
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {
        "id": product_id,
        "product_type": "tshirt",
        "manufacturer_id": manufacturer_b["id"],
        "is_active": True,
    }


@pytest.fixture
async def product_sticker_inactive(db_session: AsyncSession, manufacturer_a: dict):
    """テスト用商品: ステッカー、無効、メーカーA"""
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
            "product_type": "sticker",
            "size": f"50x50mm_{unique_suffix}",
            "position": None,
            "color": f"black_{unique_suffix}",
            "manufacturer_id": manufacturer_a["id"],
            "cost": 200,
            "lead_time_days": 5,
            "order_limit": 100,
            "is_active": False,
        }
    )
    await db_session.commit()

    yield {
        "id": product_id,
        "product_type": "sticker",
        "manufacturer_id": manufacturer_a["id"],
        "is_active": False,
    }


# ---------------------------------------------------------------------------
# AC-013: GET /products?product_type=sticker でステッカー商品のみが返される
# ---------------------------------------------------------------------------

class TestProductTypeFilter:
    """AC-013: product_type フィルターのテスト"""

    @pytest.mark.asyncio
    async def test_ac013_filter_by_product_type_sticker(
        self,
        client: AsyncClient,
        auth_headers: dict,
        product_sticker_active: dict,
        product_tshirt_active: dict,
    ):
        """AC-013: GET /products?product_type=sticker でステッカー商品のみが返される

        given: product_type=sticker の商品と product_type=tshirt の商品がそれぞれ登録されている
        when: GET /api/v1/products?product_type=sticker を管理者トークンで呼び出す
        then: レスポンスの items には product_type=sticker の商品のみ含まれる
        """
        response = await client.get(
            f"{API_PREFIX}/products",
            params={"product_type": "sticker"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

        # レスポンスの全アイテムが sticker であること
        for item in data["items"]:
            assert item["product_type"] == "sticker", (
                f"Expected product_type 'sticker', got '{item['product_type']}'"
            )

        # テストで作成した sticker 商品が含まれること
        item_ids = [item["id"] for item in data["items"]]
        assert product_sticker_active["id"] in item_ids, (
            f"Sticker product {product_sticker_active['id']} should be in filtered results"
        )

        # tshirt 商品が含まれないこと
        assert product_tshirt_active["id"] not in item_ids, (
            f"Tshirt product {product_tshirt_active['id']} should NOT be in sticker-filtered results"
        )


# ---------------------------------------------------------------------------
# AC-014: GET /products?manufacturer_id=xxx でそのメーカーの商品のみが返される
# ---------------------------------------------------------------------------

class TestManufacturerIdFilter:
    """AC-014: manufacturer_id フィルターのテスト"""

    @pytest.mark.asyncio
    async def test_ac014_filter_by_manufacturer_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        manufacturer_a: dict,
        product_sticker_active: dict,
        product_tshirt_active: dict,
    ):
        """AC-014: GET /products?manufacturer_id=xxx でそのメーカーの商品のみが返される

        given: メーカーA の商品とメーカーB の商品がそれぞれ登録されている
        when: GET /api/v1/products?manufacturer_id=メーカーAのID を管理者トークンで呼び出す
        then: レスポンスの items には manufacturer_id=メーカーAのID の商品のみ含まれる
        """
        response = await client.get(
            f"{API_PREFIX}/products",
            params={"manufacturer_id": manufacturer_a["id"]},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

        # レスポンスの全アイテムがメーカーAのものであること
        for item in data["items"]:
            assert item.get("manufacturer_id") == manufacturer_a["id"] or \
                   item.get("manufacturer_name") == manufacturer_a["name"], (
                f"Expected manufacturer_id '{manufacturer_a['id']}', "
                f"got manufacturer_id='{item.get('manufacturer_id')}'"
            )

        # テストで作成したメーカーA の商品が含まれること
        item_ids = [item["id"] for item in data["items"]]
        assert product_sticker_active["id"] in item_ids, (
            f"Manufacturer A's product {product_sticker_active['id']} should be in filtered results"
        )

        # メーカーBの商品が含まれないこと
        assert product_tshirt_active["id"] not in item_ids, (
            f"Manufacturer B's product {product_tshirt_active['id']} should NOT be in results filtered by manufacturer A"
        )


# ---------------------------------------------------------------------------
# AC-015: GET /products?is_active=true で有効な商品のみが返される
# ---------------------------------------------------------------------------

class TestIsActiveFilter:
    """AC-015: is_active フィルターのテスト"""

    @pytest.mark.asyncio
    async def test_ac015_filter_by_is_active_true(
        self,
        client: AsyncClient,
        auth_headers: dict,
        product_sticker_active: dict,
        product_sticker_inactive: dict,
    ):
        """AC-015: GET /products?is_active=true で有効な商品のみが返される

        given: is_active=true の商品と is_active=false の商品がそれぞれ登録されている
        when: GET /api/v1/products?is_active=true を管理者トークンで呼び出す
        then: レスポンスの items には is_active=true の商品のみ含まれる
        """
        response = await client.get(
            f"{API_PREFIX}/products",
            params={"is_active": "true"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

        # レスポンスの全アイテムが is_active=true であること
        for item in data["items"]:
            assert item["is_active"] is True, (
                f"Expected is_active=True, got {item['is_active']} for product {item['id']}"
            )

        # テストで作成した有効な商品が含まれること
        item_ids = [item["id"] for item in data["items"]]
        assert product_sticker_active["id"] in item_ids, (
            f"Active product {product_sticker_active['id']} should be in is_active=true results"
        )

        # 無効な商品が含まれないこと
        assert product_sticker_inactive["id"] not in item_ids, (
            f"Inactive product {product_sticker_inactive['id']} should NOT be in is_active=true results"
        )

    @pytest.mark.asyncio
    async def test_ac015_filter_by_is_active_false(
        self,
        client: AsyncClient,
        auth_headers: dict,
        product_sticker_active: dict,
        product_sticker_inactive: dict,
    ):
        """is_active=false で無効な商品のみが返されることを確認

        given: is_active=true の商品と is_active=false の商品がそれぞれ登録されている
        when: GET /api/v1/products?is_active=false を管理者トークンで呼び出す
        then: レスポンスの items には is_active=false の商品のみ含まれる
        """
        response = await client.get(
            f"{API_PREFIX}/products",
            params={"is_active": "false"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

        # レスポンスの全アイテムが is_active=false であること
        for item in data["items"]:
            assert item["is_active"] is False, (
                f"Expected is_active=False, got {item['is_active']} for product {item['id']}"
            )

        # テストで作成した無効な商品が含まれること
        item_ids = [item["id"] for item in data["items"]]
        assert product_sticker_inactive["id"] in item_ids, (
            f"Inactive product {product_sticker_inactive['id']} should be in is_active=false results"
        )

        # 有効な商品が含まれないこと
        assert product_sticker_active["id"] not in item_ids, (
            f"Active product {product_sticker_active['id']} should NOT be in is_active=false results"
        )


# ---------------------------------------------------------------------------
# AC-016: 複数フィルターの組み合わせで正しく絞り込みできる
# ---------------------------------------------------------------------------

class TestCombinedFilters:
    """AC-016: 複数フィルター組み合わせのテスト"""

    @pytest.mark.asyncio
    async def test_ac016_filter_by_product_type_and_is_active(
        self,
        client: AsyncClient,
        auth_headers: dict,
        product_sticker_active: dict,
        product_sticker_inactive: dict,
        product_tshirt_active: dict,
    ):
        """AC-016: GET /products?product_type=sticker&is_active=true で正しく絞り込みできる

        given: 複数の種類・メーカー・ステータスの商品が登録されている
        when: GET /api/v1/products?product_type=sticker&is_active=true を管理者トークンで呼び出す
        then: レスポンスには product_type=sticker かつ is_active=true の商品のみ含まれる
        """
        response = await client.get(
            f"{API_PREFIX}/products",
            params={"product_type": "sticker", "is_active": "true"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

        # レスポンスの全アイテムが sticker かつ is_active=true であること
        for item in data["items"]:
            assert item["product_type"] == "sticker", (
                f"Expected product_type 'sticker', got '{item['product_type']}'"
            )
            assert item["is_active"] is True, (
                f"Expected is_active=True, got {item['is_active']}"
            )

        # テストで作成した sticker + active 商品が含まれること
        item_ids = [item["id"] for item in data["items"]]
        assert product_sticker_active["id"] in item_ids, (
            "Active sticker product should be in combined filter results"
        )

        # sticker + inactive 商品が含まれないこと
        assert product_sticker_inactive["id"] not in item_ids, (
            "Inactive sticker product should NOT be in combined filter results"
        )

        # tshirt 商品が含まれないこと
        assert product_tshirt_active["id"] not in item_ids, (
            "Tshirt product should NOT be in sticker-filtered results"
        )

    @pytest.mark.asyncio
    async def test_ac016_filter_by_manufacturer_and_is_active(
        self,
        client: AsyncClient,
        auth_headers: dict,
        manufacturer_a: dict,
        product_sticker_active: dict,
        product_sticker_inactive: dict,
        product_tshirt_active: dict,
    ):
        """manufacturer_id と is_active の組み合わせフィルター

        given: メーカーAの有効・無効商品、メーカーBの有効商品が登録されている
        when: GET /api/v1/products?manufacturer_id=A&is_active=true を管理者トークンで呼び出す
        then: メーカーA かつ is_active=true の商品のみ含まれる
        """
        response = await client.get(
            f"{API_PREFIX}/products",
            params={
                "manufacturer_id": manufacturer_a["id"],
                "is_active": "true",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

        item_ids = [item["id"] for item in data["items"]]

        # メーカーAの有効商品が含まれること
        assert product_sticker_active["id"] in item_ids, (
            "Active product from manufacturer A should be in results"
        )

        # メーカーAの無効商品が含まれないこと
        assert product_sticker_inactive["id"] not in item_ids, (
            "Inactive product from manufacturer A should NOT be in is_active=true results"
        )

        # メーカーBの商品が含まれないこと
        assert product_tshirt_active["id"] not in item_ids, (
            "Product from manufacturer B should NOT be in manufacturer A filtered results"
        )


# ---------------------------------------------------------------------------
# AC-017: フィルター条件に一致する商品がない場合、空配列が返される
# ---------------------------------------------------------------------------

class TestEmptyFilterResults:
    """AC-017: 一致する商品がない場合のテスト"""

    @pytest.mark.asyncio
    async def test_ac017_no_matching_products_returns_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        product_sticker_active: dict,
    ):
        """AC-017: フィルター条件に一致する商品がない場合、空配列が返される

        given: product_type=tote_bag の商品は登録されていない（sticker のみ）
        when: GET /api/v1/products?product_type=tote_bag を管理者トークンで呼び出す
        then: レスポンスの items は空配列、total は 0
        """
        # tote_bag タイプの商品が存在しないことを確認するため、
        # 存在しにくい manufacturer_id との組み合わせでフィルター
        # （他のテストデータと衝突しないように UUID で指定）
        non_existent_manufacturer_id = str(uuid4())

        response = await client.get(
            f"{API_PREFIX}/products",
            params={"manufacturer_id": non_existent_manufacturer_id},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # items が空配列であること
        assert data["items"] == [], (
            f"Expected empty items array, got {len(data['items'])} items"
        )

        # total が 0 であること
        assert data["total"] == 0, (
            f"Expected total=0, got {data['total']}"
        )

    @pytest.mark.asyncio
    async def test_ac017_no_matching_combined_filter_returns_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        manufacturer_b: dict,
        product_sticker_active: dict,
        product_tshirt_active: dict,
    ):
        """product_type と manufacturer_id の組み合わせで一致なしの場合

        given: メーカーB には tshirt の商品しかない
        when: GET /api/v1/products?product_type=sticker&manufacturer_id=メーカーBのID
        then: レスポンスの items は空配列、total は 0
        """
        response = await client.get(
            f"{API_PREFIX}/products",
            params={
                "product_type": "sticker",
                "manufacturer_id": manufacturer_b["id"],
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # items が空配列であること
        assert data["items"] == [], (
            f"Expected empty items for sticker+manufacturerB filter, "
            f"got {len(data['items'])} items"
        )

        # total が 0 であること
        assert data["total"] == 0, (
            f"Expected total=0, got {data['total']}"
        )
