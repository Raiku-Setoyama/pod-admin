"""Integration tests for shipment tracking file import (CSV/XLSX).

FEAT-0018: CSV/XLSXファイルによる伝票番号一括インポート機能

Tests the full flow through API -> Service -> Repository -> Database,
verifying that the imported tracking numbers are correctly persisted.

AC-001: CSVファイル（UTF-8）アップロードで伝票番号・運送会社が更新される
AC-002: XLSXファイルアップロードでも同様に更新される
AC-003: 複数行のCSVで一括更新ができる
AC-004: 存在しない注文番号の行はエラー、他の行は正常処理
AC-005: shipmentが紐づいていない注文番号の行はエラー
AC-012: GET /api/v1/shipments/import-templateでサンプルCSVテンプレートがダウンロードできる
"""

import csv
import io
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---- Helpers ----


def create_csv_bytes(
    rows: list[list[str]],
    encoding: str = "utf-8",
    bom: bool = False,
) -> bytes:
    """Create CSV content as bytes."""
    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(row)
    csv_text = output.getvalue()

    csv_bytes = csv_text.encode(encoding)
    if bom:
        csv_bytes = b"\xef\xbb\xbf" + csv_bytes
    return csv_bytes


# ---- Fixtures ----


@pytest.fixture
async def order_with_shipment(db_session: AsyncSession, test_order_source: dict):
    """テスト用の注文 + 配送データ（shipment紐づき済み）

    注文番号 "FEAT18-{uuid[:8]}" で作成し、shipmentと紐づけます。
    """
    order_id = str(uuid4())
    order_number = f"FEAT18-{order_id[:8]}"
    shipment_id = str(uuid4())
    shipment_item_id = str(uuid4())

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
            "order_number": order_number,
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product",
            "quantity": 1,
            "customer_name": "FEAT-0018 Customer",
            "customer_email": "feat0018@example.com",
            "customer_phone": "090-0018-0018",
            "customer_postal_code": "100-0018",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区テスト18-1",
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
        "order_id": order_id,
        "order_number": order_number,
        "shipment_id": shipment_id,
    }


@pytest.fixture
async def multiple_orders_with_shipments(
    db_session: AsyncSession, test_order_source: dict
):
    """テスト用の3件の注文 + 配送データ"""
    orders = []
    for i in range(3):
        order_id = str(uuid4())
        order_number = f"FEAT18-MULTI-{i+1}-{order_id[:8]}"
        shipment_id = str(uuid4())
        shipment_item_id = str(uuid4())

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
                "product_name": f"Test Product {i+1}",
                "quantity": 1,
                "customer_name": f"Customer {i+1}",
                "customer_email": f"customer{i+1}@example.com",
                "customer_phone": f"090-0000-{i+1:04d}",
                "customer_postal_code": f"100-{i+1:04d}",
                "customer_address_prefecture": "東京都",
                "customer_address_city": f"千代田区テスト{i+1}",
                "status": "delivered",
            },
        )

        await db_session.execute(
            text("""
                INSERT INTO shipments (id, status, created_at, updated_at)
                VALUES (:id, :status, NOW(), NOW())
            """),
            {"id": shipment_id, "status": "pending"},
        )

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

        orders.append({
            "order_id": order_id,
            "order_number": order_number,
            "shipment_id": shipment_id,
        })

    await db_session.commit()
    yield orders


@pytest.fixture
async def order_without_shipment(db_session: AsyncSession, test_order_source: dict):
    """テスト用の注文（shipment紐づきなし）"""
    order_id = str(uuid4())
    order_number = f"FEAT18-NOSHIP-{order_id[:8]}"

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
            "product_name": "Test Product No Ship",
            "quantity": 1,
            "customer_name": "No Ship Customer",
            "customer_email": "noship@example.com",
            "customer_phone": "090-0000-9999",
            "customer_postal_code": "100-9999",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区テスト9999",
            "status": "delivered",
        },
    )
    await db_session.commit()

    yield {
        "order_id": order_id,
        "order_number": order_number,
    }


class TestImportTrackingFileAPI:
    """Integration tests for POST /api/v1/shipments/import."""

    # ===========================================
    # AC-001: CSVファイル（UTF-8）で伝票番号・運送会社が更新される
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac001_csv_upload_updates_tracking_and_carrier(
        self,
        client: AsyncClient,
        auth_headers: dict,
        order_with_shipment: dict,
        db_session: AsyncSession,
    ):
        """AC-001: CSVファイルで伝票番号・運送会社が更新される.

        Given: shipmentが存在し、注文番号に紐づいている
        When: 注文番号、伝票番号"1234-5678-9012"、運送会社名"ヤマト運輸"のCSVをPOSTする
        Then: 対応するshipmentのtracking_numberとcarrierが更新される
        """
        order_number = order_with_shipment["order_number"]
        shipment_id = order_with_shipment["shipment_id"]

        csv_bytes = create_csv_bytes([
            ["注文番号", "伝票番号", "運送会社名"],
            [order_number, "1234-5678-9012", "ヤマト運輸"],
        ])

        response = await client.post(
            "/api/v1/shipments/import",
            headers=auth_headers,
            files={"file": ("tracking.csv", csv_bytes, "text/csv")},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        data = response.json()
        assert data["success_count"] == 1
        assert data["error_count"] == 0

        # Verify DB was updated
        result = await db_session.execute(
            text("SELECT tracking_number, carrier FROM shipments WHERE id = :id"),
            {"id": shipment_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "1234-5678-9012"
        assert row[1] == "ヤマト運輸"

    # ===========================================
    # AC-002: XLSXファイルで同様に更新される
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac002_xlsx_upload_updates_tracking_and_carrier(
        self,
        client: AsyncClient,
        auth_headers: dict,
        order_with_shipment: dict,
        db_session: AsyncSession,
    ):
        """AC-002: XLSXファイルで伝票番号・運送会社が更新される.

        Given: shipmentが存在し、注文番号に紐づいている
        When: 同内容のXLSXファイルをPOST /api/v1/shipments/importにアップロードする
        Then: CSVと同じ結果になる
        """
        import openpyxl

        order_number = order_with_shipment["order_number"]
        shipment_id = order_with_shipment["shipment_id"]

        # Create XLSX in memory
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["注文番号", "伝票番号", "運送会社名"])
        ws.append([order_number, "XLSX-TRACK-001", "佐川急便"])

        xlsx_buffer = io.BytesIO()
        wb.save(xlsx_buffer)
        xlsx_bytes = xlsx_buffer.getvalue()

        response = await client.post(
            "/api/v1/shipments/import",
            headers=auth_headers,
            files={
                "file": (
                    "tracking.xlsx",
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        data = response.json()
        assert data["success_count"] == 1
        assert data["error_count"] == 0

        # Verify DB was updated
        result = await db_session.execute(
            text("SELECT tracking_number, carrier FROM shipments WHERE id = :id"),
            {"id": shipment_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "XLSX-TRACK-001"
        assert row[1] == "佐川急便"

    # ===========================================
    # AC-003: 複数行のCSVで一括更新ができる
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac003_multiple_rows_bulk_update(
        self,
        client: AsyncClient,
        auth_headers: dict,
        multiple_orders_with_shipments: list[dict],
        db_session: AsyncSession,
    ):
        """AC-003: 3行のCSVで3件すべてのshipmentが更新される.

        Given: 3件のshipmentが存在する
        When: 3行のCSVをアップロードする
        Then: 3件すべてのshipmentが更新され、success_count=3が返される
        """
        orders = multiple_orders_with_shipments

        csv_rows = [["注文番号", "伝票番号", "運送会社名"]]
        for i, order in enumerate(orders):
            csv_rows.append([
                order["order_number"],
                f"TRACK-{i+1:04d}",
                "ヤマト運輸",
            ])

        csv_bytes = create_csv_bytes(csv_rows)

        response = await client.post(
            "/api/v1/shipments/import",
            headers=auth_headers,
            files={"file": ("tracking.csv", csv_bytes, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 3
        assert data["error_count"] == 0
        assert data["total_count"] == 3

        # Verify all 3 shipments were updated
        for i, order in enumerate(orders):
            result = await db_session.execute(
                text("SELECT tracking_number FROM shipments WHERE id = :id"),
                {"id": order["shipment_id"]},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == f"TRACK-{i+1:04d}", (
                f"Expected TRACK-{i+1:04d} for shipment {order['shipment_id']}, got {row[0]}"
            )

    # ===========================================
    # AC-004: 存在しない注文番号の行はエラー、他は正常処理
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac004_nonexistent_order_number_partial_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        order_with_shipment: dict,
    ):
        """AC-004: 存在しない注文番号の行はエラー、他の行は正常処理.

        Given: "ORD-001"は存在するが"ORD-999"は存在しない
        When: 2行のCSV（ORD-001とORD-999）をアップロードする
        Then: success_count=1、error_count=1、errorsにORD-999のエラーが含まれる
        """
        order_number = order_with_shipment["order_number"]
        nonexistent_order = "NONEXISTENT-ORD-999"

        csv_bytes = create_csv_bytes([
            ["注文番号", "伝票番号", "運送会社名"],
            [order_number, "VALID-TRACK-001", "ヤマト運輸"],
            [nonexistent_order, "INVALID-TRACK-001", "佐川急便"],
        ])

        response = await client.post(
            "/api/v1/shipments/import",
            headers=auth_headers,
            files={"file": ("tracking.csv", csv_bytes, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 1
        assert data["error_count"] == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["order_number"] == nonexistent_order

    # ===========================================
    # AC-005: shipmentが紐づいていない注文番号の行はエラー
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac005_order_without_shipment_is_error(
        self,
        client: AsyncClient,
        auth_headers: dict,
        order_without_shipment: dict,
    ):
        """AC-005: shipmentが紐づいていない注文番号はエラー.

        Given: 注文は存在するがshipmentが紐づいていない
        When: その注文番号を含むCSVをアップロードする
        Then: error_count=1、errorsに「配送レコードが存在しません」エラーが含まれる
        """
        order_number = order_without_shipment["order_number"]

        csv_bytes = create_csv_bytes([
            ["注文番号", "伝票番号", "運送会社名"],
            [order_number, "TRACK-NOSHIP", "ヤマト運輸"],
        ])

        response = await client.post(
            "/api/v1/shipments/import",
            headers=auth_headers,
            files={"file": ("tracking.csv", csv_bytes, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error_count"] == 1
        assert len(data["errors"]) == 1
        # Error message should mention missing shipment
        error_msg = data["errors"][0]["message"]
        assert "配送" in error_msg or "shipment" in error_msg.lower()


class TestImportTemplateAPI:
    """Integration tests for GET /api/v1/shipments/import-template."""

    # ===========================================
    # AC-012: テンプレートCSVがダウンロードできる
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac012_import_template_download(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """AC-012: GET /api/v1/shipments/import-templateでテンプレートCSVがダウンロードできる.

        Given: 認証済み管理者
        When: GET /api/v1/shipments/import-templateにリクエストする
        Then: UTF-8 BOM付きCSVファイルが返され、正しいヘッダーとサンプルデータが含まれる
        """
        response = await client.get(
            "/api/v1/shipments/import-template",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        # Verify content type is CSV
        content_type = response.headers.get("content-type", "")
        assert "csv" in content_type.lower() or "text" in content_type.lower(), (
            f"Expected CSV content type, got: {content_type}"
        )

        # Verify Content-Disposition header
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition.lower(), (
            f"Expected attachment disposition, got: {content_disposition}"
        )

        # Verify UTF-8 BOM
        content = response.content
        assert content[:3] == b"\xef\xbb\xbf", "Expected UTF-8 BOM"

        # Parse CSV content
        csv_text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        # Verify header row
        assert len(rows) >= 2, f"Expected header + sample row, got {len(rows)} rows"
        assert rows[0] == ["注文番号", "伝票番号", "運送会社名"], (
            f"Expected correct header, got: {rows[0]}"
        )

        # Verify sample data row exists with 3 columns
        assert len(rows[1]) == 3, (
            f"Expected 3 columns in sample row, got {len(rows[1])}"
        )

    @pytest.mark.asyncio
    async def test_ac012_import_template_requires_auth(
        self,
        client: AsyncClient,
    ):
        """テンプレートダウンロードには認証が必要."""
        response = await client.get("/api/v1/shipments/import-template")

        assert response.status_code == 401 or response.status_code == 403, (
            f"Expected 401/403 without auth, got {response.status_code}"
        )
