"""全メーカー横断発注明細一覧 API 統合テスト

FEAT-0018: 全メーカー分の発注明細を一覧で確認できる「すべての発注」ページ

テスト対象: GET /api/v1/manufacturers/all-order-items
- AC-006: 全メーカーの発注明細を返す
- AC-007: ステータスフィルターに対応する
- AC-008: キーワード検索に対応する
- AC-009: メーカーIDフィルターに対応する
- AC-010: 認証なしの場合401が返る
- AC-011: 発注明細が0件の場合、空配列とtotal=0が返される

REQ-0065: 明細単位のステータスで表示・絞り込みし、発送完了後の明細も残す
"""

import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Fixtures: テストデータ
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_manufacturer_a(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
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
async def test_manufacturer_b(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
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
async def test_product_a(db_session: AsyncSession, test_manufacturer_a: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
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
async def test_product_b(db_session: AsyncSession, test_manufacturer_b: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
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
    test_order_source: dict[str, Any],
    test_product_a: dict[str, Any],
    test_product_b: dict[str, Any],
    test_manufacturer_a: dict[str, Any],
    test_manufacturer_b: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """複数メーカーの発注明細を作成するフィクスチャ

    以下のデータを作成（注文ステータス / 明細ステータス）:
    メーカーA:
    - ordered / ordered: 注文番号 ORD-{prefix}-AAA, 商品名 キーホルダーA
    - ordered / ordered: 注文番号 ORD-{prefix}-BBB, 商品名 Tシャツ特大
    - manufacturing / manufacturing: 注文番号 ORD-{prefix}-CCC, 商品名 キーホルダーB
    メーカーB:
    - ordered / ordered: 注文番号 ORD-{prefix}-DDD, 商品名 ステッカー大
    - delivered / delivered: 注文番号 ORD-{prefix}-EEE, 商品名 ステッカー小
    - shipped / delivered: 注文番号 ORD-{prefix}-FFF, 商品名 ステッカー中
      （明細は shipped を取らない。発送完了後も納入済みの明細として残る）
    """
    unique_prefix = str(uuid4())[:8]

    test_data = [
        # (order_status, item_status, order_suffix, product_name, uid_suffix, product_id)
        ("ordered", "ordered", "AAA", "キーホルダーA", "001", test_product_a["id"]),
        ("ordered", "ordered", "BBB", "Tシャツ特大", "002", test_product_a["id"]),
        ("manufacturing", "manufacturing", "CCC", "キーホルダーB", "003", test_product_a["id"]),
        ("ordered", "ordered", "DDD", "ステッカー大", "004", test_product_b["id"]),
        ("delivered", "delivered", "EEE", "ステッカー小", "005", test_product_b["id"]),
        ("shipped", "delivered", "FFF", "ステッカー中", "006", test_product_b["id"]),
    ]

    orders = []
    order_items = []

    for i, (status, item_status, suffix, product_name, uid_suffix, product_id) in enumerate(test_data):
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
                    price, quantity, status, created_at, updated_at
                )
                VALUES (
                    :id, :order_id, :uid, :product_id, :product_name, :product_type,
                    :price, :quantity, :status, NOW(), NOW()
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
                "status": item_status,
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
            "status": item_status,
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
        auth_headers: dict[str, Any],
        test_all_orders: dict[str, Any],
    ) -> None:
        """AC-006: 全メーカーの発注明細を返す

        given: メーカーAとメーカーBに紐づく発注明細がDBに存在する
        when: GET /api/v1/manufacturers/all-order-items を管理者トークンで呼び出す
        then: ステータス200で全メーカーの発注明細一覧が返される。
              各明細にmanufacturer_nameが含まれる。
              REQ-0065: 発送完了になった注文の明細も除外されず、6件すべてが返される。
        """
        unique_prefix = test_all_orders["unique_prefix"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"search": unique_prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 発送完了の注文の明細も含めた6件が返される
        assert data["total"] == 6

        # 各明細に manufacturer_id と manufacturer_name が含まれる
        for item in data["items"]:
            assert "manufacturer_id" in item
            assert "manufacturer_name" in item
            assert item["manufacturer_name"] is not None

        # 両方のメーカーの明細が含まれる
        manufacturer_names = {item["manufacturer_name"] for item in data["items"]}
        assert test_all_orders["manufacturer_a_name"] in manufacturer_names
        assert test_all_orders["manufacturer_b_name"] in manufacturer_names

        # 発送完了になった注文の明細も、納入済みの明細として含まれる
        by_name = {item["product_name"]: item for item in data["items"]}
        assert "ステッカー中" in by_name
        assert by_name["ステッカー中"]["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_api_filters_by_status_ordered(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_all_orders: dict[str, Any],
    ) -> None:
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
        auth_headers: dict[str, Any],
        test_all_orders: dict[str, Any],
    ) -> None:
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
        auth_headers: dict[str, Any],
        test_all_orders: dict[str, Any],
    ) -> None:
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
        auth_headers: dict[str, Any],
        test_all_orders: dict[str, Any],
    ) -> None:
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
        auth_headers: dict[str, Any],
    ) -> None:
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
        auth_headers: dict[str, Any],
    ) -> None:
        """AC-011: 発注明細が0件の場合、空配列とtotal=0が返される

        given: 発注明細が存在しない
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
        auth_headers: dict[str, Any],
        test_all_orders: dict[str, Any],
    ) -> None:
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
        auth_headers: dict[str, Any],
        test_all_orders: dict[str, Any],
    ) -> None:
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


# ===========================================================================
# REQ-0065: 明細単位のステータスで表示・絞り込みする
# ===========================================================================

@pytest.fixture
async def test_mixed_manufacturer_order(
    db_session: AsyncSession,
    test_order_source: dict[str, Any],
    test_product_a: dict[str, Any],
    test_product_b: dict[str, Any],
    test_manufacturer_a: dict[str, Any],
    test_manufacturer_b: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """2 メーカーにまたがる 1 注文を作るフィクスチャ

    メーカーA の明細は納入済み、メーカーB の明細は製造中。
    注文ステータスは導出ルール（1つでも manufacturing があれば manufacturing）に従い
    manufacturing になる。明細単位で見れば A は納入済みである。
    """
    unique_prefix = str(uuid4())[:8]
    order_id = str(uuid4())
    order_number = f"ORD-{unique_prefix}-MIXED"

    await db_session.execute(
        text("""
            INSERT INTO orders (
                id, order_number, order_source_id, product_name, quantity,
                customer_name, customer_email, customer_phone, customer_postal_code,
                customer_address_prefecture, customer_address_city, status, ordered_at,
                total_price, created_at, updated_at
            )
            VALUES (
                :id, :order_number, :order_source_id, 'まとめ買い', 2,
                '顧客M', 'customer-mixed@example.com', '090-0000-0000', '100-0001',
                '東京都', '千代田区', 'manufacturing', :ordered_at, 2000, NOW(), NOW()
            )
        """),
        {
            "id": order_id,
            "order_number": order_number,
            "order_source_id": test_order_source["id"],
            "ordered_at": datetime.now(),
        }
    )

    items = [
        # (product_id, product_type, uid_suffix, item_status)
        (test_product_a["id"], "tshirt", "A", "delivered"),
        (test_product_b["id"], "sticker", "B", "manufacturing"),
    ]
    for product_id, product_type, uid_suffix, item_status in items:
        await db_session.execute(
            text("""
                INSERT INTO order_items (
                    id, order_id, uid, product_id, product_name, product_type,
                    price, quantity, status, created_at, updated_at
                )
                VALUES (
                    :id, :order_id, :uid, :product_id, :product_name, :product_type,
                    1000, 1, :status, NOW(), NOW()
                )
            """),
            {
                "id": str(uuid4()),
                "order_id": order_id,
                "uid": f"UID-{unique_prefix}-{uid_suffix}",
                "product_id": product_id,
                "product_name": f"まとめ買い商品{uid_suffix}",
                "product_type": product_type,
                "status": item_status,
            }
        )

    await db_session.commit()

    yield {
        "unique_prefix": unique_prefix,
        "order_number": order_number,
        "manufacturer_a_id": test_manufacturer_a["id"],
        "manufacturer_b_id": test_manufacturer_b["id"],
    }


class TestAllManufacturerOrderItemsUsesItemStatus:
    """REQ-0065: 一覧・絞り込みが明細単位のステータスで行われる"""

    @pytest.mark.asyncio
    async def test_shipped_order_items_remain_as_delivered(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_all_orders: dict[str, Any],
    ) -> None:
        """受入基準 1・3: 発送完了になった注文の明細が「納品済」で絞り込める

        given: 注文が発送完了になり、その明細は納入済みのまま残っている
        when: status=delivered で絞り込む
        then: 発送完了になった注文の明細も返される
        """
        unique_prefix = test_all_orders["unique_prefix"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"status": "delivered", "search": unique_prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # ステッカー小（注文 delivered）とステッカー中（注文 shipped）の 2 件
        product_names = {item["product_name"] for item in data["items"]}
        assert product_names == {"ステッカー小", "ステッカー中"}
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_item_status_is_returned_per_item(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_mixed_manufacturer_order: dict[str, Any],
    ) -> None:
        """受入基準 2: 注文ではなく明細のステータスが返る

        given: 1 注文の中にメーカーAの納入済み明細とメーカーBの製造中明細がある
               （注文ステータスは manufacturing）
        when: 絞り込みなしで一覧を取得する
        then: 明細ごとに delivered / manufacturing が返る
        """
        unique_prefix = test_mixed_manufacturer_order["unique_prefix"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"search": unique_prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        statuses = {item["uid"]: item["status"] for item in data["items"]}
        assert statuses == {
            f"UID-{unique_prefix}-A": "delivered",
            f"UID-{unique_prefix}-B": "manufacturing",
        }

    @pytest.mark.asyncio
    async def test_filters_mixed_order_by_item_status(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_mixed_manufacturer_order: dict[str, Any],
    ) -> None:
        """受入基準 4: 複数メーカーにまたがる注文で、明細ごとに独立して絞り込める

        given: 注文ステータスが manufacturing の注文に、納入済みの明細が含まれる
        when: status=delivered で絞り込む
        then: その納入済み明細だけが返る（注文ステータスでは弾かれない）
        """
        unique_prefix = test_mixed_manufacturer_order["unique_prefix"]

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"status": "delivered", "search": unique_prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["uid"] == f"UID-{unique_prefix}-A"
        assert data["items"][0]["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_filters_cancelled_items(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        db_session: AsyncSession,
        test_order_source: dict[str, Any],
        test_product_a: dict[str, Any],
    ) -> None:
        """受入基準 3: キャンセル済みの明細が「キャンセル済」で絞り込める

        given: キャンセルされた注文と、その明細（キャンセル済み）がある
        when: status=cancelled で絞り込む
        then: その明細が返る
        """
        unique_prefix = str(uuid4())[:8]
        order_id = str(uuid4())

        await db_session.execute(
            text("""
                INSERT INTO orders (
                    id, order_number, order_source_id, product_name, quantity,
                    customer_name, customer_email, customer_phone, customer_postal_code,
                    customer_address_prefecture, customer_address_city, status, ordered_at,
                    total_price, created_at, updated_at
                )
                VALUES (
                    :id, :order_number, :order_source_id, 'キャンセル品', 1,
                    '顧客C', 'customer-cancel@example.com', '090-0000-0000', '100-0001',
                    '東京都', '千代田区', 'cancelled', :ordered_at, 1000, NOW(), NOW()
                )
            """),
            {
                "id": order_id,
                "order_number": f"ORD-{unique_prefix}-CANCEL",
                "order_source_id": test_order_source["id"],
                "ordered_at": datetime.now(),
            }
        )
        await db_session.execute(
            text("""
                INSERT INTO order_items (
                    id, order_id, uid, product_id, product_name, product_type,
                    price, quantity, status, created_at, updated_at
                )
                VALUES (
                    :id, :order_id, :uid, :product_id, 'キャンセル品', 'tshirt',
                    1000, 1, 'cancelled', NOW(), NOW()
                )
            """),
            {
                "id": str(uuid4()),
                "order_id": order_id,
                "uid": f"UID-{unique_prefix}-X",
                "product_id": test_product_a["id"],
            }
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"status": "cancelled", "search": unique_prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["status"] == "cancelled"
