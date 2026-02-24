"""Unit tests for ShipmentService._to_response() product_name mapping.

FEAT-0014: Fix product name display in shipment detail page.
Tests verify that product_name is correctly sourced from OrderItem.product_name
instead of the deprecated Order.product_name field.

AC-001: Single OrderItem -> product_name set correctly
AC-002: Multiple OrderItems -> comma-separated product_name
AC-003: Order is null -> product_name is null
AC-004: Order has 0 OrderItems -> product_name is null
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderItem, OrderStatus
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.services.shipment_service import ShipmentService


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
def shipment_service(mock_shipment_repo, mock_order_repo, mock_file_storage):
    """Create ShipmentService with mocked dependencies."""
    return ShipmentService(
        shipment_repo=mock_shipment_repo,
        order_repo=mock_order_repo,
        file_storage=mock_file_storage,
    )


def create_mock_order_item(product_name: str) -> MagicMock:
    """Create a mock OrderItem with the given product_name."""
    item = MagicMock(spec=OrderItem)
    item.product_name = product_name
    return item


def create_mock_order(
    order_id: str = "order-001",
    order_number: str = "TEST-001",
    product_name: str | None = None,
    order_items: list[MagicMock] | None = None,
) -> MagicMock:
    """Create a mock Order.

    Args:
        order_id: The order ID.
        order_number: The order number.
        product_name: The deprecated Order.product_name field (nullable).
        order_items: List of OrderItem mocks to attach as order.items.
    """
    order = MagicMock(spec=Order)
    order.id = order_id
    order.order_number = order_number
    order.product_name = product_name  # deprecated, often None in new data
    order.items = order_items if order_items is not None else []
    order.customer_name = "Test Customer"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "Tokyo"
    order.customer_address_city = "Chiyoda"
    order.customer_address_building = None
    order.customer_phone = "090-1234-5678"
    return order


def create_mock_shipment(
    shipment_id: str = "shipment-001",
    status: str = ShipmentStatus.PENDING.value,
    shipment_items: list[tuple[str, MagicMock | None]] | None = None,
) -> MagicMock:
    """Create a mock Shipment.

    Args:
        shipment_id: The shipment ID.
        status: The shipment status.
        shipment_items: List of (item_id, order_mock_or_none) tuples.
            Each becomes a ShipmentItem with the given order attached.
    """
    shipment = MagicMock(spec=Shipment)
    shipment.id = shipment_id
    shipment.status = status
    shipment.tracking_number = None
    shipment.carrier = None
    shipment.packing_photo_path = None
    shipment.shipped_at = None
    shipment.delivered_at = None
    shipment.note = None
    shipment.created_at = datetime.now(timezone.utc)
    shipment.updated_at = datetime.now(timezone.utc)
    shipment.items = []

    if shipment_items:
        for item_id, order in shipment_items:
            si = MagicMock(spec=ShipmentItem)
            si.id = item_id
            si.order_id = order.id if order else "unknown"
            si.order = order
            shipment.items.append(si)

    # Set first_order property
    if shipment.items and shipment.items[0].order:
        shipment.first_order = shipment.items[0].order
    else:
        shipment.first_order = None

    return shipment


class TestShipmentProductName:
    """Test product_name mapping in ShipmentService._to_response()."""

    # ===========================================
    # AC-001: Single OrderItem -> product_name from OrderItem
    # ===========================================

    def test_ac001_single_order_item_product_name(self, shipment_service):
        """AC-001: ShipmentItemResponse の product_name に OrderItem の商品名が設定される.

        Given: ShipmentItem に紐づく Order が1件の OrderItem
               (product_name="アクリルキーホルダーA") を持つ
        When: ShipmentService._to_response() で ShipmentResponse を生成する
        Then: 該当 ShipmentItemResponse の product_name が
              "アクリルキーホルダーA" となる
        """
        # Arrange
        order_item = create_mock_order_item("アクリルキーホルダーA")
        order = create_mock_order(
            product_name=None,  # deprecated field is null
            order_items=[order_item],
        )
        shipment = create_mock_shipment(
            shipment_items=[("item-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 1
        assert response.items[0].product_name == "アクリルキーホルダーA"

    # ===========================================
    # AC-002: Multiple OrderItems -> comma-separated
    # ===========================================

    def test_ac002_multiple_order_items_comma_separated(self, shipment_service):
        """AC-002: Order に複数の OrderItem がある場合、商品名がカンマ区切りで結合される.

        Given: ShipmentItem に紐づく Order が複数の OrderItem
               ("商品A", "商品B") を持つ
        When: ShipmentService._to_response() で ShipmentResponse を生成する
        Then: 該当 ShipmentItemResponse の product_name が
              "商品A, 商品B" となる
        """
        # Arrange
        order_item_a = create_mock_order_item("商品A")
        order_item_b = create_mock_order_item("商品B")
        order = create_mock_order(
            product_name=None,
            order_items=[order_item_a, order_item_b],
        )
        shipment = create_mock_shipment(
            shipment_items=[("item-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 1
        assert response.items[0].product_name == "商品A, 商品B"

    # ===========================================
    # AC-003: Order is null -> product_name is null
    # ===========================================

    def test_ac003_order_is_null_product_name_is_none(self, shipment_service):
        """AC-003: Order が null の場合、product_name は null になる.

        Given: ShipmentItem に紐づく Order が null である
        When: ShipmentService._to_response() で ShipmentResponse を生成する
        Then: 該当 ShipmentItemResponse の product_name が null となる
        """
        # Arrange
        # Create a shipment with a ShipmentItem whose order is None
        shipment = MagicMock(spec=Shipment)
        shipment.id = "shipment-001"
        shipment.status = ShipmentStatus.PENDING.value
        shipment.tracking_number = None
        shipment.carrier = None
        shipment.packing_photo_path = None
        shipment.shipped_at = None
        shipment.delivered_at = None
        shipment.note = None
        shipment.created_at = datetime.now(timezone.utc)
        shipment.updated_at = datetime.now(timezone.utc)

        si = MagicMock(spec=ShipmentItem)
        si.id = "item-001"
        si.order_id = "order-missing"
        si.order = None

        shipment.items = [si]
        shipment.first_order = None

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 1
        assert response.items[0].product_name is None

    # ===========================================
    # AC-004: Order has 0 OrderItems -> product_name is null
    # ===========================================

    def test_ac004_order_with_empty_items_product_name_is_none(self, shipment_service):
        """AC-004: Order に OrderItem が0件の場合、product_name は null になる.

        Given: ShipmentItem に紐づく Order の items が空リストであり、
               Order.product_name (deprecated) も null である
        When: ShipmentService._to_response() で ShipmentResponse を生成する
        Then: 該当 ShipmentItemResponse の product_name が null となる

        Note: フォールバックとして Order.product_name が参照されるが、
              それも null の場合は最終的に null になる。
        """
        # Arrange
        order = create_mock_order(
            product_name=None,  # deprecated field also null
            order_items=[],  # empty items list
        )
        shipment = create_mock_shipment(
            shipment_items=[("item-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 1
        assert response.items[0].product_name is None

    # ===========================================
    # Additional edge cases
    # ===========================================

    def test_fallback_to_deprecated_field_when_items_empty_but_product_name_exists(
        self, shipment_service
    ):
        """Fallback: When Order.items is empty but Order.product_name (deprecated)
        has a value, the deprecated field should be used as fallback.

        This ensures backward compatibility with old data where
        Order.product_name was set and OrderItem did not exist yet.
        Per the design memo:
          if order and order.items:
              product_name = ", ".join(...)
          else:
              product_name = order.product_name if order else None  # fallback
        """
        # Arrange
        order = create_mock_order(
            product_name="Legacy Product Name",
            order_items=[],  # no order items
        )
        shipment = create_mock_shipment(
            shipment_items=[("item-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert - fallback to deprecated Order.product_name
        assert response.items[0].product_name == "Legacy Product Name"

    def test_multiple_shipment_items_each_with_different_orders(self, shipment_service):
        """Multiple ShipmentItems with different orders should each resolve
        product_name independently from their own Order's OrderItems."""
        # Arrange
        order1_item = create_mock_order_item("商品X")
        order1 = create_mock_order(
            order_id="order-001",
            order_number="ORD-001",
            product_name=None,
            order_items=[order1_item],
        )

        order2_item_a = create_mock_order_item("商品Y")
        order2_item_b = create_mock_order_item("商品Z")
        order2 = create_mock_order(
            order_id="order-002",
            order_number="ORD-002",
            product_name=None,
            order_items=[order2_item_a, order2_item_b],
        )

        shipment = create_mock_shipment(
            shipment_items=[
                ("item-001", order1),
                ("item-002", order2),
            ],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 2
        assert response.items[0].product_name == "商品X"
        assert response.items[1].product_name == "商品Y, 商品Z"
