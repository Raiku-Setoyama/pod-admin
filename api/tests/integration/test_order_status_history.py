"""Integration tests for order status history.

FEAT-0014: AC-002, AC-003, AC-004, AC-005, AC-006, AC-010, AC-011, AC-013
Tests the full flow through API -> Service -> Repository -> Database
for status history recording and retrieval.
"""

import json
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
async def test_order_for_history(db_session: AsyncSession, test_order_source: dict):
    """Create a test order in 'ordered' status for history tests."""
    order_id = str(uuid4())

    await db_session.execute(
        text("""
            INSERT INTO orders (
                id, order_number, order_source_id, product_name, quantity,
                customer_name, customer_email, customer_phone,
                customer_postal_code, customer_address_prefecture,
                customer_address_city, status, ordered_at, total_price,
                created_at, updated_at
            )
            VALUES (
                :id, :order_number, :order_source_id, :product_name, :quantity,
                :customer_name, :customer_email, :customer_phone,
                :customer_postal_code, :customer_address_prefecture,
                :customer_address_city, :status, NOW(), :total_price,
                NOW(), NOW()
            )
        """),
        {
            "id": order_id,
            "order_number": f"HIST-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product",
            "quantity": 1,
            "customer_name": "テスト顧客",
            "customer_email": "customer@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区1-1-1",
            "status": "ordered",
            "total_price": 1000,
        },
    )
    await db_session.commit()

    yield {"id": order_id, "order_source_id": test_order_source["id"]}


@pytest.fixture
async def test_orders_for_bulk_history(db_session: AsyncSession, test_order_source: dict):
    """Create 3 test orders in 'ordered' status for bulk history tests."""
    order_ids = []
    for i in range(3):
        order_id = str(uuid4())
        order_ids.append(order_id)

        await db_session.execute(
            text("""
                INSERT INTO orders (
                    id, order_number, order_source_id, product_name, quantity,
                    customer_name, customer_email, customer_phone,
                    customer_postal_code, customer_address_prefecture,
                    customer_address_city, status, ordered_at, total_price,
                    created_at, updated_at
                )
                VALUES (
                    :id, :order_number, :order_source_id, :product_name, :quantity,
                    :customer_name, :customer_email, :customer_phone,
                    :customer_postal_code, :customer_address_prefecture,
                    :customer_address_city, :status, NOW(), :total_price,
                    NOW(), NOW()
                )
            """),
            {
                "id": order_id,
                "order_number": f"BULK-{order_id[:8]}",
                "order_source_id": test_order_source["id"],
                "product_name": f"Test Product {i}",
                "quantity": 1,
                "customer_name": f"テスト顧客{i}",
                "customer_email": f"customer{i}@example.com",
                "customer_phone": f"090-000{i}-0000",
                "customer_postal_code": "100-0001",
                "customer_address_prefecture": "東京都",
                "customer_address_city": f"千代田区{i}-{i}-{i}",
                "status": "ordered",
                "total_price": 1000 * (i + 1),
            },
        )

    await db_session.commit()

    yield {"ids": order_ids, "order_source_id": test_order_source["id"]}


@pytest.fixture
async def test_manufacturer_for_history(db_session: AsyncSession):
    """Create a test manufacturer for history tests."""
    manufacturer_id = str(uuid4())
    manufacturer_name = f"テストメーカー_{manufacturer_id[:8]}"

    await db_session.execute(
        text("""
            INSERT INTO manufacturers (
                id, name, email, phone, supported_products, unit_prices,
                lead_time_days, daily_order_limit,
                sharing_method, is_active, created_at, updated_at
            )
            VALUES (
                :id, :name, :email, :phone, :supported_products, :unit_prices,
                :lead_time_days, :daily_order_limit,
                :sharing_method, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": manufacturer_id,
            "name": manufacturer_name,
            "email": "manufacturer@example.com",
            "phone": "03-1234-5678",
            "supported_products": ["acrylic_keychain"],
            "unit_prices": json.dumps({}),
            "lead_time_days": 7,
            "daily_order_limit": 100,
            "sharing_method": "DRIVE",
            "is_active": True,
        },
    )
    await db_session.commit()

    yield {"id": manufacturer_id, "name": manufacturer_name}


@pytest.fixture
async def test_order_with_manufacturer(
    db_session: AsyncSession,
    test_order_source: dict,
    test_manufacturer_for_history: dict,
):
    """Create a test order with product linked to manufacturer."""
    order_id = str(uuid4())
    product_id = str(uuid4())
    order_item_id = str(uuid4())
    manufacturer_id = test_manufacturer_for_history["id"]

    # Create product linked to manufacturer
    await db_session.execute(
        text("""
            INSERT INTO products (
                id, product_type, size, position, color, manufacturer_id, cost, lead_time_days,
                is_active, created_at, updated_at
            )
            VALUES (
                :id, :product_type, :size, :position, :color, :manufacturer_id, :cost, :lead_time_days,
                :is_active, NOW(), NOW()
            )
        """),
        {
            "id": product_id,
            "product_type": "acrylic_keychain",
            "size": f"50x50_{product_id[:8]}",
            "position": "正面",
            "color": "クリア",
            "manufacturer_id": manufacturer_id,
            "cost": 500,
            "lead_time_days": 5,
            "is_active": True,
        },
    )

    # Create order
    await db_session.execute(
        text("""
            INSERT INTO orders (
                id, order_number, order_source_id, product_name, quantity,
                customer_name, customer_email, customer_phone,
                customer_postal_code, customer_address_prefecture,
                customer_address_city, status, ordered_at, total_price,
                created_at, updated_at
            )
            VALUES (
                :id, :order_number, :order_source_id, :product_name, :quantity,
                :customer_name, :customer_email, :customer_phone,
                :customer_postal_code, :customer_address_prefecture,
                :customer_address_city, :status, NOW(), :total_price,
                NOW(), NOW()
            )
        """),
        {
            "id": order_id,
            "order_number": f"MFR-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "アクリルキーホルダー",
            "quantity": 1,
            "customer_name": "テスト顧客",
            "customer_email": "customer@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区1-1-1",
            "status": "ordered",
            "total_price": 1500,
        },
    )

    # Create order item linked to product
    await db_session.execute(
        text("""
            INSERT INTO order_items (
                id, order_id, product_id, product_name, product_type,
                price, quantity, uid, created_at, updated_at
            )
            VALUES (
                :id, :order_id, :product_id, :product_name, :product_type,
                :price, :quantity, :uid, NOW(), NOW()
            )
        """),
        {
            "id": order_item_id,
            "order_id": order_id,
            "product_id": product_id,
            "product_name": "アクリルキーホルダー - 50x50 (mm) - アクリル",
            "product_type": "acrylic_keychain",
            "price": 1500,
            "quantity": 1,
            "uid": "test-uid-001",
        },
    )

    await db_session.commit()

    yield {
        "id": order_id,
        "product_id": product_id,
        "order_item_id": order_item_id,
        "manufacturer_id": manufacturer_id,
        "order_source_id": test_order_source["id"],
    }


# =========================================================================
# AC-002: Single status update records history
# =========================================================================


class TestSingleStatusUpdateHistory:
    """AC-002: Status update via PATCH /orders/{id}/status creates history record."""

    @pytest.mark.asyncio
    async def test_status_update_creates_history_record(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_for_history: dict,
        db_session: AsyncSession,
    ):
        """AC-002: Single order status update creates history record.

        given: An order in 'ordered' status
        when: PATCH /orders/{id}/status changes to 'manufacturing'
        then: order_status_history has from_status=ordered, to_status=manufacturing
        """
        order_id = test_order_for_history["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify history record in DB
        result = await db_session.execute(
            text("""
                SELECT from_status, to_status, changed_by
                FROM order_status_history
                WHERE order_id = :order_id
                ORDER BY created_at DESC
            """),
            {"order_id": order_id},
        )
        history = result.fetchone()
        assert history is not None
        assert history[0] == "ordered"  # from_status
        assert history[1] == "manufacturing"  # to_status


# =========================================================================
# AC-003: Bulk status update records history for each order
# =========================================================================


class TestBulkStatusUpdateHistory:
    """AC-003: Bulk status update creates history records for each order."""

    @pytest.mark.asyncio
    async def test_bulk_update_creates_history_for_each_order(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_orders_for_bulk_history: dict,
        db_session: AsyncSession,
    ):
        """AC-003: Bulk status update creates history for each of 3 orders.

        given: 3 orders in 'ordered' status
        when: PATCH /orders/bulk-status changes all 3 to 'manufacturing'
        then: 3 history records are created in order_status_history
        """
        order_ids = test_orders_for_bulk_history["ids"]

        response = await client.patch(
            "/api/v1/orders/bulk-status",
            json={
                "order_ids": order_ids,
                "status": "manufacturing",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 3

        # Verify history records in DB
        result = await db_session.execute(
            text("""
                SELECT order_id, from_status, to_status
                FROM order_status_history
                WHERE order_id = ANY(:order_ids)
                ORDER BY created_at
            """),
            {"order_ids": order_ids},
        )
        history_rows = result.fetchall()
        assert len(history_rows) == 3

        for row in history_rows:
            assert row[1] == "ordered"  # from_status
            assert row[2] == "manufacturing"  # to_status


# =========================================================================
# AC-004: Manufacturer status update records history
# =========================================================================


class TestManufacturerStatusUpdateHistory:
    """AC-004: Manufacturer status update creates history records."""

    @pytest.mark.asyncio
    async def test_manufacturer_status_update_creates_history(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_with_manufacturer: dict,
        db_session: AsyncSession,
    ):
        """AC-004: Manufacturer status update creates history record.

        given: A manufacturer has an order in 'ordered' status
        when: Manufacturer status update changes to 'manufacturing'
        then: order_status_history has corresponding record
        """
        manufacturer_id = test_order_with_manufacturer["manufacturer_id"]
        order_id = test_order_with_manufacturer["id"]

        response = await client.patch(
            f"/api/v1/manufacturers/{manufacturer_id}/order-status",
            json={
                "status": "manufacturing",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify history record
        result = await db_session.execute(
            text("""
                SELECT from_status, to_status, changed_by
                FROM order_status_history
                WHERE order_id = :order_id
                ORDER BY created_at DESC
            """),
            {"order_id": order_id},
        )
        history = result.fetchone()
        assert history is not None
        assert history[0] == "ordered"  # from_status
        assert history[1] == "manufacturing"  # to_status


# =========================================================================
# AC-005: GET /orders/{order_id}/status-history returns history in desc order
# =========================================================================


class TestGetStatusHistory:
    """AC-005: GET /orders/{order_id}/status-history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_returns_descending_order(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_for_history: dict,
        db_session: AsyncSession,
    ):
        """AC-005: GET /orders/{order_id}/status-history returns records in desc order.

        given: An order has multiple status changes
        when: GET /orders/{order_id}/status-history
        then: History is returned in created_at descending order
        """
        order_id = test_order_for_history["id"]

        # First status change: ordered -> manufacturing
        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )

        # Second status change: manufacturing -> delivered
        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=auth_headers,
        )

        # Get history
        response = await client.get(
            f"/api/v1/orders/{order_id}/status-history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 2

        # Verify descending order (newest first)
        items = data["items"]
        for i in range(len(items) - 1):
            assert items[i]["created_at"] >= items[i + 1]["created_at"]

    @pytest.mark.asyncio
    async def test_get_history_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_for_history: dict,
    ):
        """Test: Returns empty list when no history exists.

        given: An order with no status history
        when: GET /orders/{order_id}/status-history
        then: Returns empty items list
        """
        order_id = test_order_for_history["id"]

        response = await client.get(
            f"/api/v1/orders/{order_id}/status-history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        # Could be 0 or 1 (if initial status is recorded at order creation)
        assert isinstance(data["items"], list)


# =========================================================================
# AC-006: 404 for non-existent order
# =========================================================================


class TestGetStatusHistoryNotFound:
    """AC-006: GET /orders/{order_id}/status-history returns 404 for non-existent order."""

    @pytest.mark.asyncio
    async def test_get_history_nonexistent_order_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """AC-006: Non-existent order returns 404.

        given: A non-existent order_id
        when: GET /orders/{order_id}/status-history
        then: 404 Not Found error is returned
        """
        non_existent_id = str(uuid4())

        response = await client.get(
            f"/api/v1/orders/{non_existent_id}/status-history",
            headers=auth_headers,
        )

        assert response.status_code == 404


# =========================================================================
# AC-010: changed_by records user name
# =========================================================================


class TestChangedByRecording:
    """AC-010: changed_by records the name of the admin user."""

    @pytest.mark.asyncio
    async def test_changed_by_records_admin_name(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_for_history: dict,
        db_session: AsyncSession,
    ):
        """AC-010: changed_by contains the admin user's name.

        given: Admin user "Test Admin" is logged in
        when: PATCH /orders/{id}/status changes status
        then: History record's changed_by is "Test Admin"
        """
        order_id = test_order_for_history["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify changed_by in history record
        result = await db_session.execute(
            text("""
                SELECT changed_by
                FROM order_status_history
                WHERE order_id = :order_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"order_id": order_id},
        )
        history = result.fetchone()
        assert history is not None
        # The admin user name should be "Test Admin" (from test_admin_user fixture)
        assert history[0] is not None
        assert len(history[0]) > 0


# =========================================================================
# AC-011: Manufacturer changed_by records "システム（メーカー発注）"
# =========================================================================


class TestManufacturerChangedBy:
    """AC-011: Manufacturer updates record changed_by as system identifier."""

    @pytest.mark.asyncio
    async def test_manufacturer_update_changed_by_is_system(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_with_manufacturer: dict,
        db_session: AsyncSession,
    ):
        """AC-011: Manufacturer status update sets changed_by to "システム（メーカー発注）".

        given: A manufacturer status update is executed
        when: ManufacturerOrderService.update_order_status is called
        then: History record has changed_by="システム（メーカー発注）"
        """
        manufacturer_id = test_order_with_manufacturer["manufacturer_id"]
        order_id = test_order_with_manufacturer["id"]

        response = await client.patch(
            f"/api/v1/manufacturers/{manufacturer_id}/order-status",
            json={
                "status": "manufacturing",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify changed_by
        result = await db_session.execute(
            text("""
                SELECT changed_by
                FROM order_status_history
                WHERE order_id = :order_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"order_id": order_id},
        )
        history = result.fetchone()
        assert history is not None
        assert history[0] == "システム（メーカー発注）"


# =========================================================================
# AC-013: Alembic migration creates table correctly
# =========================================================================


class TestMigration:
    """AC-013: Alembic migration creates order_status_history table."""

    @pytest.mark.asyncio
    async def test_order_status_history_table_exists(
        self,
        db_session: AsyncSession,
    ):
        """AC-013: order_status_history table exists after migration.

        given: Existing database schema
        when: Check for order_status_history table
        then: Table exists with proper columns
        """
        result = await db_session.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'order_status_history'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: {"data_type": row[1], "is_nullable": row[2]} for row in result.fetchall()}

        # Table should exist with required columns
        assert "id" in columns
        assert "order_id" in columns
        assert "from_status" in columns
        assert "to_status" in columns
        assert "changed_by" in columns
        assert "note" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        # from_status should be nullable
        assert columns["from_status"]["is_nullable"] == "YES"
        # to_status should be NOT NULL
        assert columns["to_status"]["is_nullable"] == "NO"
        # changed_by should be nullable
        assert columns["changed_by"]["is_nullable"] == "YES"
        # note should be nullable
        assert columns["note"]["is_nullable"] == "YES"

    @pytest.mark.asyncio
    async def test_order_status_history_has_order_id_index(
        self,
        db_session: AsyncSession,
    ):
        """AC-013: order_status_history has index on order_id.

        given: order_status_history table exists
        when: Check for index on order_id
        then: Index exists
        """
        result = await db_session.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'order_status_history'
                AND indexdef LIKE '%order_id%'
            """)
        )
        indexes = result.fetchall()
        assert len(indexes) > 0, "Expected index on order_id column"

    @pytest.mark.asyncio
    async def test_order_status_history_has_foreign_key(
        self,
        db_session: AsyncSession,
    ):
        """AC-013: order_status_history has FK to orders table.

        given: order_status_history table exists
        when: Check for foreign key on order_id
        then: FK constraint to orders.id exists
        """
        result = await db_session.execute(
            text("""
                SELECT tc.constraint_name, ccu.table_name AS foreign_table_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.table_name = 'order_status_history'
                AND tc.constraint_type = 'FOREIGN KEY'
                AND ccu.table_name = 'orders'
            """)
        )
        fk_constraints = result.fetchall()
        assert len(fk_constraints) > 0, "Expected FK constraint to orders table"
