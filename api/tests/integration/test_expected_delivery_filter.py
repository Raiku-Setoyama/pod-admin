"""発注一覧の納品予定日フィルター 統合テスト

納品予定日フィルターは、一覧に表示している明細の納品予定日（OrderItem.expected_delivery_date）
で絞り込む。受注日 + メーカーのリードタイムを暦日で足し直すと、営業日計算・〆切時刻で
確定した表示上の納品予定日と食い違う（9/1〜9/30 の指定で 10/2 予定の明細が出ていた）。

テスト対象:
- GET /manufacturers/all-order-items（すべての発注）
- GET /manufacturers/{id}/order-items（メーカー別の発注）
"""

import json
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

JST = timezone(timedelta(hours=9))

# (uid の末尾, 受注日時, 納品予定日)
# メーカー・商品のリードタイムは 7 日。暦日で足すと 1 件目は 9/27 になり、
# 9 月の範囲に入ってしまう（不具合の再現ケース）。
ITEMS: list[tuple[str, datetime, date]] = [
    ("OCT02", datetime(2026, 9, 20, 10, 0, tzinfo=JST), date(2026, 10, 2)),
    ("SEP30", datetime(2026, 9, 18, 10, 0, tzinfo=JST), date(2026, 9, 30)),
    ("SEP15", datetime(2026, 9, 3, 10, 0, tzinfo=JST), date(2026, 9, 15)),
    ("OCT01", datetime(2026, 9, 21, 10, 0, tzinfo=JST), date(2026, 10, 1)),
]


@pytest.fixture
async def delivery_items(
    db_session: AsyncSession,
    test_order_source: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """納品予定日の異なる明細を持つメーカー・商品・受注を作る"""
    manufacturer_id = str(uuid4())
    product_id = str(uuid4())
    prefix = f"EDF-{str(uuid4())[:8]}"

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
            "name": f"納品予定日テスト_{manufacturer_id[:8]}",
            "email": "test-manufacturer@example.com",
            "supported_products": ["tshirt"],
            "unit_prices": json.dumps({"tshirt": 500}),
            "lead_time_days": 7,
            "daily_order_limit": 100,
            "sharing_method": "portal",
            "is_active": True,
        },
    )
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
            "size": prefix,
            "position": "正面",
            "color": "白",
            "manufacturer_id": manufacturer_id,
            "cost": 500,
            "lead_time_days": 7,
            "is_active": True,
        },
    )

    for suffix, ordered_at, expected_delivery_date in ITEMS:
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
                    :id, :order_number, :order_source_id, :product_name, :quantity,
                    :customer_name, :customer_email, :customer_phone, :customer_postal_code,
                    :customer_address_prefecture, :customer_address_city, :status, :ordered_at,
                    :total_price, NOW(), NOW()
                )
            """),
            {
                "id": order_id,
                "order_number": f"ORD-{prefix}-{suffix}",
                "order_source_id": test_order_source["id"],
                "product_name": "Tシャツ",
                "quantity": 1,
                "customer_name": "顧客",
                "customer_email": "customer@example.com",
                "customer_phone": "090-0000-0000",
                "customer_postal_code": "100-0001",
                "customer_address_prefecture": "東京都",
                "customer_address_city": "千代田区",
                "status": "ordered",
                "ordered_at": ordered_at,
                "total_price": 1000,
            },
        )
        await db_session.execute(
            text("""
                INSERT INTO order_items (
                    id, order_id, uid, product_id, product_name, product_type,
                    price, quantity, status, expected_delivery_date, created_at, updated_at
                )
                VALUES (
                    :id, :order_id, :uid, :product_id, :product_name, :product_type,
                    :price, :quantity, :status, :expected_delivery_date, NOW(), NOW()
                )
            """),
            {
                "id": str(uuid4()),
                "order_id": order_id,
                "uid": f"UID-{prefix}-{suffix}",
                "product_id": product_id,
                "product_name": "Tシャツ",
                "product_type": "tshirt",
                "price": 1000,
                "quantity": 1,
                "status": "ordered",
                "expected_delivery_date": expected_delivery_date,
            },
        )

    await db_session.commit()
    yield {"manufacturer_id": manufacturer_id, "prefix": prefix}


def _suffixes(data: dict[str, Any], prefix: str) -> set[str]:
    return {item["uid"].removeprefix(f"UID-{prefix}-") for item in data["items"]}


SEPTEMBER = {"expected_delivery_from": "2026-09-01", "expected_delivery_to": "2026-09-30"}
OCTOBER = {"expected_delivery_from": "2026-10-01", "expected_delivery_to": "2026-10-31"}


class TestAllOrderItemsExpectedDeliveryFilter:
    """すべての発注（GET /manufacturers/all-order-items）"""

    @pytest.mark.asyncio
    async def test_september_range_matches_displayed_dates(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        delivery_items: dict[str, Any],
    ) -> None:
        """9/1〜9/30 の指定で、表示上の納品予定日が 9 月の明細だけが返る（10/2 は出ない）"""
        prefix = delivery_items["prefix"]
        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={**SEPTEMBER, "search": prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert _suffixes(data, prefix) == {"SEP15", "SEP30"}
        for item in data["items"]:
            assert "2026-09-01" <= item["expected_delivery_date"] <= "2026-09-30"

    @pytest.mark.asyncio
    async def test_october_range_includes_oct_2(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        delivery_items: dict[str, Any],
    ) -> None:
        """10/1〜10/31 の指定で、10/2 予定の明細が返る（受注日 + リードタイムでは 9/27）"""
        prefix = delivery_items["prefix"]
        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={**OCTOBER, "search": prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert _suffixes(response.json(), prefix) == {"OCT01", "OCT02"}

    @pytest.mark.asyncio
    async def test_single_bound_from_only(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        delivery_items: dict[str, Any],
    ) -> None:
        """開始日だけの指定でも、表示上の納品予定日で絞り込む（開始日を含む）"""
        prefix = delivery_items["prefix"]
        response = await client.get(
            "/api/v1/manufacturers/all-order-items",
            params={"expected_delivery_from": "2026-09-30", "search": prefix},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert _suffixes(response.json(), prefix) == {"SEP30", "OCT01", "OCT02"}


class TestManufacturerOrderItemsExpectedDeliveryFilter:
    """メーカー別の発注（GET /manufacturers/{id}/order-items）"""

    @pytest.mark.asyncio
    async def test_september_and_october_ranges(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        delivery_items: dict[str, Any],
    ) -> None:
        """メーカー別の一覧も、表示上の納品予定日で絞り込む"""
        prefix = delivery_items["prefix"]
        url = f"/api/v1/manufacturers/{delivery_items['manufacturer_id']}/order-items"

        september = await client.get(url, params=SEPTEMBER, headers=auth_headers)
        october = await client.get(url, params=OCTOBER, headers=auth_headers)

        assert september.status_code == 200
        assert october.status_code == 200
        assert _suffixes(september.json(), prefix) == {"SEP15", "SEP30"}
        assert _suffixes(october.json(), prefix) == {"OCT01", "OCT02"}
