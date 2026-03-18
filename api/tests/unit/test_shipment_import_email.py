"""Unit tests for shipment import with email notification.

Tests the email sending logic integrated into import_tracking_from_file(),
including status updates, duplicate prevention, and edge cases.
"""

import io
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from app.models.order import Order, OrderItem, OrderStatus
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.services.shipment_service import ShipmentService


# ---- Helpers ----


def make_csv_file(rows: list[list[str]]) -> MagicMock:
    """Create a mock UploadFile with CSV content."""
    import csv

    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(row)
    csv_bytes = output.getvalue().encode("utf-8")

    file = MagicMock()
    file.filename = "test.csv"
    file.size = len(csv_bytes)
    file.read = AsyncMock(return_value=csv_bytes)
    return file


def make_order(
    order_id: str = "order-001",
    order_number: str = "ORD-0001",
    customer_email: str | None = "customer@example.com",
    customer_name: str = "テスト顧客",
    status: str = "delivered",
    items: list | None = None,
) -> MagicMock:
    """Create a mock Order."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.order_number = order_number
    order.customer_email = customer_email
    order.customer_name = customer_name
    order.status = status

    if items is None:
        item = MagicMock(spec=OrderItem)
        item.product_name = "テスト商品"
        item.quantity = 1
        item.thumbnail_image_url = "https://example.com/thumb.png"
        order.items = [item]
    else:
        order.items = items

    return order


def make_shipment(
    shipment_id: str = "shipment-001",
    order_id: str = "order-001",
    shipping_email_sent: bool = False,
) -> MagicMock:
    """Create a mock Shipment."""
    shipment = MagicMock(spec=Shipment)
    shipment.id = shipment_id
    shipment.status = ShipmentStatus.PENDING.value
    shipment.tracking_number = None
    shipment.carrier = None
    shipment.shipped_at = None
    shipment.shipping_email_sent = shipping_email_sent

    si = MagicMock(spec=ShipmentItem)
    si.order_id = order_id
    shipment.items = [si]

    return shipment


@pytest.fixture
def mock_repos():
    """Create mock repositories."""
    return {
        "shipment_repo": AsyncMock(),
        "order_repo": AsyncMock(),
        "file_storage": AsyncMock(),
        "order_source_repo": AsyncMock(),
    }


@pytest.fixture
def mock_email_service():
    """Create mock email service."""
    service = AsyncMock()
    service.send_shipping_notification = AsyncMock(return_value=True)
    return service


@pytest.fixture
def service_with_email(mock_repos, mock_email_service):
    """ShipmentService with email service."""
    return ShipmentService(
        shipment_repo=mock_repos["shipment_repo"],
        order_repo=mock_repos["order_repo"],
        file_storage=mock_repos["file_storage"],
        order_source_repo=mock_repos["order_source_repo"],
        email_service=mock_email_service,
    )


@pytest.fixture
def service_without_email(mock_repos):
    """ShipmentService without email service."""
    return ShipmentService(
        shipment_repo=mock_repos["shipment_repo"],
        order_repo=mock_repos["order_repo"],
        file_storage=mock_repos["file_storage"],
        order_source_repo=mock_repos["order_source_repo"],
        email_service=None,
    )


class TestImportTrackingWithEmail:
    """Test import_tracking_from_file with email notifications."""

    @pytest.mark.asyncio
    async def test_sends_email_on_successful_import(
        self, service_with_email, mock_repos, mock_email_service
    ):
        """Email is sent when import succeeds and customer has email."""
        order = make_order()
        shipment = make_shipment()

        mock_repos["order_repo"].find_by_order_number.return_value = order
        mock_repos["shipment_repo"].find_by_order_ids.return_value = {order.id: shipment}

        file = make_csv_file([
            ["注文番号", "伝票番号", "運送会社名"],
            ["ORD-0001", "1234-5678", "ヤマト運輸"],
        ])

        result = await service_with_email.import_tracking_from_file(file)

        assert result.success_count == 1
        assert result.email_sent_count == 1
        assert result.email_failed_count == 0
        mock_email_service.send_shipping_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_status_to_shipped(
        self, service_with_email, mock_repos, mock_email_service
    ):
        """Shipment and order status are updated to shipped."""
        order = make_order()
        shipment = make_shipment()

        mock_repos["order_repo"].find_by_order_number.return_value = order
        mock_repos["shipment_repo"].find_by_order_ids.return_value = {order.id: shipment}

        file = make_csv_file([
            ["注文番号", "伝票番号"],
            ["ORD-0001", "1234-5678"],
        ])

        await service_with_email.import_tracking_from_file(file)

        assert shipment.status == ShipmentStatus.SHIPPED.value
        assert shipment.shipped_at is not None
        assert order.status == OrderStatus.SHIPPED.value

    @pytest.mark.asyncio
    async def test_sets_shipping_email_sent_flag(
        self, service_with_email, mock_repos, mock_email_service
    ):
        """shipping_email_sent flag is set to True after successful send."""
        order = make_order()
        shipment = make_shipment()

        mock_repos["order_repo"].find_by_order_number.return_value = order
        mock_repos["shipment_repo"].find_by_order_ids.return_value = {order.id: shipment}

        file = make_csv_file([
            ["注文番号", "伝票番号"],
            ["ORD-0001", "1234-5678"],
        ])

        await service_with_email.import_tracking_from_file(file)

        assert shipment.shipping_email_sent is True

    @pytest.mark.asyncio
    async def test_skips_email_when_already_sent(
        self, service_with_email, mock_repos, mock_email_service
    ):
        """No duplicate email when shipping_email_sent is already True."""
        order = make_order()
        shipment = make_shipment(shipping_email_sent=True)

        mock_repos["order_repo"].find_by_order_number.return_value = order
        mock_repos["shipment_repo"].find_by_order_ids.return_value = {order.id: shipment}

        file = make_csv_file([
            ["注文番号", "伝票番号"],
            ["ORD-0001", "1234-5678"],
        ])

        result = await service_with_email.import_tracking_from_file(file)

        assert result.success_count == 1
        assert result.email_sent_count == 0
        mock_email_service.send_shipping_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_email_when_no_customer_email(
        self, service_with_email, mock_repos, mock_email_service
    ):
        """No email sent when customer has no email address."""
        order = make_order(customer_email=None)
        shipment = make_shipment()

        mock_repos["order_repo"].find_by_order_number.return_value = order
        mock_repos["shipment_repo"].find_by_order_ids.return_value = {order.id: shipment}

        file = make_csv_file([
            ["注文番号", "伝票番号"],
            ["ORD-0001", "1234-5678"],
        ])

        result = await service_with_email.import_tracking_from_file(file)

        assert result.success_count == 1
        assert result.email_sent_count == 0
        mock_email_service.send_shipping_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_email_without_email_service(
        self, service_without_email, mock_repos
    ):
        """Import works normally without email service (no crash)."""
        order = make_order()
        shipment = make_shipment()

        mock_repos["order_repo"].find_by_order_number.return_value = order
        mock_repos["shipment_repo"].find_by_order_ids.return_value = {order.id: shipment}

        file = make_csv_file([
            ["注文番号", "伝票番号"],
            ["ORD-0001", "1234-5678"],
        ])

        result = await service_without_email.import_tracking_from_file(file)

        assert result.success_count == 1
        assert result.email_sent_count == 0

    @pytest.mark.asyncio
    async def test_email_failure_does_not_rollback_update(
        self, service_with_email, mock_repos, mock_email_service
    ):
        """DB update succeeds even when email sending fails."""
        mock_email_service.send_shipping_notification.return_value = False

        order = make_order()
        shipment = make_shipment()

        mock_repos["order_repo"].find_by_order_number.return_value = order
        mock_repos["shipment_repo"].find_by_order_ids.return_value = {order.id: shipment}

        file = make_csv_file([
            ["注文番号", "伝票番号"],
            ["ORD-0001", "1234-5678"],
        ])

        result = await service_with_email.import_tracking_from_file(file)

        # Import still succeeds
        assert result.success_count == 1
        # Email failed
        assert result.email_sent_count == 0
        assert result.email_failed_count == 1
        # Status still updated
        assert shipment.status == ShipmentStatus.SHIPPED.value
        # Flag NOT set (email failed)
        assert shipment.shipping_email_sent is False
        # DB update still called
        mock_repos["shipment_repo"].update.assert_called_once()

    @pytest.mark.asyncio
    async def test_results_contain_row_details(
        self, service_with_email, mock_repos, mock_email_service
    ):
        """Results list contains per-row details including email status."""
        order = make_order()
        shipment = make_shipment()

        mock_repos["order_repo"].find_by_order_number.return_value = order
        mock_repos["shipment_repo"].find_by_order_ids.return_value = {order.id: shipment}

        file = make_csv_file([
            ["注文番号", "伝票番号"],
            ["ORD-0001", "1234-5678"],
        ])

        result = await service_with_email.import_tracking_from_file(file)

        assert len(result.results) == 1
        row_result = result.results[0]
        assert row_result.order_number == "ORD-0001"
        assert row_result.tracking_number == "1234-5678"
        assert row_result.email_sent is True
