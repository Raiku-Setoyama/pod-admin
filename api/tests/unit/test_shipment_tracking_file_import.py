"""Unit tests for shipment tracking file import (CSV/XLSX).

FEAT-0018: CSV/XLSXファイルによる伝票番号一括インポート機能

Tests verify file parsing logic, validation, and edge cases for the
import_tracking_from_file() method and generate_import_template() method
on ShipmentService.

AC-006: 必須列（注文番号、伝票番号）がないCSVはバリデーションエラー
AC-007: 空行はスキップされる
AC-008: 伝票番号が空の行はエラーとして報告される
AC-009: 運送会社名列が省略されている場合、carrierはnullのまま
AC-010: CSV/XLSX以外のファイルはバリデーションエラー
AC-011: 10MBを超えるファイルはバリデーションエラー
AC-013: Shift-JISエンコードのCSVも正しく解析できる
AC-017: 同一注文番号が複数行に存在する場合、最後の行の値で上書きされる
"""

import csv
import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order
from app.models.shipment import Shipment, ShipmentStatus
from app.services.shipment_service import ShipmentService

# ---- Fixtures ----


@pytest.fixture
def mock_shipment_repo() -> Any:
    """Mock shipment repository."""
    return AsyncMock()


@pytest.fixture
def mock_order_repo() -> Any:
    """Mock order repository."""
    return AsyncMock()


@pytest.fixture
def mock_file_storage() -> Any:
    """Mock file storage."""
    return AsyncMock()


@pytest.fixture
def mock_order_source_repo() -> Any:
    """Mock order source repository."""
    return AsyncMock()


@pytest.fixture
def shipment_service(
    mock_shipment_repo: Any, mock_order_repo: Any, mock_file_storage: Any, mock_order_source_repo: Any
) -> Any:
    """Create ShipmentService with mocked dependencies."""
    return ShipmentService(
        shipment_repo=mock_shipment_repo,
        order_repo=mock_order_repo,
        file_storage=mock_file_storage,
        order_source_repo=mock_order_source_repo,
    )


# ---- Helpers ----


def create_csv_bytes(
    rows: list[list[str]],
    encoding: str = "utf-8",
    bom: bool = False,
) -> bytes:
    """Create CSV content as bytes.

    Args:
        rows: List of rows (first row is header).
        encoding: Encoding to use (utf-8, shift_jis, etc.).
        bom: Whether to add UTF-8 BOM.

    Returns:
        CSV content as bytes.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(row)
    csv_text = output.getvalue()

    csv_bytes = csv_text.encode(encoding)
    if bom:
        csv_bytes = b"\xef\xbb\xbf" + csv_bytes
    return csv_bytes


def create_mock_upload_file(
    content: bytes,
    filename: str = "tracking.csv",
    content_type: str = "text/csv",
) -> MagicMock:
    """Create a mock UploadFile for testing.

    Args:
        content: File content as bytes.
        filename: Filename.
        content_type: MIME content type.

    Returns:
        Mock UploadFile object.
    """
    mock_file = MagicMock()
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.size = len(content)
    mock_file.read = AsyncMock(return_value=content)
    mock_file.seek = AsyncMock()
    return mock_file


def create_mock_order(
    order_id: str = "order-001",
    order_number: str = "ORD-001",
) -> MagicMock:
    """Create a mock Order."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.order_number = order_number
    return order


def create_mock_shipment(
    shipment_id: str = "shipment-001",
    tracking_number: str | None = None,
    carrier: str | None = None,
) -> MagicMock:
    """Create a mock Shipment."""
    shipment = MagicMock(spec=Shipment)
    shipment.id = shipment_id
    shipment.status = ShipmentStatus.PENDING.value
    shipment.tracking_number = tracking_number
    shipment.carrier = carrier
    shipment.items = []
    shipment.first_order = None
    return shipment


# ---- Tests ----


class TestImportTrackingFromFile:
    """Test ShipmentService.import_tracking_from_file()."""

    # ===========================================
    # AC-006: 必須列（注文番号、伝票番号）がないCSVはバリデーションエラー
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac006_missing_tracking_number_column_raises_validation_error(
        self, shipment_service: Any
    ) -> None:
        """AC-006: 「伝票番号」列がないCSVはバリデーションエラーになる.

        Given: ヘッダーが「注文番号」列のみのCSV
        When: ファイルを解析する
        Then: 「伝票番号」列が見つかりませんというバリデーションエラーが返される
        """
        csv_bytes = create_csv_bytes([
            ["注文番号"],
            ["ORD-001"],
        ])
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        with pytest.raises(Exception) as exc_info:
            await shipment_service.import_tracking_from_file(mock_file)

        assert "伝票番号" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ac006_missing_order_number_column_raises_validation_error(
        self, shipment_service: Any
    ) -> None:
        """AC-006: 「注文番号」列がないCSVはバリデーションエラーになる.

        Given: ヘッダーが「伝票番号」列のみのCSV
        When: ファイルを解析する
        Then: 「注文番号」列が見つかりませんというバリデーションエラーが返される
        """
        csv_bytes = create_csv_bytes([
            ["伝票番号"],
            ["1234-5678-9012"],
        ])
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        with pytest.raises(Exception) as exc_info:
            await shipment_service.import_tracking_from_file(mock_file)

        assert "注文番号" in str(exc_info.value)

    # ===========================================
    # AC-007: 空行はスキップされる
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac007_empty_rows_are_skipped(
        self, shipment_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-007: データ行の間に空行が含まれるCSVで空行は無視される.

        Given: データ行の間に空行が含まれるCSV
        When: ファイルを解析する
        Then: 空行は無視され、有効な行のみが処理される
        """
        # CSV with blank lines interspersed
        csv_text = "注文番号,伝票番号,運送会社名\nORD-001,1234-5678-9012,ヤマト運輸\n\n\nORD-002,2345-6789-0123,佐川急便\n"
        csv_bytes = csv_text.encode("utf-8")
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        # Set up mocks for the two valid orders
        order1 = create_mock_order("order-001", "ORD-001")
        order2 = create_mock_order("order-002", "ORD-002")
        mock_order_repo.find_by_order_number = AsyncMock(
            side_effect=lambda n: order1 if n == "ORD-001" else order2
        )

        shipment1 = create_mock_shipment("shipment-001")
        shipment2 = create_mock_shipment("shipment-002")
        mock_shipment_repo.find_by_order_ids = AsyncMock(
            return_value={"order-001": shipment1, "order-002": shipment2}
        )
        mock_shipment_repo.update = AsyncMock()

        result = await shipment_service.import_tracking_from_file(mock_file)

        # Only 2 valid rows should be processed (not 4 including blanks)
        assert result.total_count == 2
        assert result.success_count == 2
        assert result.error_count == 0

    # ===========================================
    # AC-008: 伝票番号が空の行はエラーとして報告される
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac008_empty_tracking_number_is_error(
        self, shipment_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-008: 伝票番号が空の行はエラーとして報告される.

        Given: 注文番号は入力されているが伝票番号が空の行
        When: ファイルを解析する
        Then: error_count=1、errorsに「伝票番号が空です」エラーが含まれる
        """
        csv_bytes = create_csv_bytes([
            ["注文番号", "伝票番号", "運送会社名"],
            ["ORD-001", "", "ヤマト運輸"],
        ])
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        result = await shipment_service.import_tracking_from_file(mock_file)

        assert result.error_count == 1
        assert len(result.errors) == 1
        assert "伝票番号" in result.errors[0].message
        assert result.errors[0].order_number == "ORD-001"

    # ===========================================
    # AC-009: 運送会社名列が省略されている場合、carrierはnullのまま
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac009_missing_carrier_column_sets_carrier_null(
        self, shipment_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-009: ヘッダーが「注文番号,伝票番号」のみのCSVで正常処理される.

        Given: ヘッダーが「注文番号,伝票番号」のみのCSV
        When: ファイルを解析する
        Then: 正常に処理され、carrierは更新されない（nullのまま）
        """
        csv_bytes = create_csv_bytes([
            ["注文番号", "伝票番号"],
            ["ORD-001", "1234-5678-9012"],
        ])
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        order = create_mock_order("order-001", "ORD-001")
        mock_order_repo.find_by_order_number = AsyncMock(return_value=order)

        shipment = create_mock_shipment("shipment-001")
        mock_shipment_repo.find_by_order_ids = AsyncMock(
            return_value={"order-001": shipment}
        )
        mock_shipment_repo.update = AsyncMock()

        result = await shipment_service.import_tracking_from_file(mock_file)

        assert result.success_count == 1
        assert result.error_count == 0
        # Verify carrier was not set (no carrier column)
        assert shipment.carrier is None

    # ===========================================
    # AC-010: CSV/XLSX以外のファイルはバリデーションエラー
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac010_unsupported_file_extension_raises_error(
        self, shipment_service: Any
    ) -> None:
        """AC-010: .txtファイルはバリデーションエラーになる.

        Given: .txtファイル
        When: POST /api/v1/shipments/importにアップロードする
        Then: 422エラー「対応していないファイル形式です。CSVまたはXLSXファイルをアップロードしてください」が返される
        """
        mock_file = create_mock_upload_file(
            b"some text data",
            filename="tracking.txt",
            content_type="text/plain",
        )

        with pytest.raises(Exception) as exc_info:
            await shipment_service.import_tracking_from_file(mock_file)

        error_msg = str(exc_info.value)
        assert "対応していないファイル形式" in error_msg or "CSV" in error_msg

    @pytest.mark.asyncio
    async def test_ac010_pdf_file_raises_error(
        self, shipment_service: Any
    ) -> None:
        """AC-010: .pdfファイルはバリデーションエラーになる."""
        mock_file = create_mock_upload_file(
            b"%PDF-1.4",
            filename="tracking.pdf",
            content_type="application/pdf",
        )

        with pytest.raises(Exception) as exc_info:
            await shipment_service.import_tracking_from_file(mock_file)

        error_msg = str(exc_info.value)
        assert "対応していないファイル形式" in error_msg or "CSV" in error_msg

    # ===========================================
    # AC-011: 10MBを超えるファイルはバリデーションエラー
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac011_file_over_10mb_raises_error(
        self, shipment_service: Any
    ) -> None:
        """AC-011: 11MBのCSVファイルはバリデーションエラーになる.

        Given: 11MBのCSVファイル
        When: POST /api/v1/shipments/importにアップロードする
        Then: 422エラー「ファイルサイズが上限（10MB）を超えています」が返される
        """
        # Create a file that reports 11MB
        large_content = b"x" * (11 * 1024 * 1024)
        mock_file = create_mock_upload_file(
            large_content,
            filename="tracking.csv",
            content_type="text/csv",
        )
        # Ensure mock reports the correct size
        mock_file.size = len(large_content)

        with pytest.raises(Exception) as exc_info:
            await shipment_service.import_tracking_from_file(mock_file)

        error_msg = str(exc_info.value)
        assert "ファイルサイズ" in error_msg or "10MB" in error_msg

    @pytest.mark.asyncio
    async def test_ac011_file_exactly_10mb_is_accepted(
        self, shipment_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-011: 10MB以下のファイルはサイズバリデーションを通過する."""
        csv_bytes = create_csv_bytes([
            ["注文番号", "伝票番号"],
            ["ORD-001", "1234-5678-9012"],
        ])
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")
        # Exactly 10MB
        mock_file.size = 10 * 1024 * 1024

        order = create_mock_order("order-001", "ORD-001")
        mock_order_repo.find_by_order_number = AsyncMock(return_value=order)

        shipment = create_mock_shipment("shipment-001")
        mock_shipment_repo.find_by_order_ids = AsyncMock(
            return_value={"order-001": shipment}
        )
        mock_shipment_repo.update = AsyncMock()

        # Should succeed (not raise file size error)
        result = await shipment_service.import_tracking_from_file(mock_file)

        # The method should exist and return a result
        assert result.success_count == 1

    # ===========================================
    # AC-013: Shift-JISエンコードのCSVも正しく解析できる
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac013_shift_jis_csv_is_parsed_correctly(
        self, shipment_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-013: Shift-JISでエンコードされたCSVが正しく解析される.

        Given: Shift-JISでエンコードされたCSV
        When: ファイルを解析する
        Then: 日本語の注文番号・運送会社名が正しく読み取れる
        """
        csv_bytes = create_csv_bytes(
            [
                ["注文番号", "伝票番号", "運送会社名"],
                ["ORD-001", "1234-5678-9012", "ヤマト運輸"],
            ],
            encoding="shift_jis",
        )
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        order = create_mock_order("order-001", "ORD-001")
        mock_order_repo.find_by_order_number = AsyncMock(return_value=order)

        shipment = create_mock_shipment("shipment-001")
        mock_shipment_repo.find_by_order_ids = AsyncMock(
            return_value={"order-001": shipment}
        )
        mock_shipment_repo.update = AsyncMock()

        result = await shipment_service.import_tracking_from_file(mock_file)

        assert result.success_count == 1
        assert result.error_count == 0
        # Verify the tracking number was correctly parsed from Shift-JIS
        assert shipment.tracking_number == "1234-5678-9012"
        assert shipment.carrier == "ヤマト運輸"

    @pytest.mark.asyncio
    async def test_ac013_utf8_bom_csv_is_parsed_correctly(
        self, shipment_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-013: UTF-8 BOM付きCSVが正しく解析される."""
        csv_bytes = create_csv_bytes(
            [
                ["注文番号", "伝票番号", "運送会社名"],
                ["ORD-001", "1234-5678-9012", "佐川急便"],
            ],
            encoding="utf-8",
            bom=True,
        )
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        order = create_mock_order("order-001", "ORD-001")
        mock_order_repo.find_by_order_number = AsyncMock(return_value=order)

        shipment = create_mock_shipment("shipment-001")
        mock_shipment_repo.find_by_order_ids = AsyncMock(
            return_value={"order-001": shipment}
        )
        mock_shipment_repo.update = AsyncMock()

        result = await shipment_service.import_tracking_from_file(mock_file)

        assert result.success_count == 1
        assert shipment.tracking_number == "1234-5678-9012"
        assert shipment.carrier == "佐川急便"

    # ===========================================
    # AC-017: 同一注文番号が複数行に存在する場合、最後の行の値で上書きされる
    # ===========================================

    @pytest.mark.asyncio
    async def test_ac017_duplicate_order_number_last_write_wins(
        self, shipment_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-017: 同じ注文番号が2行あると最後の行の伝票番号で更新される.

        Given: 同じ注文番号"ORD-001"が2行存在し、伝票番号がそれぞれ異なる
        When: ファイルを解析・処理する
        Then: 最後の行の伝票番号で更新される（警告なし）
        """
        csv_bytes = create_csv_bytes([
            ["注文番号", "伝票番号", "運送会社名"],
            ["ORD-001", "FIRST-TRACKING", "ヤマト運輸"],
            ["ORD-001", "LAST-TRACKING", "佐川急便"],
        ])
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        order = create_mock_order("order-001", "ORD-001")
        mock_order_repo.find_by_order_number = AsyncMock(return_value=order)

        shipment = create_mock_shipment("shipment-001")
        mock_shipment_repo.find_by_order_ids = AsyncMock(
            return_value={"order-001": shipment}
        )
        mock_shipment_repo.update = AsyncMock()

        result = await shipment_service.import_tracking_from_file(mock_file)

        # Both rows count as processed for the same order
        assert result.total_count == 2
        # The shipment should have the LAST tracking number
        assert shipment.tracking_number == "LAST-TRACKING"
        assert shipment.carrier == "佐川急便"

    # ===========================================
    # Additional: 「運送会社」ヘッダー名のバリエーション
    # ===========================================

    @pytest.mark.asyncio
    async def test_carrier_column_alternative_name_accepted(
        self, shipment_service: Any, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """運送会社名列のヘッダーが「運送会社」でも許容される.

        Spec assumption: 運送会社名の列ヘッダーは「運送会社名」「運送会社」のいずれも許容する
        """
        csv_bytes = create_csv_bytes([
            ["注文番号", "伝票番号", "運送会社"],
            ["ORD-001", "1234-5678-9012", "日本郵便"],
        ])
        mock_file = create_mock_upload_file(csv_bytes, filename="tracking.csv")

        order = create_mock_order("order-001", "ORD-001")
        mock_order_repo.find_by_order_number = AsyncMock(return_value=order)

        shipment = create_mock_shipment("shipment-001")
        mock_shipment_repo.find_by_order_ids = AsyncMock(
            return_value={"order-001": shipment}
        )
        mock_shipment_repo.update = AsyncMock()

        result = await shipment_service.import_tracking_from_file(mock_file)

        assert result.success_count == 1
        assert shipment.carrier == "日本郵便"


class TestGenerateImportTemplate:
    """Test ShipmentService.generate_import_template()."""

    # ===========================================
    # AC-012 (partial): テンプレートCSV生成
    # ===========================================

    @pytest.mark.asyncio
    async def test_template_has_correct_headers(self, shipment_service: Any) -> None:
        """テンプレートCSVのヘッダー行が正しい.

        Given: ShipmentService.generate_import_template() が呼び出される
        When: テンプレートCSVを生成する
        Then: ヘッダー行「注文番号,伝票番号,運送会社名」が含まれる
        """
        csv_bytes, filename = await shipment_service.generate_import_template()

        # Parse the CSV
        csv_text = csv_bytes.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        # Verify header
        assert len(rows) >= 1
        assert rows[0] == ["注文番号", "伝票番号", "運送会社名"]

    @pytest.mark.asyncio
    async def test_template_has_sample_data_row(self, shipment_service: Any) -> None:
        """テンプレートCSVにサンプルデータ行が含まれる.

        Given: ShipmentService.generate_import_template() が呼び出される
        When: テンプレートCSVを生成する
        Then: ヘッダー行に加えてサンプルデータ行が1行含まれる
        """
        csv_bytes, filename = await shipment_service.generate_import_template()

        csv_text = csv_bytes.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        # Header + at least 1 sample data row
        assert len(rows) >= 2, f"Expected at least 2 rows (header + sample), got {len(rows)}"
        # Sample row should have 3 columns
        assert len(rows[1]) == 3, f"Expected 3 columns in sample row, got {len(rows[1])}"

    @pytest.mark.asyncio
    async def test_template_is_utf8_bom(self, shipment_service: Any) -> None:
        """テンプレートCSVがUTF-8 BOM付きである.

        Given: ShipmentService.generate_import_template() が呼び出される
        When: テンプレートCSVを生成する
        Then: UTF-8 BOM付きCSVファイルが返される
        """
        csv_bytes, filename = await shipment_service.generate_import_template()

        # Check for UTF-8 BOM
        assert csv_bytes[:3] == b"\xef\xbb\xbf", "Expected UTF-8 BOM at start of file"

    @pytest.mark.asyncio
    async def test_template_filename_is_csv(self, shipment_service: Any) -> None:
        """テンプレートのファイル名が.csv拡張子である."""
        csv_bytes, filename = await shipment_service.generate_import_template()

        assert filename.endswith(".csv"), f"Expected .csv extension, got '{filename}'"
