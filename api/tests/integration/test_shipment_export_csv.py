"""Integration tests for POST /api/v1/shipments/export-csv - 18th column.

FEAT-0017: Add "商品名（処理用）" column to shipment CSV export.
Tests the full flow through API -> Service -> Repository -> Database,
verifying that the exported CSV contains 18 columns with the correct
18th column header and data.

AC-006: POST /api/v1/shipments/export-csv returns 18-column CSV
        with "商品名（処理用）" header and "{order_number}_{uid}" data.
"""

import csv
import io
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_product_for_csv(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
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
                "name": f"FEAT17 Manufacturer {manufacturer_id[:8]}",
                "email": "feat17-mfg@example.com",
                "phone": "03-0017-0017",
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
                "position": "FEAT17",
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
async def shipment_for_csv_export(
    db_session: AsyncSession,
    test_order_source: dict[str, Any],
    test_product_for_csv: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """配送CSVエクスポートテスト用のデータセット.

    Order -> OrderItem (uid="TEST-UID-0017") -> Shipment の完全なリレーションを構築。
    """
    order_id = str(uuid4())
    order_number = f"FEAT17-{order_id[:8]}"
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())
    order_item_id = str(uuid4())
    uid = "TEST-UID-0017"

    # Create order (status=delivered for shipment)
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
            "order_number": order_number,
            "order_source_id": test_order_source["id"],
            "product_name": None,
            "quantity": 1,
            "customer_name": "FEAT-0017 Test Customer",
            "customer_email": "feat0017@example.com",
            "customer_phone": "090-0017-0017",
            "customer_postal_code": "100-0017",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区テスト17-1",
            "status": "delivered",
        },
    )

    # Create OrderItem with uid
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
            "uid": uid,
            "product_id": test_product_for_csv["id"],
            "product_name": "テスト商品FEAT17",
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
        "order_number": order_number,
        "uid": uid,
        "expected_18th_column": f"{order_number}_{uid}",
    }


class TestShipmentExportCsvAPI:
    """Integration tests for POST /api/v1/shipments/export-csv 18th column."""

    # ===========================================
    # AC-006: CSV response has 18 columns with correct 18th column
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac006_export_csv_has_18_columns_with_processing_product_name(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        shipment_for_csv_export: dict[str, Any],
    ) -> None:
        """AC-006: POST /api/v1/shipments/export-csv が18列のCSVを返す.

        Given: 配送データが登録されている
        When: POST /api/v1/shipments/export-csv を管理者トークンで呼び出す
        Then: レスポンスのCSVが18列のヘッダーを持ち、
              18列目に「商品名（処理用）」ヘッダーと
              「注文番号_商品番号」形式のデータが含まれる
        """
        shipment_id = shipment_for_csv_export["shipment_id"]
        expected_value = shipment_for_csv_export["expected_18th_column"]

        response = await client.post(
            "/api/v1/shipments/export-csv",
            json={"shipment_ids": [shipment_id]},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        # Parse CSV from response
        csv_text = response.content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        # Verify header (18 columns)
        header = rows[0]
        assert len(header) == 18, (
            f"Expected 18 header columns, got {len(header)}: {header}"
        )
        assert header[17] == "商品名（処理用）", (
            f"Expected header[17] to be '商品名（処理用）', got '{header[17]}'"
        )

        # Verify data row exists
        assert len(rows) >= 2, f"Expected at least 1 data row, got {len(rows) - 1}"

        # Verify 18th column data value
        data_row = rows[1]
        assert len(data_row) == 18, (
            f"Expected 18 data columns, got {len(data_row)}"
        )
        assert data_row[17] == expected_value, (
            f"Expected data_row[17] to be '{expected_value}', got '{data_row[17]}'"
        )
