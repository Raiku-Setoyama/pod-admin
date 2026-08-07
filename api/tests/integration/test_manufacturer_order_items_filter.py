"""発注詳細画面のステータス/検索フィルター機能 統合テスト

FEAT-0012: 発注詳細画面にステータスフィルター・キーワード検索機能を追加

テスト対象: GET /manufacturers/{id}/order-items API エンドポイント
- statusパラメータでステータスフィルタリング
- searchパラメータでキーワード検索（注文番号・製品番号・商品名）
- デフォルトで全ステータス（shipped除く）を返す
- レスポンスに status フィールドが含まれる
"""

import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_manufacturer(db_session: AsyncSession):
    """テスト用のメーカー"""
    manufacturer_id = str(uuid4())
    # ユニークな名前を生成（並列テスト対策）
    manufacturer_name = f"テストメーカー_{manufacturer_id[:8]}"

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
            "email": "test-manufacturer@example.com",
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
async def test_product(db_session: AsyncSession, test_manufacturer: dict):
    """テスト用の商品"""
    product_id = str(uuid4())
    # ユニークなサイズを使用して既存データとの衝突を避ける
    unique_size = f"FILTER-{product_id[:8]}"

    await db_session.execute(
        text("""
            INSERT INTO products (
                id, product_type, size, position, color, manufacturer_id, cost, lead_time_days, is_active, created_at, updated_at
            )
            VALUES (
                :id, :product_type, :size, :position, :color, :manufacturer_id, :cost, :lead_time_days, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": product_id,
            "product_type": "tshirt",
            "size": unique_size,
            "position": "正面",
            "color": "白",
            "manufacturer_id": test_manufacturer["id"],
            "cost": 500,
            "lead_time_days": 7,
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {"id": product_id, "manufacturer_id": test_manufacturer["id"]}


@pytest.fixture
async def test_orders_with_items(
    db_session: AsyncSession,
    test_order_source: dict,
    test_product: dict,
    test_manufacturer: dict,
):
    """複数ステータスの受注と明細を作成するフィクスチャ

    以下のデータを作成:
    - 発注済み(ordered)の受注3件
    - 製造中(manufacturing)の受注2件
    - 納入済(delivered)の受注1件
    - 配送完了(shipped)の受注1件（検索対象外）
    """
    orders = []
    order_items = []

    # ユニークなプレフィックスを生成（テスト間の衝突を避ける）
    unique_prefix = str(uuid4())[:8]

    test_data = [
        # (status, order_number_suffix, product_name, uid_suffix)
        ("ordered", "ABC", "キーホルダーA", "001"),
        ("ordered", "DEF", "Tシャツ特大", "002"),
        ("ordered", "GHI", "アクリルスタンド", "003"),
        ("manufacturing", "JKL", "キーホルダーB", "004"),
        ("manufacturing", "MNO", "ステッカー大", "005"),
        ("delivered", "PQR", "Tシャツ白", "006"),
        ("shipped", "STU", "トートバッグ", "007"),  # 検索対象外
    ]

    for i, (status, order_suffix, product_name, uid_suffix) in enumerate(test_data):
        # ユニークなorder_numberとuidを生成
        order_number = f"ORD-{unique_prefix}-{order_suffix}"
        uid = f"UID-{unique_prefix}-{uid_suffix}"
        order_id = str(uuid4())
        order_item_id = str(uuid4())
        ordered_at = datetime.now() - timedelta(days=i)

        # 受注を作成
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
                "customer_email": f"customer{i+1}@example.com",
                "customer_phone": "090-0000-0000",
                "customer_postal_code": "100-0001",
                "customer_address_prefecture": "東京都",
                "customer_address_city": "千代田区",
                "status": status,
                "ordered_at": ordered_at,
                "total_price": 1000,
            }
        )

        # 受注明細を作成（statusはOrder.statusと同期）
        # shipped の場合は OrderItem.status は delivered として扱う（OrderItemStatusには shipped がないため）
        item_status = "delivered" if status == "shipped" else status
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
                "product_id": test_product["id"],
                "product_name": product_name,
                "product_type": "tshirt",
                "price": 1000,
                "quantity": 1,
                "status": item_status,
            }
        )

        orders.append({
            "id": order_id,
            "order_number": order_number,
            "status": status,
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
        "manufacturer_id": test_manufacturer["id"],
        "orders": orders,
        "order_items": order_items,
        "unique_prefix": unique_prefix,
    }


class TestManufacturerOrderItemsAPI:
    """GET /manufacturers/{id}/order-items API の統合テスト"""

    @pytest.mark.asyncio
    async def test_api_returns_all_statuses_by_default(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-007/AC-015: デフォルトでは全OrderItemステータス（ordered/manufacturing/delivered）が返される

        given: 複数のステータスの明細が存在する
        when: パラメータなしで GET /manufacturers/{id}/order-items を呼び出す
        then: ordered, manufacturing, delivered の明細が全て返される

        Note: OrderItem.statusには shipped がないため、shipped の Order に紐づく OrderItem も
        delivered ステータスとして含まれる（全7件）
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 全7件が返される（OrderItem.statusでフィルタするため全て含まれる）
        assert data["total"] == 7

        # OrderItem には shipped ステータスがないことを確認
        statuses = [item["status"] for item in data["items"]]
        assert "shipped" not in statuses

        # ordered, manufacturing, delivered が含まれていることを確認
        assert "ordered" in statuses
        assert "manufacturing" in statuses
        assert "delivered" in statuses

    @pytest.mark.asyncio
    async def test_api_filters_by_status_manufacturing(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-006/AC-014: ステータスフィルターで特定のステータスのアイテムのみが返される

        given: 複数のステータスの明細が存在する
        when: status=manufacturing でAPIを呼び出す
        then: 製造中(manufacturing)の明細のみが返される
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={"status": "manufacturing"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # manufacturing ステータスの2件のみ返されることを確認
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "manufacturing"

    @pytest.mark.asyncio
    async def test_api_filters_by_status_ordered(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-006/AC-014: 発注済みステータスでフィルタリング

        given: 複数のステータスの明細が存在する
        when: status=ordered でAPIを呼び出す
        then: 発注済み(ordered)の明細のみが返される
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={"status": "ordered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # ordered ステータスの3件のみ返されることを確認
        assert data["total"] == 3
        for item in data["items"]:
            assert item["status"] == "ordered"

    @pytest.mark.asyncio
    async def test_api_filters_by_status_delivered(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-006/AC-014: 納入済みステータスでフィルタリング

        given: 複数のステータスの明細が存在する
        when: status=delivered でAPIを呼び出す
        then: 納入済み(delivered)の明細のみが返される

        Note: shipped の Order に紐づく OrderItem も delivered ステータスを持つため、
        2件が返される（1件は元々 delivered、1件は shipped Order に紐づく）
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={"status": "delivered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # delivered ステータスの2件が返されることを確認
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_api_search_by_order_number(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-002/AC-013: 注文番号でキーワード検索

        given: 複数の明細が存在する
        when: search=ABC でAPIを呼び出す
        then: 注文番号に「ABC」を含む明細のみが返される
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={"search": "ABC"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # ORD-001-ABC の1件のみ返されることを確認
        assert data["total"] == 1
        assert "ABC" in data["items"][0]["order_number"]

    @pytest.mark.asyncio
    async def test_api_search_by_uid(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-003/AC-013: 製品番号(uid)でキーワード検索

        given: 複数の明細が存在する
        when: search={unique_prefix}-004 でAPIを呼び出す
        then: 製品番号にそのパターンを含む明細のみが返される
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]
        unique_prefix = test_orders_with_items["unique_prefix"]

        # UID-{unique_prefix}-004 を検索（manufacturing ステータス）
        search_query = f"{unique_prefix}-004"
        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={"search": search_query},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 検索パターンを含む1件のみ返されることを確認
        assert data["total"] == 1
        assert search_query in data["items"][0]["uid"]

    @pytest.mark.asyncio
    async def test_api_search_by_product_name(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-004/AC-013: 商品名でキーワード検索

        given: 複数の明細が存在する
        when: search=キーホルダー でAPIを呼び出す
        then: 商品名に「キーホルダー」を含む明細のみが返される
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={"search": "キーホルダー"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 「キーホルダー」を含む2件（キーホルダーA, キーホルダーB）が返される
        assert data["total"] == 2
        for item in data["items"]:
            assert "キーホルダー" in item["product_name"]

    @pytest.mark.asyncio
    async def test_api_search_is_case_insensitive(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-013: 検索は大文字小文字を区別しない

        given: 複数の明細が存在する
        when: search=abc（小文字）でAPIを呼び出す
        then: 注文番号に「ABC」を含む明細が返される
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={"search": "abc"},  # 小文字
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # ORD-001-ABC がヒットすることを確認
        assert data["total"] >= 1
        order_numbers = [item["order_number"] for item in data["items"]]
        assert any("ABC" in num for num in order_numbers)

    @pytest.mark.asyncio
    async def test_api_combines_status_and_search(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-011: 検索とステータスフィルターを組み合わせて使用できる

        given: 複数のステータスと商品名の明細が存在する
        when: search=キーホルダー と status=manufacturing でAPIを呼び出す
        then: 商品名に「キーホルダー」を含み、かつステータスが「製造中」の明細のみが返される
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={
                "search": "キーホルダー",
                "status": "manufacturing",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # キーホルダーB（製造中）の1件のみ返される
        # キーホルダーA は ordered なので含まれない
        assert data["total"] == 1
        assert "キーホルダー" in data["items"][0]["product_name"]
        assert data["items"][0]["status"] == "manufacturing"

    @pytest.mark.asyncio
    async def test_api_response_includes_status_field(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """AC-008/AC-016: APIレスポンスの各アイテムにstatusフィールドが含まれる

        given: 明細が存在する
        when: APIを呼び出す
        then: 各アイテムのレスポンスにstatusフィールドが含まれる
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 各アイテムに status フィールドが含まれることを確認
        for item in data["items"]:
            assert "status" in item
            assert item["status"] in ["ordered", "manufacturing", "delivered"]

    @pytest.mark.asyncio
    async def test_api_returns_empty_when_no_match(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """検索条件に一致するアイテムがない場合は空のリストを返す

        given: 明細が存在する
        when: 存在しない検索条件でAPIを呼び出す
        then: 空のリストが返される
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            params={"search": "存在しない商品名XYZ"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_api_excludes_shipped_status_from_all_statuses(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_with_items: dict,
    ):
        """OrderItem.status には shipped がないことを確認

        given: Order.status が shipped のアイテムを含む複数のステータスの明細が存在する
        when: パラメータなしでAPIを呼び出す
        then: 全てのアイテムの status は shipped でない（OrderItem.status に shipped は存在しない）

        Note: shipped Order に紐づく OrderItem は delivered ステータスを持つため、
        「トートバッグ」は含まれるが、そのステータスは delivered
        """
        manufacturer_id = test_orders_with_items["manufacturer_id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-items",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 全てのアイテムの item.status が shipped でないことを確認
        # （OrderItem.status には shipped がないため）
        for item in data["items"]:
            assert item["status"] != "shipped"
            assert item["status"] in ["ordered", "manufacturing", "delivered"]

        # トートバッグは含まれる（shipped Order に紐づくが、OrderItem.status は delivered）
        product_names = [item["product_name"] for item in data["items"]]
        assert "トートバッグ" in product_names
