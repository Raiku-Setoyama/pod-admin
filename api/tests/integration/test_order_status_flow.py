"""Integration tests for order status flow.

FEAT-0006: Order status manual switching functionality.
Tests the full flow through API -> Service -> Repository -> Database.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4


@pytest.fixture
async def test_order_ordered(db_session: AsyncSession, test_order_source: dict):
    """Create a test order in 'ordered' status."""
    order_id = str(uuid4())

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
            "order_number": f"ORD-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product",
            "quantity": 1,
            "customer_name": "Test Customer",
            "customer_email": "customer@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "Tokyo",
            "customer_address_city": "Chiyoda",
            "status": "ordered",
        },
    )
    await db_session.commit()

    yield {"id": order_id, "order_source_id": test_order_source["id"]}


@pytest.fixture
async def test_order_manufacturing(db_session: AsyncSession, test_order_source: dict):
    """Create a test order in 'manufacturing' status."""
    order_id = str(uuid4())

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
            "order_number": f"MFG-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product",
            "quantity": 1,
            "customer_name": "Test Customer",
            "customer_email": "customer@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "Tokyo",
            "customer_address_city": "Chiyoda",
            "status": "manufacturing",
        },
    )
    await db_session.commit()

    yield {"id": order_id, "order_source_id": test_order_source["id"]}


@pytest.fixture
async def test_order_delivered_with_shipment(
    db_session: AsyncSession, test_order_source: dict
):
    """Create a test order in 'delivered' status with a pending shipment."""
    order_id = str(uuid4())
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())

    # Create order
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
            "order_number": f"DLV-{order_id[:8]}",
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
        {"id": shipment_item_id, "shipment_id": shipment_id, "order_id": order_id},
    )

    await db_session.commit()

    yield {
        "id": order_id,
        "shipment_id": shipment_id,
        "order_source_id": test_order_source["id"],
    }


@pytest.fixture
async def test_order_delivered_with_shipped_shipment(
    db_session: AsyncSession, test_order_source: dict
):
    """Create a test order in 'delivered' status with a shipped shipment."""
    order_id = str(uuid4())
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())

    # Create order (status is still delivered, but shipment is shipped)
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
            "status": "shipped",  # Already shipped
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
        "id": order_id,
        "shipment_id": shipment_id,
        "order_source_id": test_order_source["id"],
    }


class TestOrderStatusTransitionAPI:
    """Integration tests for order status transition via API."""

    # ===========================================
    # Forward transitions
    # ===========================================

    @pytest.mark.asyncio
    async def test_ordered_to_manufacturing(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_ordered: dict,
        db_session: AsyncSession,
    ):
        """Test: ordered -> manufacturing via API."""
        order_id = test_order_ordered["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "manufacturing"

        # Verify in database
        result = await db_session.execute(
            text("SELECT status FROM orders WHERE id = :id"),
            {"id": order_id},
        )
        row = result.fetchone()
        assert row[0] == "manufacturing"

    @pytest.mark.asyncio
    async def test_manufacturing_to_ordered(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_manufacturing: dict,
        db_session: AsyncSession,
    ):
        """Test: manufacturing -> ordered via API (reverse transition)."""
        order_id = test_order_manufacturing["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ordered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ordered"

    @pytest.mark.asyncio
    async def test_ordered_to_delivered_creates_shipment(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_ordered: dict,
        db_session: AsyncSession,
    ):
        """Test: ordered -> delivered creates shipment automatically."""
        order_id = test_order_ordered["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "delivered"

        # Verify shipment was created
        result = await db_session.execute(
            text("""
                SELECT s.id FROM shipments s
                JOIN shipment_items si ON si.shipment_id = s.id
                WHERE si.order_id = :order_id
            """),
            {"order_id": order_id},
        )
        shipment = result.fetchone()
        assert shipment is not None

    @pytest.mark.asyncio
    async def test_manufacturing_to_delivered_creates_shipment(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_manufacturing: dict,
        db_session: AsyncSession,
    ):
        """Test: manufacturing -> delivered creates shipment automatically."""
        order_id = test_order_manufacturing["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "delivered"

        # Verify shipment was created
        result = await db_session.execute(
            text("""
                SELECT s.id FROM shipments s
                JOIN shipment_items si ON si.shipment_id = s.id
                WHERE si.order_id = :order_id
            """),
            {"order_id": order_id},
        )
        shipment = result.fetchone()
        assert shipment is not None

    # ===========================================
    # Reverse transitions (from delivered)
    # ===========================================

    @pytest.mark.asyncio
    async def test_delivered_to_ordered_deletes_shipment(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_delivered_with_shipment: dict,
        db_session: AsyncSession,
    ):
        """Test: delivered -> ordered deletes related shipment."""
        order_id = test_order_delivered_with_shipment["id"]
        shipment_id = test_order_delivered_with_shipment["shipment_id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ordered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ordered"

        # Verify shipment was deleted (or shipment_item was deleted)
        result = await db_session.execute(
            text("""
                SELECT si.id FROM shipment_items si
                WHERE si.order_id = :order_id
            """),
            {"order_id": order_id},
        )
        shipment_item = result.fetchone()
        assert shipment_item is None

    @pytest.mark.asyncio
    async def test_delivered_to_manufacturing_deletes_shipment(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_delivered_with_shipment: dict,
        db_session: AsyncSession,
    ):
        """Test: delivered -> manufacturing deletes related shipment."""
        order_id = test_order_delivered_with_shipment["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "manufacturing"

        # Verify shipment was deleted
        result = await db_session.execute(
            text("""
                SELECT si.id FROM shipment_items si
                WHERE si.order_id = :order_id
            """),
            {"order_id": order_id},
        )
        shipment_item = result.fetchone()
        assert shipment_item is None

    # ===========================================
    # Invalid transitions
    # ===========================================

    @pytest.mark.asyncio
    async def test_cannot_transition_to_shipped_directly(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_ordered: dict,
    ):
        """Test: Direct transition to shipped is rejected."""
        order_id = test_order_ordered["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "shipped"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "INVALID_STATUS_TRANSITION" in data.get("error", {}).get("code", "")

    @pytest.mark.asyncio
    async def test_cannot_revert_from_delivered_when_shipment_shipped(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_delivered_with_shipped_shipment: dict,
    ):
        """Test: Cannot go back from delivered when shipment is already shipped."""
        order_id = test_order_delivered_with_shipped_shipment["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ordered"},
            headers=auth_headers,
        )

        # Should be rejected because shipment is already shipped
        assert response.status_code == 400

    # ===========================================
    # Edge cases
    # ===========================================

    @pytest.mark.asyncio
    async def test_order_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test: Returns 404 when order not found."""
        non_existent_id = str(uuid4())

        response = await client.patch(
            f"/api/v1/orders/{non_existent_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_status_value(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_ordered: dict,
    ):
        """Test: Returns 422 when invalid status value provided."""
        order_id = test_order_ordered["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "invalid_status"},
            headers=auth_headers,
        )

        assert response.status_code == 422
