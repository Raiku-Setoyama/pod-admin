"""Integration tests for order bulk status update API.

FEAT-0007: Order bulk status update functionality.
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
async def test_orders_ordered(db_session: AsyncSession, test_order_source: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """Create multiple test orders in 'ordered' status."""
    order_ids = [str(uuid4()) for _ in range(3)]

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
                "order_number": f"BULK-ORD-{i}-{order_id[:8]}",
                "order_source_id": test_order_source["id"],
                "product_name": f"Test Product {i}",
                "quantity": 1,
                "customer_name": f"Test Customer {i}",
                "customer_email": f"customer{i}@example.com",
                "customer_phone": "090-0000-0000",
                "customer_postal_code": "100-0001",
                "customer_address_prefecture": "Tokyo",
                "customer_address_city": "Chiyoda",
                "status": "ordered",
            },
        )
    await db_session.commit()

    yield {"order_ids": order_ids, "order_source_id": test_order_source["id"]}


@pytest.fixture
async def test_orders_manufacturing(db_session: AsyncSession, test_order_source: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """Create multiple test orders in 'manufacturing' status."""
    order_ids = [str(uuid4()) for _ in range(3)]

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
                "order_number": f"BULK-MFG-{i}-{order_id[:8]}",
                "order_source_id": test_order_source["id"],
                "product_name": f"Test Product {i}",
                "quantity": 1,
                "customer_name": f"Test Customer {i}",
                "customer_email": f"customer{i}@example.com",
                "customer_phone": "090-0000-0000",
                "customer_postal_code": "100-0001",
                "customer_address_prefecture": "Tokyo",
                "customer_address_city": "Chiyoda",
                "status": "manufacturing",
            },
        )
    await db_session.commit()

    yield {"order_ids": order_ids, "order_source_id": test_order_source["id"]}


@pytest.fixture
async def test_orders_delivered_with_shipments(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Create multiple test orders in 'delivered' status with pending shipments."""
    order_ids = [str(uuid4()) for _ in range(3)]
    shipment_ids = [str(uuid4()) for _ in range(3)]

    for i, (order_id, shipment_id) in enumerate(zip(order_ids, shipment_ids, strict=True)):
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
                "order_number": f"BULK-DLV-{i}-{order_id[:8]}",
                "order_source_id": test_order_source["id"],
                "product_name": f"Test Product {i}",
                "quantity": 1,
                "customer_name": f"Test Customer {i}",
                "customer_email": f"customer{i}@example.com",
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
        "order_ids": order_ids,
        "shipment_ids": shipment_ids,
        "order_source_id": test_order_source["id"],
    }


@pytest.fixture
async def test_orders_mixed_statuses(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Create test orders with mixed statuses (ordered and shipped)."""
    order_ordered_id = str(uuid4())
    order_shipped_id = str(uuid4())
    shipment_id = str(uuid4())

    # Create ordered order
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
            "id": order_ordered_id,
            "order_number": f"BULK-MIX-ORD-{order_ordered_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product Ordered",
            "quantity": 1,
            "customer_name": "Test Customer Ordered",
            "customer_email": "ordered@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "Tokyo",
            "customer_address_city": "Chiyoda",
            "status": "ordered",
        },
    )

    # Create shipped order
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
            "id": order_shipped_id,
            "order_number": f"BULK-MIX-SHP-{order_shipped_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product Shipped",
            "quantity": 1,
            "customer_name": "Test Customer Shipped",
            "customer_email": "shipped@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "Tokyo",
            "customer_address_city": "Chiyoda",
            "status": "shipped",
        },
    )

    # Create shipped shipment for shipped order
    await db_session.execute(
        text("""
            INSERT INTO shipments (id, status, shipped_at, created_at, updated_at)
            VALUES (:id, :status, NOW(), NOW(), NOW())
        """),
        {"id": shipment_id, "status": "shipped"},
    )

    shipment_item_id = str(uuid4())
    await db_session.execute(
        text("""
            INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
            VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
        """),
        {
            "id": shipment_item_id,
            "shipment_id": shipment_id,
            "order_id": order_shipped_id,
        },
    )

    await db_session.commit()

    yield {
        "order_ordered_id": order_ordered_id,
        "order_shipped_id": order_shipped_id,
        "shipment_id": shipment_id,
        "order_source_id": test_order_source["id"],
    }


@pytest.fixture
async def test_orders_delivered_with_shipped_shipment(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Create test orders in 'delivered' status with shipped shipments."""
    order_ids = [str(uuid4()) for _ in range(2)]
    shipment_ids = [str(uuid4()) for _ in range(2)]

    for i, (order_id, shipment_id) in enumerate(zip(order_ids, shipment_ids, strict=True)):
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
                "order_number": f"BULK-SHPD-{i}-{order_id[:8]}",
                "order_source_id": test_order_source["id"],
                "product_name": f"Test Product {i}",
                "quantity": 1,
                "customer_name": f"Test Customer {i}",
                "customer_email": f"customer{i}@example.com",
                "customer_phone": "090-0000-0000",
                "customer_postal_code": "100-0001",
                "customer_address_prefecture": "Tokyo",
                "customer_address_city": "Chiyoda",
                "status": "shipped",  # Order is shipped
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
        "order_ids": order_ids,
        "shipment_ids": shipment_ids,
        "order_source_id": test_order_source["id"],
    }


class TestOrderBulkStatusUpdateAPI:
    """Integration tests for order bulk status update via API."""

    # ===========================================
    # AC-007: Bulk update API works correctly
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_ordered_to_manufacturing_all_success(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_ordered: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """AC-007: PATCH /orders/bulk-status updates all orders and returns correct count."""
        order_ids = test_orders_ordered["order_ids"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "manufacturing"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 3
        assert data["failed_count"] == 0
        assert data["failed_ids"] == []

        # Verify in database
        for order_id in order_ids:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": order_id},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "manufacturing"

    # ===========================================
    # AC-008: Partial success returns correct results
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_partial_success_mixed_statuses(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_mixed_statuses: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """AC-008: Mixed statuses - only valid transitions succeed, failed IDs returned."""
        order_ordered_id = test_orders_mixed_statuses["order_ordered_id"]
        order_shipped_id = test_orders_mixed_statuses["order_shipped_id"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={
                "order_ids": [order_ordered_id, order_shipped_id],
                "status": "manufacturing",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 1
        assert data["failed_count"] == 1
        assert order_shipped_id in data["failed_ids"]

        # Verify ordered order was updated
        result = await db_session.execute(
            text("SELECT status FROM orders WHERE id = :id"),
            {"id": order_ordered_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "manufacturing"

        # Verify shipped order was NOT updated
        result = await db_session.execute(
            text("SELECT status FROM orders WHERE id = :id"),
            {"id": order_shipped_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "shipped"

    # ===========================================
    # AC-009: shipped status rejected with 422
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_to_shipped_rejected_with_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_ordered: dict[str, Any],
    ) -> None:
        """AC-009: PATCH /orders/bulk-status with status=shipped returns 422."""
        order_ids = test_orders_ordered["order_ids"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "shipped"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    # ===========================================
    # AC-010: delivered creates Shipments
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_to_delivered_creates_shipments(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_manufacturing: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """AC-010: PATCH /orders/bulk-status to delivered creates shipments for all."""
        order_ids = test_orders_manufacturing["order_ids"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "delivered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 3
        assert data["failed_count"] == 0

        # Verify all orders are now delivered
        for order_id in order_ids:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": order_id},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "delivered"

            # Verify shipment was created for each order
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
    # AC-011: delivered -> ordered deletes Shipments
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_delivered_to_ordered_deletes_shipments(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_delivered_with_shipments: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """AC-011: delivered -> ordered deletes related shipments."""
        order_ids = test_orders_delivered_with_shipments["order_ids"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "ordered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 3
        assert data["failed_count"] == 0

        # Verify all orders are now ordered
        for order_id in order_ids:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": order_id},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "ordered"

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
    # AC-012: shipped shipment blocks reverting
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_fails_when_shipment_is_shipped(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_delivered_with_shipped_shipment: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """AC-012: Orders with shipped shipments cannot be reverted."""
        order_ids = test_orders_delivered_with_shipped_shipment["order_ids"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "ordered"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 0
        assert data["failed_count"] == 2
        assert set(data["failed_ids"]) == set(order_ids)

    # ===========================================
    # AC-013: Empty order_ids returns 400/422
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_empty_order_ids_returns_error(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
    ) -> None:
        """AC-013: Empty order_ids returns 400/422 error."""
        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": [], "status": "manufacturing"},
            headers=auth_headers,
        )

        # Should return 400 or 422 for validation error
        assert response.status_code in [400, 422]

    # ===========================================
    # Additional integration tests
    # ===========================================

    @pytest.mark.asyncio
    async def test_bulk_update_nonexistent_orders_in_failed_ids(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_ordered: dict[str, Any],
    ) -> None:
        """Non-existent order IDs are included in failed_ids."""
        valid_order_id = test_orders_ordered["order_ids"][0]
        nonexistent_id = str(uuid4())

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={
                "order_ids": [valid_order_id, nonexistent_id],
                "status": "manufacturing",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 1
        assert data["failed_count"] == 1
        assert nonexistent_id in data["failed_ids"]

    @pytest.mark.asyncio
    async def test_bulk_update_requires_authentication(
        self,
        client: AsyncClient,
        test_orders_ordered: dict[str, Any],
    ) -> None:
        """Bulk update requires authentication."""
        order_ids = test_orders_ordered["order_ids"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "manufacturing"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bulk_update_invalid_status_value(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_ordered: dict[str, Any],
    ) -> None:
        """Invalid status value returns 422."""
        order_ids = test_orders_ordered["order_ids"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "invalid_status"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_update_ordered_to_delivered_then_back_to_manufacturing(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        test_orders_ordered: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """Full flow: ordered -> delivered -> manufacturing with shipment lifecycle."""
        order_ids = test_orders_ordered["order_ids"]

        # Step 1: ordered -> delivered (creates shipments)
        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "delivered"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 3

        # Verify shipments exist
        for order_id in order_ids:
            result = await db_session.execute(
                text("""
                    SELECT s.id FROM shipments s
                    JOIN shipment_items si ON si.shipment_id = s.id
                    WHERE si.order_id = :order_id
                """),
                {"order_id": order_id},
            )
            assert result.fetchone() is not None

        # Step 2: delivered -> manufacturing (deletes shipments)
        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": order_ids, "status": "manufacturing"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 3

        # Verify shipments deleted
        for order_id in order_ids:
            result = await db_session.execute(
                text("""
                    SELECT si.id FROM shipment_items si
                    WHERE si.order_id = :order_id
                """),
                {"order_id": order_id},
            )
            assert result.fetchone() is None

            # Verify order status
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": order_id},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "manufacturing"
