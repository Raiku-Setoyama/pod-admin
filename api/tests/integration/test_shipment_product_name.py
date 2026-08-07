"""Integration tests for shipment product_name resolution.

FEAT-0014: Fix product name display in shipment detail page.
Tests the full flow through API -> Service -> Repository -> Database,
verifying that GET /shipments/{id} returns the correct product_name
from OrderItem instead of the deprecated Order.product_name.

AC-005: 配送詳細APIが正しい商品名を返す
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_product(db_session: AsyncSession):
    """テスト用の商品マスタ (order_items FK のため必要).

    既存の商品がある場合はそれを使い、なければ新規作成する。
    """
    # まず既存の商品を検索
    result = await db_session.execute(
        text("SELECT id FROM products WHERE is_active = true LIMIT 1")
    )
    existing = result.fetchone()

    if existing:
        yield {"id": existing[0]}
    else:
        # 既存商品がない場合のみ新規作成
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
                "name": f"FEAT14 Manufacturer {manufacturer_id[:8]}",
                "email": "feat14-mfg@example.com",
                "phone": "03-0014-0014",
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
                "position": "FEAT14",
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
async def shipment_with_order_items(
    db_session: AsyncSession,
    test_order_source: dict,
    test_product: dict,
):
    """配送データ: Order に OrderItem (product_name="テスト商品") が紐づくケース.

    Order.product_name は null (新しいデータ形式)。
    OrderItem.product_name = "テスト商品" が正しいソース。
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
            "order_number": f"FEAT14-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": None,  # deprecated field is NULL
            "quantity": 1,
            "customer_name": "FEAT-0014 Test Customer",
            "customer_email": "feat0014@example.com",
            "customer_phone": "090-0014-0014",
            "customer_postal_code": "100-0014",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区テスト1-1",
            "status": "delivered",
        },
    )

    # Create OrderItem with the correct product_name
    await db_session.execute(
        text("""
            INSERT INTO order_items (
                id, order_id, uid, product_id,
                product_name, product_type,
                price, quantity,
                created_at, updated_at
            )
            VALUES (
                :id, :order_id, :uid, :product_id,
                :product_name, :product_type,
                :price, :quantity,
                NOW(), NOW()
            )
        """),
        {
            "id": order_item_id,
            "order_id": order_id,
            "uid": "TEST-UID-001",
            "product_id": test_product["id"],
            "product_name": "テスト商品",
            "product_type": "acrylic_keychain",
            "price": 1500,
            "quantity": 1,
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
        "order_id": order_id,
        "order_item_id": order_item_id,
        "expected_product_name": "テスト商品",
    }


class TestShipmentProductNameAPI:
    """Integration tests for shipment product_name via API."""

    # ===========================================
    # AC-005: 配送詳細APIが正しい商品名を返す
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac005_get_shipment_returns_correct_product_name(
        self,
        client: AsyncClient,
        auth_headers: dict,
        shipment_with_order_items: dict,
    ):
        """AC-005: 配送詳細APIが正しい商品名を返す.

        Given: 配送に紐づく注文に OrderItem (product_name="テスト商品") が存在する
        When: GET /shipments/{id} を呼び出す
        Then: レスポンスの items[].product_name が "テスト商品" を含む
              ("-" ではない)
        """
        shipment_id = shipment_with_order_items["shipment_id"]

        response = await client.get(
            f"/api/v1/shipments/{shipment_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify the shipment has items
        assert len(data["items"]) > 0

        # The product_name should come from OrderItem, not from the deprecated Order.product_name
        # Order.product_name is NULL, so if the bug exists, this would be null/"-"
        product_names = [item["product_name"] for item in data["items"]]
        assert any(
            name is not None and "テスト商品" in name for name in product_names
        ), (
            f"Expected at least one item with product_name containing 'テスト商品', "
            f"but got: {product_names}"
        )

        # Explicitly verify it is NOT null (which would indicate the bug)
        for item in data["items"]:
            assert item["product_name"] is not None, (
                "product_name should not be null when OrderItem.product_name exists"
            )
            assert item["product_name"] != "-", (
                "product_name should not be '-' when OrderItem.product_name exists"
            )
