"""Integration tests for shipment status flow.

FEAT-0006: Shipment status manual switching functionality.
Tests the full flow through API -> Service -> Repository -> Database.
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_shipment_pending(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Create a test shipment in 'pending' status with one order."""
    order_id = str(uuid4())
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())

    # Create order in delivered status
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
            "order_number": f"PND-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product",
            "quantity": 1,
            "customer_name": "Test Customer",
            "customer_email": "customer@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "Tokyo",
            "customer_address_city": "Chiyoda",
            "status": "delivered",
        },
    )

    # Create pending shipment
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
        {"id": shipment_item_id, "shipment_id": shipment_id, "order_id": order_id},
    )

    await db_session.commit()

    yield {
        "id": shipment_id,
        "order_id": order_id,
        "order_source_id": test_order_source["id"],
    }


@pytest.fixture
async def test_shipment_ready(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Create a test shipment in 'ready' status with one order."""
    order_id = str(uuid4())
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())

    # Create order in delivered status
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
            "order_number": f"RDY-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product",
            "quantity": 1,
            "customer_name": "Test Customer",
            "customer_email": "customer@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "Tokyo",
            "customer_address_city": "Chiyoda",
            "status": "delivered",
        },
    )

    # Create ready shipment
    await db_session.execute(
        text("""
            INSERT INTO shipments (id, status, created_at, updated_at)
            VALUES (:id, :status, NOW(), NOW())
        """),
        {"id": shipment_id, "status": "ready"},
    )

    # Create shipment item
    await db_session.execute(
        text("""
            INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
            VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
        """),
        {"id": shipment_item_id, "shipment_id": shipment_id, "order_id": order_id},
    )

    await db_session.commit()

    yield {
        "id": shipment_id,
        "order_id": order_id,
        "order_source_id": test_order_source["id"],
    }


@pytest.fixture
async def test_shipment_shipped(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Create a test shipment in 'shipped' status with one order."""
    order_id = str(uuid4())
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())

    # Create order in shipped status
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
            "order_number": f"SHP-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product",
            "quantity": 1,
            "customer_name": "Test Customer",
            "customer_email": "customer@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "Tokyo",
            "customer_address_city": "Chiyoda",
            "status": "shipped",
        },
    )

    # Create shipped shipment
    await db_session.execute(
        text("""
            INSERT INTO shipments (id, status, shipped_at, created_at, updated_at)
            VALUES (:id, :status, NOW(), NOW(), NOW())
        """),
        {"id": shipment_id, "status": "shipped"},
    )

    # Create shipment item
    await db_session.execute(
        text("""
            INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
            VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
        """),
        {"id": shipment_item_id, "shipment_id": shipment_id, "order_id": order_id},
    )

    await db_session.commit()

    yield {
        "id": shipment_id,
        "order_id": order_id,
        "order_source_id": test_order_source["id"],
    }


@pytest.fixture
async def test_shipment_with_multiple_orders(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Create a test shipment with multiple orders."""
    order_ids = [str(uuid4()) for _ in range(3)]
    shipment_id = str(uuid4())

    # Create multiple orders in delivered status
    for i, order_id in enumerate(order_ids):
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
                "order_number": f"MLT-{i}-{order_id[:8]}",
                "order_source_id": test_order_source["id"],
                "product_name": f"Test Product {i}",
                "quantity": 1,
                "customer_name": "Test Customer",
                "customer_email": "customer@example.com",
                "customer_phone": "090-0000-0000",
                "customer_postal_code": "100-0001",
                "customer_address_prefecture": "Tokyo",
                "customer_address_city": "Chiyoda",
                "status": "delivered",
            },
        )

    # Create pending shipment
    await db_session.execute(
        text("""
            INSERT INTO shipments (id, status, created_at, updated_at)
            VALUES (:id, :status, NOW(), NOW())
        """),
        {"id": shipment_id, "status": "pending"},
    )

    # Create shipment items for all orders
    for order_id in order_ids:
        shipment_item_id = str(uuid4())
        await db_session.execute(
            text("""
                INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
                VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
            """),
            {"id": shipment_item_id, "shipment_id": shipment_id, "order_id": order_id},
        )

    await db_session.commit()

    yield {
        "id": shipment_id,
        "order_ids": order_ids,
        "order_source_id": test_order_source["id"],
    }


class TestShipmentStatusTransitionAPI:
    """Integration tests for shipment status transition via API."""

    # ===========================================
    # Forward transitions
    # ===========================================

    @pytest.mark.asyncio
    async def test_pending_to_ready(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_pending: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: pending -> ready via API."""
        shipment_id = test_shipment_pending["id"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "ready"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

        # Verify in database
        result = await db_session.execute(
            text("SELECT status FROM shipments WHERE id = :id"),
            {"id": shipment_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "ready"

    @pytest.mark.asyncio
    async def test_ready_to_pending(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_ready: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: ready -> pending via API (reverse transition)."""
        shipment_id = test_shipment_ready["id"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "pending"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_pending_to_shipped_updates_order(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_pending: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: pending -> shipped sets shipped_at and updates order to shipped."""
        shipment_id = test_shipment_pending["id"]
        order_id = test_shipment_pending["order_id"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "shipped"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shipped"
        assert data["shipped_at"] is not None

        # Verify order status was updated
        result = await db_session.execute(
            text("SELECT status FROM orders WHERE id = :id"),
            {"id": order_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "shipped"

    @pytest.mark.asyncio
    async def test_ready_to_shipped_updates_order(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_ready: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: ready -> shipped sets shipped_at and updates order to shipped."""
        shipment_id = test_shipment_ready["id"]
        order_id = test_shipment_ready["order_id"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "shipped"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shipped"
        assert data["shipped_at"] is not None

        # Verify order status was updated
        result = await db_session.execute(
            text("SELECT status FROM orders WHERE id = :id"),
            {"id": order_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "shipped"

    # ===========================================
    # Reverse transitions (from shipped)
    # ===========================================

    @pytest.mark.asyncio
    async def test_shipped_to_pending_reverts_order(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_shipped: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: shipped -> pending clears shipped_at and reverts order to delivered."""
        shipment_id = test_shipment_shipped["id"]
        order_id = test_shipment_shipped["order_id"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "pending"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["shipped_at"] is None

        # Verify order status was reverted
        result = await db_session.execute(
            text("SELECT status FROM orders WHERE id = :id"),
            {"id": order_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "delivered"

    @pytest.mark.asyncio
    async def test_shipped_to_ready_reverts_order(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_shipped: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: shipped -> ready clears shipped_at and reverts order to delivered."""
        shipment_id = test_shipment_shipped["id"]
        order_id = test_shipment_shipped["order_id"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "ready"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["shipped_at"] is None

        # Verify order status was reverted
        result = await db_session.execute(
            text("SELECT status FROM orders WHERE id = :id"),
            {"id": order_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "delivered"

    # ===========================================
    # Multiple orders in shipment
    # ===========================================

    @pytest.mark.asyncio
    async def test_shipped_updates_all_orders(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_with_multiple_orders: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: shipping a shipment with multiple orders updates all orders."""
        shipment_id = test_shipment_with_multiple_orders["id"]
        order_ids = test_shipment_with_multiple_orders["order_ids"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "shipped"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shipped"

        # Verify all orders were updated
        for order_id in order_ids:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": order_id},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "shipped"

    @pytest.mark.asyncio
    async def test_revert_from_shipped_reverts_all_orders(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_with_multiple_orders: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: reverting from shipped reverts all orders to delivered."""
        shipment_id = test_shipment_with_multiple_orders["id"]
        order_ids = test_shipment_with_multiple_orders["order_ids"]

        # First, ship it
        await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "shipped"},
            headers=auth_headers,
        )

        # Then revert
        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "pending"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

        # Verify all orders were reverted
        for order_id in order_ids:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": order_id},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "delivered"

    # ===========================================
    # Additional fields
    # ===========================================

    @pytest.mark.asyncio
    async def test_tracking_number_set_on_ship(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_ready: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Test: tracking number can be set when shipping."""
        shipment_id = test_shipment_ready["id"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={
                "status": "shipped",
                "tracking_number": "1234567890",
                "carrier": "Yamato",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tracking_number"] == "1234567890"
        assert data["carrier"] == "Yamato"

        # Verify in database
        result = await db_session.execute(
            text("SELECT tracking_number, carrier FROM shipments WHERE id = :id"),
            {"id": shipment_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "1234567890"
        assert row[1] == "Yamato"

    # ===========================================
    # Edge cases
    # ===========================================

    @pytest.mark.asyncio
    async def test_shipment_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
    ) -> None:
        """Test: Returns 404 when shipment not found."""
        non_existent_id = str(uuid4())

        response = await client.patch(
            f"/api/v1/shipments/{non_existent_id}/status",
            json={"status": "ready"},
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_status_value(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_shipment_pending: dict[str, Any],
    ) -> None:
        """Test: Returns 422 when invalid status value provided."""
        shipment_id = test_shipment_pending["id"]

        response = await client.patch(
            f"/api/v1/shipments/{shipment_id}/status",
            json={"status": "invalid_status"},
            headers=auth_headers,
        )

        assert response.status_code == 422
