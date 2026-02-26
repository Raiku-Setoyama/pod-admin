"""全メーカー横断発注明細一覧 API 統合テスト

FEAT-0018: 全メーカー分の発注明細を一覧で確認できる「すべての発注」ページ

テスト対象: GET /api/v1/manufacturers/all-order-items
- AC-006: 全メーカーの発注明細を返す
- AC-007: ステータスフィルターに対応する
- AC-008: キーワード検索に対応する
- AC-009: メーカーIDフィルターに対応する
- AC-010: 認証なしの場合401が返る
- AC-011: 発注明細が0件の場合、空配列とtotal=0が返される
"""

import json
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fixtures: テストデータ
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_manufacturer_a(db_session: AsyncSession):
    """テスト用メーカーA"""
    manufacturer_id = str(uuid4())
    manufacturer_name = f"テストメーカーA_{manufacturer_id[:8]}"

    await db_session.execute(
        text("""
            INSERT INTO manufacturers (
                id, name, email, supported_products, unit_prices, lead_time_days,
                daily_order_limit, sharing_method, is_active, created_at, updated_at
            )
            VALUES (
                :id, :name, :email, :supported_products, :unit_prices, :lead_time_days,
                :daily_order_limit, :sharing_method, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": manufacturer_id,
            "name": manufacturer_name,
            "email": f"mfr-a-{manufacturer_id[:8]}@example.com",
            "supported_products": ["tshirt", "acrylic_keychain"],
            "unit_prices": json.dumps({"tshirt": 500, "acrylic_keychain": 300}),
            "lead_time_days": 7,
            "daily_order_limit": 100,
            "sharing_method": "portal",
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {"id": manufacturer_id, "name": manufacturer_name}


@pytest.fixture
async def test_manufacturer_b(db_session: AsyncSession):
    """テスト用メーカーB"""
    manufacturer_id = str(uuid4())
    manufacturer_name = f"テストメーカーB_{manufacturer_id[:8]}"

    await db_session.execute(
        text("""
            INSERT INTO manufacturers (
                id, name, email, supported_products, unit_prices, lead_time_days,
                daily_order_limit, sharing_method, is_active, created_at, updated_at
            )
            VALUES (
                :id, :name, :email, :supported_products, :unit_prices, :lead_time_days,
                :daily_order_limit, :sharing_method, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": manufacturer_id,
            "name": manufacturer_name,
            "email": f"mfr-b-{manufacturer_id[:8]}@example.com",
            "supported_products": ["sticker"],
            "unit_prices": json.dumps({"sticker": 200}),
            "lead_time_days": 5,
            "daily_order_limit": 200,
            "sharing_method": "portal",
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {"id": manufacturer_id, "name": manufacturer_name}


@pytest.fixture
async def test_product_a(db_session: AsyncSession, test_manufacturer_a: dict):
    """テスト用商品A（メーカーA）"""
    product_id = str(uuid4())
    unique_size = f"ALL-A-{product_id[:8]}"

    await db_session.execute(
        text("""
            INSERT INTO products (
                id, product_type, size, position, color, manufacturer_id, cost,
                lead_time_days, is_active, created_at, updated_at
            )
            VALUES (
                :id, :product_type, :size, :position, :color, :manufacturer_id, :cost,
                :lead_time_days, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": product_id,
            "product_type": "tshirt",
            "size": unique_size,
            "position": "正面",
            "color": "白",
            "manufacturer_id": test_manufacturer_a["id"],
            "cost": 500,
            "lead_time_days": 7,
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {"id": product_id, "manufacturer_id": test_manufacturer_a["id"]}


@pytest.fixture
async def test_product_b(db_session: AsyncSession, test_manufacturer_b: dict):
    """テスト用商品B（メーカーB）"""
    product_id = str(uuid4())
    unique_size = f"ALL-B-{product_id[:8]}"

    await db_session.execute(
        text("""
            INSERT INTO products (
                id, product_type, size, position, color, manufacturer_id, cost,
                lead_time_days, is_active, created_at, updated_at
            )
            VALUES (
                :id, :product_type, :size, :position, :color, :manufacturer_id, :cost,
                :lead_time_days, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": product_id,
            "product_type": "sticker",
            "size": unique_size,
            "position": None,
            "color": "ホワイト",
            "manufacturer_id": test_manufacturer_b["id"],
            "cost": 200,
            "lead_time_days": 5,
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {"id": product_id, "manufacturer_id": test_manufacturer_b["id"]}


@pytest.fixture
async def test_all_orders(
    db_session: AsyncSession,
    test_order_source: dict,
    test_product_a: dict,
    test_product_b: dict,
    test_manufacturer_a: dict,
    test_manufacturer_b: dict,
):
    """複数メーカーの発注明細を作成するフィクスチャ

    以下のデータを作成:
    メーカーA:
    - ordered ステータス: 注文番号 ORD-{prefix}-AAA, 商品名 キーホルダーA
    - ordered ステータス: 注文番号 ORD-{prefix}-BBB, 商品名 Tシャツ特大
    - manufacturing ステータス: 注文番号 ORD-{prefix}-CCC, 商品名 キーホルダーB
    メーカーB:
    - ordered ステータス: 注文番号 ORD-{prefix}-DDD, 商品名 ステッカー大
    - delivered ステータス: 注文番号 ORD-{prefix}-EEE, 商品名 ステッカー小
    - shipped ステータス: 注文番号 ORD-{prefix}-FFF, 商品名 ステッカー中（除外対象）
    """
    unique_prefix = str(uuid4())[:8]

    test_data = [
        # (status, order_suffix, product_name, uid_suffix, product_id)
        ("ordered", "AAA", "キーホルダーA", "001", test_product_a["id"]),
        ("ordered", "BBB", "Tシャツ特大", "002", test_product_a["id"]),
        ("manufacturing", "CCC", "キーホルダーB", "003", test_product_a["id"]),
        ("ordered", "DDD", "ステッカー大", "004", test_product_b["id"]),
        ("delivered", "EEE", "ステッカー小", "005", test_product_b["id"]),
        ("shipped", "FFF", "ステッカー中", "006", test_product_b["id"]),
    ]

    orders = []
    order_items = []

    for i, (status, suffix, product_name, uid_suffix, product_id) in enumerate(test_data):
        order_number = f"ORD-{unique_prefix}-{suffix}"
        uid = f"UID-{unique_prefix}-{uid_suffix}"
        order_id = str(uuid4())
        order_item_id = str(uuid4())
        ordered_at = datetime.now() - timedelta(days=i)

        await db_session.execute(
            text("""
                INSERT INTO orders (
                    id, order_number, order_source_id, product_name, quantity,
                    customer_name, customer_email, customer_phone, customer_postal_code,
                    customer_address_prefecture, customer_address_city, status, ordered_at,
                    total_price, created_at, updated_at
                )
                VALUES (
                    :id, :order_number, :order_source_id, :product_name, :quantity,
                    :customer_name, :customer_email, :customer_phone, :customer_postal_code,
                    :customer_address_prefecture, :customer_address_city, :status, :ordered_at,
                    :total_price, NOW(), NOW()
                )
            """),
            {
                "id": order_id,
                "order_number": order_number,
                "order_source_id": test_order_source["id"],
                "product_name": product_name,
                "quantity": 1,
                "customer_name": f"顧客{i+1}",
                "customer_email": f"customer-all-{i+1}@example.com",
                "customer_phone": "090-0000-0000",
                "customer_postal_code": "100-0001",
                "customer_address_prefecture": "東京都",
                "customer_address_city": "千代田区",
                "status": status,
                "ordered_at": ordered_at,
                "total_price": 1000,
            }
        )

        product_type = "tshirt" if product_id == test_product_a["id"] else "sticker"
        await db_session.execute(
            text("""
                INSERT INTO order_items (
                    id, order_id, uid, product_id, product_name, product_type,
                    price, quantity, created_at, updated_at
                )
                VALUES (
                    :id, :order_id, :uid, :product_id, :product_name, :product_type,
                    :price, :quantity, NOW(), NOW()
                )
            """),
            {
                "id": order_item_id,
                "order_id": order_id,
                "uid": uid,
                "product_id": product_id,
                "product_name": product_name,
                "product_type": product_type,
                "price": 1000,
                "quantity": 1,
            }
        )

        orders.append({
            "id": order_id,
            "order_number": order_number,
            "status": status,
            "product_name": product_name,
        })
        order_items.append({
            "id": order_item_id,
            "order_id": order_id,
            "uid": uid,
            "product_name": product_name,
            "status": status,
        })

    await db_session.commit()

    yield {
        "manufacturer_a_id": test_manufacturer_a["id"],
        "manufacturer_a_name": test_manufacturer_a["name"],
        "manufacturer_b_id": test_manufacturer_b["id"],
        "manufacturer_b_name": test_manufacturer_b["name"],
        "orders": orders,
        "order_items": order_items,
        "unique_prefix": unique_prefix,
    }


# ===========================================================================
# 統合テスト
# ===========================================================================

class TestAllManufacturerOrderItemsAPI:
    """GET /manufacturers/all-order-items API の統合テスト"""

    @pytest.mark.asyncio
    async def test_api_returns_all_manufacturers_order_items(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_all_orders: dict,
    ):
        """AC-006: 全メーカーの発注明細を返す

        given: メーカーAとメーカーBに紐づく発注明細がDBに存在する
        when: GET /api/v1/manufacturers/all-order-items を管理者トークンで呼び出す
        then: ステータス200で全メーカーの発注明細一覧が返される。
              各明細にmanufacturer_nameが含まれる。
              shipped以外の5件が返される。
        """
        unique_prefix = test_all_orders["unique_prefix"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"search": unique_prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # shipped 以外の5件が返される
        assert data["total"] == 5

        # 各明細に manufacturer_id と manufacturer_name が含まれる
        for item in data["items"]:
            assert "manufacturer_id" in item
            assert "manufacturer_name" in item
            assert item["manufacturer_name"] is not None

        # 両方のメーカーの明細が含まれる
        manufacturer_names = {item["manufacturer_name"] for item in data["items"]}
        assert test_all_orders["manufacturer_a_name"] in manufacturer_names
        assert test_all_orders["manufacturer_b_name"] in manufacturer_names

        # shipped のアイテムが含まれていないことを確認
        product_names = [item["product_name"] for item in data["items"]]
        assert "ステッカー中" not in product_names

    @pytest.mark.asyncio
    async def test_api_filters_by_status_ordered(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_all_orders: dict,
    ):
        """AC-007: ステータスフィルターに対応する

        given: orderedとmanufacturingの発注明細が存在する
        when: GET /api/v1/manufacturers/all-order-items?status=ordered を呼び出す
        then: orderedステータスの明細のみが返される
        """
        unique_prefix = test_all_orders["unique_prefix"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"status": "ordered", "search": unique_prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # ordered ステータスの3件（メーカーA: 2件 + メーカーB: 1件）が返される
        assert data["total"] == 3
        for item in data["items"]:
            assert item["status"] == "ordered"

    @pytest.mark.asyncio
    async def test_api_search_by_keyword(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_all_orders: dict,
    ):
        """AC-008: キーワード検索に対応する

        given: 注文番号 "ORD-{prefix}-AAA" と "ORD-{prefix}-BBB" の発注明細が存在する
        when: GET /api/v1/manufacturers/all-order-items?search={prefix}-AAA を呼び出す
        then: 注文番号に "{prefix}-AAA" を含む明細のみが返される
        """
        unique_prefix = test_all_orders["unique_prefix"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"search": f"{unique_prefix}-AAA"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert "AAA" in data["items"][0]["order_number"]

    @pytest.mark.asyncio
    async def test_api_search_by_product_name(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_all_orders: dict,
    ):
        """AC-008: 商品名でキーワード検索

        given: 商品名に「キーホルダー」を含む明細が存在する
        when: GET /api/v1/manufacturers/all-order-items?search=キーホルダー&manufacturer_id={A} でAPIを呼び出す
        then: 商品名に「キーホルダー」を含む、メーカーAの明細のみが返される
        """
        manufacturer_a_id = test_all_orders["manufacturer_a_id"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"search": "キーホルダー", "manufacturer_id": manufacturer_a_id},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # メーカーAのキーホルダーA (ordered) + キーホルダーB (manufacturing) = 2件
        assert data["total"] == 2
        for item in data["items"]:
            assert "キーホルダー" in item["product_name"]

    @pytest.mark.asyncio
    async def test_api_filters_by_manufacturer_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_all_orders: dict,
    ):
        """AC-009: メーカーIDフィルターに対応する

        given: メーカーAとメーカーBの発注明細が存在する
        when: GET /api/v1/manufacturers/all-order-items?manufacturer_id={メーカーA.id} を呼び出す
        then: メーカーAの明細のみが返される
        """
        manufacturer_a_id = test_all_orders["manufacturer_a_id"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"manufacturer_id": manufacturer_a_id},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # メーカーAの明細のみ（ordered: 2件 + manufacturing: 1件 = 3件）
        assert data["total"] == 3
        for item in data["items"]:
            assert item["manufacturer_id"] == manufacturer_a_id

    @pytest.mark.asyncio
    async def test_api_returns_401_without_auth(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """AC-010: 認証なしの場合401が返される

        given: エンドポイントが存在する（認証ありでアクセス可能）
        when: 認証トークンなしでGET /api/v1/manufacturers/all-order-items を呼び出す
        then: ステータス401が返される
        """
        # まず認証ありでエンドポイントが存在することを確認
        # (200が返ればエンドポイントが存在する)
        auth_response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            headers=auth_headers,
        )
        assert auth_response.status_code == 200, \
            "Endpoint /api/v1/manufacturers/all-order-items should exist and return 200 with auth"

        # 認証なしでアクセス
        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_api_returns_empty_when_no_items(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """AC-011: 発注明細が0件の場合、空配列とtotal=0が返される

        given: 発注明細が存在しない（またはすべてshippedステータス）
        when: GET /api/v1/manufacturers/all-order-items を呼び出す
        then: items=[], total=0, total_quantity=0, total_amount=0 が返される

        Note: テスト固有のデータを使用するため、他のテストのデータに影響されないように
              存在しないメーカーIDでフィルターして0件を確認する
        """
        nonexistent_manufacturer_id = str(uuid4())

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"manufacturer_id": nonexistent_manufacturer_id},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["total_quantity"] == 0
        assert data["total_amount"] == 0

    @pytest.mark.asyncio
    async def test_api_combines_status_and_search_filters(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_all_orders: dict,
    ):
        """ステータスとキーワード検索を組み合わせて使用できる

        given: 複数のステータスと商品名の明細が存在する
        when: search=キーホルダー と status=ordered と manufacturer_id でAPIを呼び出す
        then: 商品名に「キーホルダー」を含み、かつステータスが ordered の明細のみが返される
        """
        manufacturer_a_id = test_all_orders["manufacturer_a_id"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={
                "search": "キーホルダー",
                "status": "ordered",
                "manufacturer_id": manufacturer_a_id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # キーホルダーA (ordered) の1件のみ
        # キーホルダーB は manufacturing なので含まれない
        assert data["total"] == 1
        assert "キーホルダー" in data["items"][0]["product_name"]
        assert data["items"][0]["status"] == "ordered"

    @pytest.mark.asyncio
    async def test_api_response_has_summary_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_all_orders: dict,
    ):
        """レスポンスに集計情報（total, total_quantity, total_amount）が含まれる

        given: 発注明細が存在する
        when: GET /api/v1/manufacturers/all-order-items を呼び出す
        then: total, total_quantity, total_amount が正しい値で返される
        """
        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "total" in data
        assert "total_quantity" in data
        assert "total_amount" in data
        assert data["total"] >= 1
        assert data["total_quantity"] >= 1
        assert data["total_amount"] >= 1
