"""注文キャンセルの明細ステータス波及 統合テスト.

注文が cancelled になると、配下の受注明細（order_items）も cancelled になり、
メーカー画面（管理側）とメーカーポータル（manufacturer-login）の双方で
「発注済み」ではなく「キャンセル済み」として見えることを検証する。
"""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.security import create_access_token


@pytest.fixture
async def cancel_manufacturer(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
    """テスト用のメーカー（ポータルログイン可能）."""
    manufacturer_id = str(uuid4())
    manufacturer_name = f"キャンセル検証メーカー_{manufacturer_id[:8]}"

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
            "email": f"cancel-mfr-{manufacturer_id[:8]}@example.com",
            "supported_products": ["tshirt"],
            "unit_prices": json.dumps({"tshirt": 500}),
            "lead_time_days": 7,
            "daily_order_limit": 100,
            "sharing_method": "portal",
            "is_active": True,
        },
    )
    await db_session.commit()

    yield {"id": manufacturer_id, "name": manufacturer_name}


@pytest.fixture
def manufacturer_headers(cancel_manufacturer: dict[str, Any]) -> dict[str, Any]:
    """メーカーポータル（manufacturer-login）用の認証ヘッダー."""
    token = create_access_token({
        "sub": cancel_manufacturer["id"],
        "type": "manufacturer",
        "manufacturer_id": cancel_manufacturer["id"],
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def cancel_product(db_session: AsyncSession, cancel_manufacturer: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """テスト用の商品（メーカー紐づけ用）."""
    product_id = str(uuid4())

    await db_session.execute(
        text("""
            INSERT INTO products (
                id, product_type, size, position, color, manufacturer_id,
                cost, lead_time_days, is_active, created_at, updated_at
            )
            VALUES (
                :id, :product_type, :size, :position, :color, :manufacturer_id,
                :cost, :lead_time_days, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": product_id,
            "product_type": "tshirt",
            "size": f"CANCEL-{product_id[:8]}",
            "position": "正面",
            "color": "白",
            "manufacturer_id": cancel_manufacturer["id"],
            "cost": 500,
            "lead_time_days": 7,
            "is_active": True,
        },
    )
    await db_session.commit()

    yield {"id": product_id}


@pytest.fixture
async def ordered_order_with_items(
    db_session: AsyncSession,
    test_order_source: dict[str, Any],
    cancel_product: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """発注済み（ordered）の注文と、その明細2件."""
    order_id = str(uuid4())
    order_number = f"CANCEL-ITEMS-{order_id[:8]}"

    await db_session.execute(
        text("""
            INSERT INTO orders (
                id, order_number, order_source_id, product_name, quantity,
                customer_name, customer_email, customer_phone, customer_postal_code,
                customer_address_prefecture, customer_address_city, status,
                ordered_at, total_price, created_at, updated_at
            )
            VALUES (
                :id, :order_number, :order_source_id, :product_name, :quantity,
                :customer_name, :customer_email, :customer_phone, :customer_postal_code,
                :customer_address_prefecture, :customer_address_city, :status,
                NOW(), :total_price, NOW(), NOW()
            )
        """),
        {
            "id": order_id,
            "order_number": order_number,
            "order_source_id": test_order_source["id"],
            "product_name": "Tシャツ",
            "quantity": 2,
            "customer_name": "キャンセル検証顧客",
            "customer_email": "cancel-items@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区1-1-1",
            "status": "ordered",
            "total_price": 2000,
        },
    )

    item_ids = [str(uuid4()), str(uuid4())]
    for item_id in item_ids:
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
                "id": item_id,
                "order_id": order_id,
                "uid": f"UID-{item_id[:8]}",
                "product_id": cancel_product["id"],
                "product_name": "Tシャツ",
                "product_type": "tshirt",
                "price": 1000,
                "quantity": 1,
                "status": "ordered",
            },
        )

    await db_session.commit()

    yield {"id": order_id, "order_number": order_number, "item_ids": item_ids}


async def fetch_item_statuses(db_session: AsyncSession, order_id: str) -> list[str]:
    """注文明細のステータスを取得する."""
    result = await db_session.execute(
        text("SELECT status FROM order_items WHERE order_id = :order_id"),
        {"order_id": order_id},
    )
    return [row[0] for row in result.fetchall()]


class TestExternalCancelPropagatesToItems:
    """外部販売サイトAPIからのキャンセルが明細まで反映されること."""

    @pytest.mark.asyncio
    async def test_items_become_cancelled(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_order_source: dict[str, Any],
        ordered_order_with_items: dict[str, Any],
    ) -> None:
        """キャンセル後、order_items.status が全て cancelled になる."""
        response = await client.post(
            f"/api/v1/external/orders/{ordered_order_with_items['order_number']}/cancel",
            headers={"X-API-Key": test_order_source["api_key"]},
        )
        assert response.status_code == 200

        statuses = await fetch_item_statuses(db_session, ordered_order_with_items["id"])
        assert statuses == ["cancelled", "cancelled"]


class TestManufacturerScreensShowCancelled:
    """メーカー画面・メーカーポータルの双方でキャンセル済みとして見えること."""

    @pytest.mark.asyncio
    async def test_admin_manufacturer_order_items_show_cancelled(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_order_source: dict[str, Any],
        cancel_manufacturer: dict[str, Any],
        ordered_order_with_items: dict[str, Any],
    ) -> None:
        """管理側のメーカー画面（発注詳細）でステータスが cancelled になる."""
        await client.post(
            f"/api/v1/external/orders/{ordered_order_with_items['order_number']}/cancel",
            headers={"X-API-Key": test_order_source["api_key"]},
        )

        response = await client.get(
            f"/api/v1/manufacturers/{cancel_manufacturer['id']}/order-items",
            headers=auth_headers,
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2
        assert {item["status"] for item in items} == {"cancelled"}

    @pytest.mark.asyncio
    async def test_manufacturer_portal_order_items_show_cancelled(
        self,
        client: AsyncClient,
        manufacturer_headers: dict[str, Any],
        test_order_source: dict[str, Any],
        ordered_order_with_items: dict[str, Any],
    ) -> None:
        """manufacturer-login 側（メーカーポータル）でもステータスが cancelled になる."""
        await client.post(
            f"/api/v1/external/orders/{ordered_order_with_items['order_number']}/cancel",
            headers={"X-API-Key": test_order_source["api_key"]},
        )

        response = await client.get(
            "/api/v1/manufacturer-portal/order-items",
            headers=manufacturer_headers,
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2
        assert {item["status"] for item in items} == {"cancelled"}

    @pytest.mark.asyncio
    async def test_cancelled_items_are_excluded_from_order_summary(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_order_source: dict[str, Any],
        cancel_manufacturer: dict[str, Any],
        ordered_order_with_items: dict[str, Any],
    ) -> None:
        """キャンセル済み明細はメーカー別発注サマリー（発注中の件数）から外れる."""
        before = await client.get(
            "/api/v1/manufacturers/order-summary", headers=auth_headers
        )
        assert before.status_code == 200
        assert any(
            s["id"] == cancel_manufacturer["id"] for s in before.json()["items"]
        )

        await client.post(
            f"/api/v1/external/orders/{ordered_order_with_items['order_number']}/cancel",
            headers={"X-API-Key": test_order_source["api_key"]},
        )

        after = await client.get(
            "/api/v1/manufacturers/order-summary", headers=auth_headers
        )
        assert after.status_code == 200
        assert not any(
            s["id"] == cancel_manufacturer["id"] for s in after.json()["items"]
        )


class TestAdminCancelPropagatesToItems:
    """管理APIからのキャンセル／キャンセル解除も明細へ反映されること."""

    @pytest.mark.asyncio
    async def test_admin_status_update_cancels_items(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict[str, Any],
        ordered_order_with_items: dict[str, Any],
    ) -> None:
        """PATCH /orders/{id}/status で cancelled にすると明細も cancelled になる."""
        response = await client.patch(
            f"/api/v1/orders/{ordered_order_with_items['id']}/status",
            headers=auth_headers,
            json={"status": "cancelled"},
        )
        assert response.status_code == 200
        # レスポンスの明細も更新後のステータスであること（古い値を返さない）
        assert {item["status"] for item in response.json()["items"]} == {"cancelled"}

        statuses = await fetch_item_statuses(db_session, ordered_order_with_items["id"])
        assert statuses == ["cancelled", "cancelled"]

    @pytest.mark.asyncio
    async def test_uncancel_restores_items(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict[str, Any],
        ordered_order_with_items: dict[str, Any],
    ) -> None:
        """キャンセルを解除すると明細が発注済みへ戻る（取り残されない）."""
        order_id = ordered_order_with_items["id"]

        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            headers=auth_headers,
            json={"status": "cancelled"},
        )
        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            headers=auth_headers,
            json={"status": "ordered"},
        )
        assert response.status_code == 200

        statuses = await fetch_item_statuses(db_session, order_id)
        assert statuses == ["ordered", "ordered"]
