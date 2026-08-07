"""Integration tests for shipment detail product view (OrderItem expansion).

FEAT-0021: Display product information per OrderItem in shipment detail page.
Tests the full flow through API -> Service -> Repository -> Database,
verifying that GET /shipments/{id} returns quantity and thumbnail_image_url
from OrderItem, and that multiple OrderItems are correctly expanded into
separate ShipmentItemResponse rows.

AC-006: GET /shipments/{id} API が quantity と thumbnail_image_url を含むレスポンスを返す
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_product_for_feat21(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
    """テスト用の商品マスタ (order_items FK のため必要).

    既存の商品がある場合はそれを使い、なければ新規作成する。
    """
    result = await db_session.execute(
        text("SELECT id FROM products WHERE is_active = true LIMIT 1")
    )
    existing = result.fetchone()

    if existing:
        yield {"id": existing[0]}
    else:
        manufacturer_id = str(uuid4())
        product_id = str(uuid4())

        await db_session.execute(
            text("""
                INSERT INTO manufacturers (
                    id, name, email, phone,
                    supported_products, unit_prices,
                    sharing_method,
                    lead_time_days, daily_order_limit, is_active,
                    created_at, updated_at
                )
                VALUES (
                    :id, :name, :email, :phone,
                    ARRAY['acrylic_keychain']::varchar[], '{}'::jsonb,
                    :sharing_method,
                    :lead_time_days, :daily_order_limit, :is_active,
                    NOW(), NOW()
                )
            """),
            {
                "id": manufacturer_id,
                "name": f"FEAT21 Manufacturer {manufacturer_id[:8]}",
                "email": "feat21-mfg@example.com",
                "phone": "03-0021-0021",
                "sharing_method": "portal",
                "lead_time_days": 7,
                "daily_order_limit": 100,
                "is_active": True,
            },
        )

        await db_session.execute(
            text("""
                INSERT INTO products (
                    id, product_type, size, position, color,
                    manufacturer_id, cost, lead_time_days, is_active,
                    created_at, updated_at
                )
                VALUES (
                    :id, :product_type, :size, :position, :color,
                    :manufacturer_id, :cost, :lead_time_days, :is_active,
                    NOW(), NOW()
                )
            """),
            {
                "id": product_id,
                "product_type": "acrylic_keychain",
                "size": "100x100mm",
                "position": "FEAT21",
                "color": None,
                "manufacturer_id": manufacturer_id,
                "cost": 500,
                "lead_time_days": 7,
                "is_active": True,
            },
        )
        await db_session.commit()

        yield {"id": product_id}


@pytest.fixture
async def shipment_with_order_items_feat21(
    db_session: AsyncSession,
    test_order_source: dict[str, Any],
    test_product_for_feat21: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """配送データ: OrderItem に quantity=5, thumbnail_image_url が設定されたケース.

    AC-006 の Given 条件:
    OrderItem（quantity=5, thumbnail_image_url="https://example.com/thumb.jpg"）
    を含む配送が存在する。
    """
    order_id = str(uuid4())
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())
    order_item_id = str(uuid4())

    # Create order with product_name = NULL (new data format)
    await db_session.execute(
        text("""
            INSERT INTO orders (
                id, order_number, order_source_id,
                product_name, quantity,
                customer_name, customer_email, customer_phone,
                customer_postal_code, customer_address_prefecture,
                customer_address_city, status, ordered_at,
                created_at, updated_at
            )
            VALUES (
                :id, :order_number, :order_source_id,
                :product_name, :quantity,
                :customer_name, :customer_email, :customer_phone,
                :customer_postal_code, :customer_address_prefecture,
                :customer_address_city, :status, NOW(),
                NOW(), NOW()
            )
        """),
        {
            "id": order_id,
            "order_number": f"FEAT21-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": None,
            "quantity": 1,
            "customer_name": "FEAT-0021 Test Customer",
            "customer_email": "feat0021@example.com",
            "customer_phone": "090-0021-0021",
            "customer_postal_code": "100-0021",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区テスト21-1",
            "status": "delivered",
        },
    )

    # Create OrderItem with quantity=5 and thumbnail_image_url
    await db_session.execute(
        text("""
            INSERT INTO order_items (
                id, order_id, uid, product_id,
                product_name, product_type,
                price, quantity,
                thumbnail_image_url,
                created_at, updated_at
            )
            VALUES (
                :id, :order_id, :uid, :product_id,
                :product_name, :product_type,
                :price, :quantity,
                :thumbnail_image_url,
                NOW(), NOW()
            )
        """),
        {
            "id": order_item_id,
            "order_id": order_id,
            "uid": "FEAT21-UID-001",
            "product_id": test_product_for_feat21["id"],
            "product_name": "アクリルキーホルダーA",
            "product_type": "acrylic_keychain",
            "price": 1500,
            "quantity": 5,
            "thumbnail_image_url": "https://example.com/thumb.jpg",
        },
    )

    # Create shipment
    await db_session.execute(
        text("""
            INSERT INTO shipments (id, status, created_at, updated_at)
            VALUES (:id, :status, NOW(), NOW())
        """),
        {"id": shipment_id, "status": "pending"},
    )

    # Create shipment item linking shipment to order
    await db_session.execute(
        text("""
            INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
            VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
        """),
        {
            "id": shipment_item_id,
            "shipment_id": shipment_id,
            "order_id": order_id,
        },
    )

    await db_session.commit()

    yield {
        "shipment_id": shipment_id,
        "shipment_item_id": shipment_item_id,
        "order_id": order_id,
        "order_item_id": order_item_id,
        "expected_quantity": 5,
        "expected_thumbnail_image_url": "https://example.com/thumb.jpg",
        "expected_product_name": "アクリルキーホルダーA",
    }


@pytest.fixture
async def shipment_with_multiple_order_items_feat21(
    db_session: AsyncSession,
    test_order_source: dict[str, Any],
    test_product_for_feat21: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """配送データ: 1つの注文に複数の OrderItem が紐づくケース.

    OrderItem 単位で ShipmentItemResponse が展開されることを検証する。
    """
    order_id = str(uuid4())
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())
    order_item_id_1 = str(uuid4())
    order_item_id_2 = str(uuid4())
    order_item_id_3 = str(uuid4())

    # Create order
    await db_session.execute(
        text("""
            INSERT INTO orders (
                id, order_number, order_source_id,
                product_name, quantity,
                customer_name, customer_email, customer_phone,
                customer_postal_code, customer_address_prefecture,
                customer_address_city, status, ordered_at,
                created_at, updated_at
            )
            VALUES (
                :id, :order_number, :order_source_id,
                :product_name, :quantity,
                :customer_name, :customer_email, :customer_phone,
                :customer_postal_code, :customer_address_prefecture,
                :customer_address_city, :status, NOW(),
                NOW(), NOW()
            )
        """),
        {
            "id": order_id,
            "order_number": f"FEAT21M-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": None,
            "quantity": 1,
            "customer_name": "FEAT-0021 Multi Customer",
            "customer_email": "feat0021multi@example.com",
            "customer_phone": "090-0021-0022",
            "customer_postal_code": "100-0021",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区テスト21-2",
            "status": "delivered",
        },
    )

    # Create 3 OrderItems with different quantities and thumbnail_image_url
    order_items_data = [
        {
            "id": order_item_id_1,
            "uid": "FEAT21M-UID-001",
            "product_name": "商品A",
            "quantity": 2,
            "thumbnail_image_url": "https://example.com/a.jpg",
        },
        {
            "id": order_item_id_2,
            "uid": "FEAT21M-UID-002",
            "product_name": "商品B",
            "quantity": 1,
            "thumbnail_image_url": None,
        },
        {
            "id": order_item_id_3,
            "uid": "FEAT21M-UID-003",
            "product_name": "商品C",
            "quantity": 3,
            "thumbnail_image_url": "https://example.com/c.jpg",
        },
    ]

    for item_data in order_items_data:
        await db_session.execute(
            text("""
                INSERT INTO order_items (
                    id, order_id, uid, product_id,
                    product_name, product_type,
                    price, quantity,
                    thumbnail_image_url,
                    created_at, updated_at
                )
                VALUES (
                    :id, :order_id, :uid, :product_id,
                    :product_name, :product_type,
                    :price, :quantity,
                    :thumbnail_image_url,
                    NOW(), NOW()
                )
            """),
            {
                "id": item_data["id"],
                "order_id": order_id,
                "uid": item_data["uid"],
                "product_id": test_product_for_feat21["id"],
                "product_name": item_data["product_name"],
                "product_type": "acrylic_keychain",
                "price": 1500,
                "quantity": item_data["quantity"],
                "thumbnail_image_url": item_data["thumbnail_image_url"],
            },
        )

    # Create shipment
    await db_session.execute(
        text("""
            INSERT INTO shipments (id, status, created_at, updated_at)
            VALUES (:id, :status, NOW(), NOW())
        """),
        {"id": shipment_id, "status": "pending"},
    )

    # Create shipment item
    await db_session.execute(
        text("""
            INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
            VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
        """),
        {
            "id": shipment_item_id,
            "shipment_id": shipment_id,
            "order_id": order_id,
        },
    )

    await db_session.commit()

    yield {
        "shipment_id": shipment_id,
        "shipment_item_id": shipment_item_id,
        "order_id": order_id,
        "order_items": order_items_data,
    }


class TestShipmentDetailProductViewAPI:
    """Integration tests for shipment detail product view via API.

    FEAT-0021: OrderItem 単位の quantity, thumbnail_image_url が
    GET /shipments/{id} レスポンスに含まれることを検証する。
    """

    # ===========================================
    # AC-006: GET /shipments/{id} API が quantity と
    #         thumbnail_image_url を含むレスポンスを返す
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac006_get_shipment_returns_quantity_and_thumbnail(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        shipment_with_order_items_feat21: dict[str, Any],
    ) -> None:
        """AC-006: GET /shipments/{id} が quantity と thumbnail_image_url を返す.

        Given: OrderItem（quantity=5, thumbnail_image_url="https://example.com/thumb.jpg"）
               を含む配送が存在する
        When: GET /shipments/{id} を呼び出す
        Then: レスポンスの items 内に quantity=5,
              thumbnail_image_url="https://example.com/thumb.jpg" が含まれる
        """
        fixture = shipment_with_order_items_feat21
        shipment_id = fixture["shipment_id"]

        response = await client.get(
            f"/api/v1/shipments/{shipment_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify items exist
        assert len(data["items"]) > 0

        # Find the item corresponding to our OrderItem
        matching_items = [
            item for item in data["items"]
            if item["product_name"] == fixture["expected_product_name"]
        ]
        assert len(matching_items) == 1, (
            f"Expected exactly 1 item with product_name='{fixture['expected_product_name']}', "
            f"but got {len(matching_items)}: {[i['product_name'] for i in data['items']]}"
        )

        item = matching_items[0]

        # AC-006: quantity フィールドが正しい値を返す
        assert item["quantity"] == fixture["expected_quantity"], (
            f"Expected quantity={fixture['expected_quantity']}, "
            f"but got quantity={item['quantity']}"
        )

        # AC-006: thumbnail_image_url フィールドが正しい値を返す
        assert item["thumbnail_image_url"] == fixture["expected_thumbnail_image_url"], (
            f"Expected thumbnail_image_url='{fixture['expected_thumbnail_image_url']}', "
            f"but got thumbnail_image_url='{item['thumbnail_image_url']}'"
        )

    @pytest.mark.asyncio
    async def test_ac006_multiple_order_items_expanded_in_response(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        shipment_with_multiple_order_items_feat21: dict[str, Any],
    ) -> None:
        """AC-006 (補足): 複数 OrderItem が各行に展開され、quantity/thumbnail が正しい.

        Given: 1つの注文に 3つの OrderItem が紐づく配送がある
               - 商品A: quantity=2, thumbnail_image_url="https://example.com/a.jpg"
               - 商品B: quantity=1, thumbnail_image_url=null
               - 商品C: quantity=3, thumbnail_image_url="https://example.com/c.jpg"
        When: GET /shipments/{id} を呼び出す
        Then: items に 3つの要素が含まれ、各 quantity, thumbnail_image_url が正しい
        """
        fixture = shipment_with_multiple_order_items_feat21
        shipment_id = fixture["shipment_id"]

        response = await client.get(
            f"/api/v1/shipments/{shipment_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 3つの OrderItem が展開されている
        assert len(data["items"]) == 3, (
            f"Expected 3 items (one per OrderItem), but got {len(data['items'])}"
        )

        # 各アイテムの検証 (product_name でマッチング)
        items_by_name = {item["product_name"]: item for item in data["items"]}

        # 商品A: quantity=2, thumbnail_image_url="https://example.com/a.jpg"
        assert "商品A" in items_by_name, f"Missing '商品A' in items: {list(items_by_name.keys())}"
        assert items_by_name["商品A"]["quantity"] == 2
        assert items_by_name["商品A"]["thumbnail_image_url"] == "https://example.com/a.jpg"

        # 商品B: quantity=1, thumbnail_image_url=null
        assert "商品B" in items_by_name, f"Missing '商品B' in items: {list(items_by_name.keys())}"
        assert items_by_name["商品B"]["quantity"] == 1
        assert items_by_name["商品B"]["thumbnail_image_url"] is None

        # 商品C: quantity=3, thumbnail_image_url="https://example.com/c.jpg"
        assert "商品C" in items_by_name, f"Missing '商品C' in items: {list(items_by_name.keys())}"
        assert items_by_name["商品C"]["quantity"] == 3
        assert items_by_name["商品C"]["thumbnail_image_url"] == "https://example.com/c.jpg"

    @pytest.mark.asyncio
    async def test_ac006_composite_id_format_in_response(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        shipment_with_order_items_feat21: dict[str, Any],
    ) -> None:
        """AC-006 (補足): レスポンスの items[].id が複合ID形式.

        Given: ShipmentItem と OrderItem が紐づく配送がある
        When: GET /shipments/{id} を呼び出す
        Then: items[].id が "{shipment_item_id}_{order_item_id}" 形式
        """
        fixture = shipment_with_order_items_feat21
        shipment_id = fixture["shipment_id"]

        response = await client.get(
            f"/api/v1/shipments/{shipment_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 1
        item = data["items"][0]

        # 複合ID: {shipment_item_id}_{order_item_id}
        expected_id = f"{fixture['shipment_item_id']}_{fixture['order_item_id']}"
        assert item["id"] == expected_id, (
            f"Expected composite id='{expected_id}', but got id='{item['id']}'"
        )

    @pytest.mark.asyncio
    async def test_ac006_null_thumbnail_image_url_in_response(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        shipment_with_multiple_order_items_feat21: dict[str, Any],
    ) -> None:
        """AC-006 (補足): thumbnail_image_url が null の場合、null が返る.

        Given: thumbnail_image_url=null の OrderItem を含む配送がある
        When: GET /shipments/{id} を呼び出す
        Then: レスポンスの items 内で thumbnail_image_url が null
        """
        fixture = shipment_with_multiple_order_items_feat21
        shipment_id = fixture["shipment_id"]

        response = await client.get(
            f"/api/v1/shipments/{shipment_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 商品B は thumbnail_image_url=null
        items_by_name = {item["product_name"]: item for item in data["items"]}
        assert "商品B" in items_by_name
        assert items_by_name["商品B"]["thumbnail_image_url"] is None
