"""Integration tests for external order cancellation API.

FEAT-0023: POST /api/v1/external/orders/{order_number}/cancel
Tests the full flow through API -> Service -> Repository -> Database.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
async def api_key_headers(db_session: AsyncSession):
    """Create an order source with API key and return headers for authenticated requests."""
    source_id = str(uuid4())
    api_key = f"test-cancel-api-key-{source_id}"
    source_code = f"CAN{source_id[:8].upper()}"

    await db_session.execute(
        text("""
            INSERT INTO order_sources (
                id, code, name, api_key, phone, postal_code,
                address_prefecture, address_city, is_active,
                created_at, updated_at
            )
            VALUES (
                :id, :code, :name, :api_key, :phone, :postal_code,
                :address_prefecture, :address_city, :is_active,
                NOW(), NOW()
            )
        """),
        {
            "id": source_id,
            "code": source_code,
            "name": "Test Cancel Source",
            "api_key": api_key,
            "phone": "090-1234-5678",
            "postal_code": "100-0001",
            "address_prefecture": "東京都",
            "address_city": "千代田区",
            "is_active": True,
        },
    )
    await db_session.commit()

    yield {"X-API-Key": api_key, "_source_id": source_id}


@pytest.fixture
async def ordered_order(db_session: AsyncSession, api_key_headers: dict):
    """Create a test order in 'ordered' status."""
    order_id = str(uuid4())
    order_number = f"CANCEL-ORD-{order_id[:8]}"
    source_id = api_key_headers["_source_id"]

    await db_session.execute(
        text("""
            INSERT INTO orders (
                id, order_number, order_source_id, product_name, quantity,
                customer_name, customer_email, customer_phone,
                customer_postal_code, customer_address_prefecture,
                customer_address_city, status, ordered_at, created_at, updated_at
            )
            VALUES (
                :id, :order_number, :order_source_id, :product_name, :quantity,
                :customer_name, :customer_email, :customer_phone,
                :customer_postal_code, :customer_address_prefecture,
                :customer_address_city, :status, NOW(), NOW(), NOW()
            )
        """),
        {
            "id": order_id,
            "order_number": order_number,
            "order_source_id": source_id,
            "product_name": "Cancel Test Product",
            "quantity": 1,
            "customer_name": "Cancel Test Customer",
            "customer_email": "cancel-test@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区1-1-1",
            "status": "ordered",
        },
    )
    await db_session.commit()

    yield {"id": order_id, "order_number": order_number}


@pytest.fixture
async def manufacturing_order(db_session: AsyncSession, api_key_headers: dict):
    """Create a test order in 'manufacturing' status."""
    order_id = str(uuid4())
    order_number = f"CANCEL-MFG-{order_id[:8]}"
    source_id = api_key_headers["_source_id"]

    await db_session.execute(
        text("""
            INSERT INTO orders (
                id, order_number, order_source_id, product_name, quantity,
                customer_name, customer_email, customer_phone,
                customer_postal_code, customer_address_prefecture,
                customer_address_city, status, ordered_at, created_at, updated_at
            )
            VALUES (
                :id, :order_number, :order_source_id, :product_name, :quantity,
                :customer_name, :customer_email, :customer_phone,
                :customer_postal_code, :customer_address_prefecture,
                :customer_address_city, :status, NOW(), NOW(), NOW()
            )
        """),
        {
            "id": order_id,
            "order_number": order_number,
            "order_source_id": source_id,
            "product_name": "Manufacturing Test Product",
            "quantity": 1,
            "customer_name": "MFG Test Customer",
            "customer_email": "mfg-test@example.com",
            "customer_phone": "090-0000-0001",
            "customer_postal_code": "100-0002",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区2-2-2",
            "status": "manufacturing",
        },
    )
    await db_session.commit()

    yield {"id": order_id, "order_number": order_number}


# ============================================================
# AC-008: 正常系 - API 200 OK + DB更新確認
# ============================================================


class TestCancelOrderAPI:
    """Integration tests for the cancel order endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_ordered_order_returns_200(
        self,
        client: AsyncClient,
        api_key_headers: dict,
        ordered_order: dict,
        db_session: AsyncSession,
    ):
        """AC-008: POST /api/v1/external/orders/{order_number}/cancel が 200 を返す."""
        order_number = ordered_order["order_number"]
        headers = {"X-API-Key": api_key_headers["X-API-Key"]}

        response = await client.post(
            f"/api/v1/external/orders/{order_number}/cancel",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["order_number"] == order_number
        assert data["status"] == "cancelled"
        assert "cancelled_at" in data

    @pytest.mark.asyncio
    async def test_cancel_ordered_order_updates_db(
        self,
        client: AsyncClient,
        api_key_headers: dict,
        ordered_order: dict,
        db_session: AsyncSession,
    ):
        """AC-008: キャンセル後、DBの注文ステータスが cancelled に更新されている."""
        order_number = ordered_order["order_number"]
        order_id = ordered_order["id"]
        headers = {"X-API-Key": api_key_headers["X-API-Key"]}

        await client.post(
            f"/api/v1/external/orders/{order_number}/cancel",
            headers=headers,
        )

        # Verify DB is updated
        result = await db_session.execute(
            text("SELECT status FROM orders WHERE id = :id"),
            {"id": order_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "cancelled"


# ============================================================
# AC-009: 存在しない注文 -> 404
# ============================================================


class TestCancelOrderNotFoundAPI:
    """Integration tests for cancelling non-existent orders."""

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order_returns_404(
        self,
        client: AsyncClient,
        api_key_headers: dict,
    ):
        """AC-009: 存在しない order_number で 404 が返される."""
        headers = {"X-API-Key": api_key_headers["X-API-Key"]}

        response = await client.post(
            "/api/v1/external/orders/NONEXISTENT-ORDER-999/cancel",
            headers=headers,
        )

        assert response.status_code == 404


# ============================================================
# AC-010: ordered 以外 -> 409
# ============================================================


class TestCancelOrderConflictAPI:
    """Integration tests for cancelling orders with invalid status."""

    @pytest.mark.asyncio
    async def test_cancel_manufacturing_order_returns_409(
        self,
        client: AsyncClient,
        api_key_headers: dict,
        manufacturing_order: dict,
    ):
        """AC-010: manufacturing ステータスの注文で 409 が返される."""
        order_number = manufacturing_order["order_number"]
        headers = {"X-API-Key": api_key_headers["X-API-Key"]}

        response = await client.post(
            f"/api/v1/external/orders/{order_number}/cancel",
            headers=headers,
        )

        assert response.status_code == 409


# ============================================================
# AC-011: 認証なし -> 401
# ============================================================


class TestCancelOrderUnauthorizedAPI:
    """Integration tests for unauthenticated cancel requests."""

    @pytest.mark.asyncio
    async def test_cancel_without_api_key_returns_401(
        self,
        client: AsyncClient,
    ):
        """AC-011: APIキーなしで 401 が返される."""
        response = await client.post(
            "/api/v1/external/orders/ANY-ORDER-001/cancel",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cancel_with_invalid_api_key_returns_401(
        self,
        client: AsyncClient,
    ):
        """AC-011: 無効なAPIキーで 401 が返される."""
        headers = {"X-API-Key": "invalid-api-key-that-does-not-exist"}

        response = await client.post(
            "/api/v1/external/orders/ANY-ORDER-001/cancel",
            headers=headers,
        )

        assert response.status_code == 401
