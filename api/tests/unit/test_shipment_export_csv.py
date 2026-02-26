"""Unit tests for ShipmentService.export_csv() - 18th column addition.

FEAT-0017: Add "商品名（処理用）" column to shipment CSV export.
Tests verify that the 18th column is correctly added to both the header
and data rows with the format "{order_number}_{uid}".

AC-001: Header 18th column is "商品名（処理用）"
AC-002: Data row 18th column is "{order_number}_{uid}" format
AC-003: Multiple OrderItems produce correct values per row
AC-004: uid=None produces "{order_number}_"
AC-005: Existing 17 columns remain unchanged
"""

import csv
import io
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderItem
from app.models.order_source import OrderSource
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.services.shipment_service import ShipmentService

# ---- Existing 17 header columns (must not change) ----
EXPECTED_17_HEADERS = [
    "注文番号",
    "お客様氏名",
    "商品名",
    "商品種類",
    "数量",
    "商品番号",
    "お届け先電話番号",
    "お届け先郵便番号",
    "お届け先住所1(都道府県)",
    "お届け先住所2(市区町村番地以下)",
    "お届け先住所3(建物名等)",
    "配送元電話番号",
    "配送元郵便番号",
    "配送元住所1(都道府県)",
    "配送元住所2(市区町村番地以下)",
    "配送元住所3(建物名等)",
    "配送元氏名",
]


# ---- Fixtures ----


@pytest.fixture
def mock_shipment_repo():
    """Mock shipment repository."""
    return AsyncMock()


@pytest.fixture
def mock_order_repo():
    """Mock order repository."""
    return AsyncMock()


@pytest.fixture
def mock_file_storage():
    """Mock file storage."""
    return AsyncMock()


@pytest.fixture
def mock_order_source_repo():
    """Mock order source repository."""
    return AsyncMock()


@pytest.fixture
def shipment_service(
    mock_shipment_repo, mock_order_repo, mock_file_storage, mock_order_source_repo
):
    """Create ShipmentService with mocked dependencies."""
    return ShipmentService(
        shipment_repo=mock_shipment_repo,
        order_repo=mock_order_repo,
        file_storage=mock_file_storage,
        order_source_repo=mock_order_source_repo,
    )


def create_mock_order_source() -> MagicMock:
    """Create a mock OrderSource with sender info."""
    source = MagicMock(spec=OrderSource)
    source.name = "テスト配送元"
    source.phone = "03-1234-5678"
    source.postal_code = "100-0001"
    source.address_prefecture = "東京都"
    source.address_city = "千代田区1-1-1"
    source.address_building = "テストビル101"
    return source


def create_mock_order_item(
    product_name: str = "テスト商品",
    product_type: str = "acrylic_keychain",
    quantity: int = 1,
    uid: str | None = "ITEM-001",
) -> MagicMock:
    """Create a mock OrderItem."""
    item = MagicMock(spec=OrderItem)
    item.product_name = product_name
    item.product_type = product_type
    item.quantity = quantity
    item.uid = uid
    return item


def create_mock_order(
    order_id: str = "order-001",
    order_number: str = "ORD-0001",
    order_items: list[MagicMock] | None = None,
    order_source: MagicMock | None = None,
) -> MagicMock:
    """Create a mock Order with customer info."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.order_number = order_number
    order.customer_name = "テスト顧客"
    order.customer_phone = "090-0000-0000"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "東京都"
    order.customer_address_city = "千代田区1-1-1"
    order.customer_address_building = ""
    order.items = order_items if order_items is not None else []
    order.order_source = order_source
    return order


def create_mock_shipment(
    shipment_id: str = "shipment-001",
    shipment_items: list[tuple[str, MagicMock | None]] | None = None,
) -> MagicMock:
    """Create a mock Shipment.

    Args:
        shipment_id: The shipment ID.
        shipment_items: List of (item_id, order_mock_or_none) tuples.
    """
    shipment = MagicMock(spec=Shipment)
    shipment.id = shipment_id
    shipment.status = ShipmentStatus.PENDING.value
    shipment.items = []

    if shipment_items:
        for item_id, order in shipment_items:
            si = MagicMock(spec=ShipmentItem)
            si.id = item_id
            si.order_id = order.id if order else "unknown"
            si.order = order
            shipment.items.append(si)

    if shipment.items and shipment.items[0].order:
        shipment.first_order = shipment.items[0].order
    else:
        shipment.first_order = None

    return shipment


def parse_csv_bytes(csv_bytes: bytes) -> tuple[list[str], list[list[str]]]:
    """Parse CSV bytes (with BOM) into header and data rows.

    Returns:
        Tuple of (header_list, list_of_data_rows)
    """
    # Remove UTF-8 BOM
    csv_text = csv_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    header = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []
    return header, data_rows


# ---- Tests ----


class TestShipmentExportCsvColumn18:
    """Test 18th column ('商品名（処理用）') in ShipmentService.export_csv()."""

    # ===========================================
    # AC-001: Header 18th column is "商品名（処理用）"
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac001_header_18th_column_is_processing_product_name(
        self, shipment_service, mock_shipment_repo
    ):
        """AC-001: CSVヘッダーの18列目に「商品名（処理用）」が含まれる.

        Given: ShipmentService.export_csv() が呼び出される
        When: CSVヘッダー行を確認する
        Then: ヘッダーの18列目が「商品名（処理用）」である
        """
        # Arrange
        order_source = create_mock_order_source()
        order_item = create_mock_order_item(uid="ITEM-001")
        order = create_mock_order(
            order_number="ORD-0001",
            order_items=[order_item],
            order_source=order_source,
        )
        shipment = create_mock_shipment(
            shipment_items=[("si-001", order)],
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        # Act
        csv_bytes, _ = await shipment_service.export_csv(["shipment-001"])

        # Assert
        header, _ = parse_csv_bytes(csv_bytes)
        assert len(header) == 18, f"Expected 18 columns, got {len(header)}: {header}"
        assert header[17] == "商品名（処理用）", (
            f"Expected header[17] to be '商品名（処理用）', got '{header[17]}'"
        )

    # ===========================================
    # AC-002: Data row 18th column is "{order_number}_{uid}"
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac002_data_row_18th_column_order_number_uid(
        self, shipment_service, mock_shipment_repo
    ):
        """AC-002: CSVデータ行の18列目に「注文番号_商品番号」形式の値が出力される.

        Given: 注文番号 "ORD-0001"、商品番号（uid） "ITEM-001" の OrderItem を持つ
               Shipment が存在する
        When: ShipmentService.export_csv() でCSVを生成する
        Then: データ行の18列目の値が "ORD-0001_ITEM-001" である
        """
        # Arrange
        order_source = create_mock_order_source()
        order_item = create_mock_order_item(uid="ITEM-001")
        order = create_mock_order(
            order_number="ORD-0001",
            order_items=[order_item],
            order_source=order_source,
        )
        shipment = create_mock_shipment(
            shipment_items=[("si-001", order)],
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        # Act
        csv_bytes, _ = await shipment_service.export_csv(["shipment-001"])

        # Assert
        _, data_rows = parse_csv_bytes(csv_bytes)
        assert len(data_rows) == 1
        assert len(data_rows[0]) == 18, (
            f"Expected 18 columns in data row, got {len(data_rows[0])}"
        )
        assert data_rows[0][17] == "ORD-0001_ITEM-001", (
            f"Expected data_rows[0][17] to be 'ORD-0001_ITEM-001', got '{data_rows[0][17]}'"
        )

    # ===========================================
    # AC-003: Multiple OrderItems produce correct values per row
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac003_multiple_order_items_each_row_has_correct_value(
        self, shipment_service, mock_shipment_repo
    ):
        """AC-003: 複数OrderItemがある場合、各行にそれぞれの「注文番号_商品番号」が出力される.

        Given: 1つの注文に2つのOrderItem（uid: "ITEM-001", "ITEM-002"）が
               含まれるShipmentが存在する
        When: ShipmentService.export_csv() でCSVを生成する
        Then: 2行のデータ行が出力され、それぞれの18列目が
              "ORD-0001_ITEM-001" と "ORD-0001_ITEM-002" である
        """
        # Arrange
        order_source = create_mock_order_source()
        order_item_1 = create_mock_order_item(
            product_name="商品A", uid="ITEM-001"
        )
        order_item_2 = create_mock_order_item(
            product_name="商品B", uid="ITEM-002"
        )
        order = create_mock_order(
            order_number="ORD-0001",
            order_items=[order_item_1, order_item_2],
            order_source=order_source,
        )
        shipment = create_mock_shipment(
            shipment_items=[("si-001", order)],
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        # Act
        csv_bytes, _ = await shipment_service.export_csv(["shipment-001"])

        # Assert
        _, data_rows = parse_csv_bytes(csv_bytes)
        assert len(data_rows) == 2, (
            f"Expected 2 data rows, got {len(data_rows)}"
        )
        assert data_rows[0][17] == "ORD-0001_ITEM-001", (
            f"Expected data_rows[0][17] to be 'ORD-0001_ITEM-001', got '{data_rows[0][17]}'"
        )
        assert data_rows[1][17] == "ORD-0001_ITEM-002", (
            f"Expected data_rows[1][17] to be 'ORD-0001_ITEM-002', got '{data_rows[1][17]}'"
        )

    # ===========================================
    # AC-004: uid=None produces "{order_number}_"
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac004_uid_none_produces_order_number_with_underscore(
        self, shipment_service, mock_shipment_repo
    ):
        """AC-004: OrderItem.uid が null の場合、注文番号のみ + アンダースコアが出力される.

        Given: OrderItem.uid が None の OrderItem を持つ Shipment が存在する
        When: ShipmentService.export_csv() でCSVを生成する
        Then: データ行の18列目の値が "ORD-0001_" である
        """
        # Arrange
        order_source = create_mock_order_source()
        order_item = create_mock_order_item(uid=None)
        order = create_mock_order(
            order_number="ORD-0001",
            order_items=[order_item],
            order_source=order_source,
        )
        shipment = create_mock_shipment(
            shipment_items=[("si-001", order)],
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        # Act
        csv_bytes, _ = await shipment_service.export_csv(["shipment-001"])

        # Assert
        _, data_rows = parse_csv_bytes(csv_bytes)
        assert len(data_rows) == 1
        assert data_rows[0][17] == "ORD-0001_", (
            f"Expected data_rows[0][17] to be 'ORD-0001_', got '{data_rows[0][17]}'"
        )

    # ===========================================
    # AC-005: Existing 17 columns are unchanged
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac005_existing_17_columns_unchanged(
        self, shipment_service, mock_shipment_repo
    ):
        """AC-005: 既存の17列のヘッダーと値が変更されていない.

        Given: ShipmentService.export_csv() が呼び出される
        When: CSVの1〜17列目を確認する
        Then: 既存の17列のヘッダー名と値が変更前と同一である
        """
        # Arrange
        order_source = create_mock_order_source()
        order_item = create_mock_order_item(
            product_name="テスト商品",
            product_type="acrylic_keychain",
            quantity=2,
            uid="ITEM-001",
        )
        order = create_mock_order(
            order_number="ORD-0001",
            order_items=[order_item],
            order_source=order_source,
        )
        shipment = create_mock_shipment(
            shipment_items=[("si-001", order)],
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        # Act
        csv_bytes, _ = await shipment_service.export_csv(["shipment-001"])

        # Assert - Header columns 1-17
        header, data_rows = parse_csv_bytes(csv_bytes)
        assert header[:17] == EXPECTED_17_HEADERS, (
            f"First 17 headers changed!\nExpected: {EXPECTED_17_HEADERS}\nGot: {header[:17]}"
        )

        # Assert - Data row columns 1-17 have expected values
        assert len(data_rows) == 1
        row = data_rows[0]
        assert row[0] == "ORD-0001"  # 注文番号
        assert row[1] == "テスト顧客"  # お客様氏名
        assert row[2] == "テスト商品"  # 商品名
        assert row[3] == "アクリルキーホルダー"  # 商品種類
        assert row[4] == "2"  # 数量
        assert row[5] == "ITEM-001"  # 商品番号
        assert row[6] == "090-0000-0000"  # お届け先電話番号
        assert row[7] == "100-0001"  # お届け先郵便番号
        assert row[8] == "東京都"  # お届け先住所1
        assert row[9] == "千代田区1-1-1"  # お届け先住所2
        assert row[10] == ""  # お届け先住所3
        assert row[11] == "03-1234-5678"  # 配送元電話番号
        assert row[12] == "100-0001"  # 配送元郵便番号
        assert row[13] == "東京都"  # 配送元住所1
        assert row[14] == "千代田区1-1-1"  # 配送元住所2
        assert row[15] == "テストビル101"  # 配送元住所3
        assert row[16] == "テスト配送元"  # 配送元氏名
