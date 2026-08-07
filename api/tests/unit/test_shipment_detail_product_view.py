"""Unit tests for ShipmentService._to_response() OrderItem expansion.

FEAT-0021: Display product information per OrderItem in shipment detail page.
Tests verify that _to_response() expands each ShipmentItem into multiple
ShipmentItemResponse rows (one per OrderItem), including quantity and
thumbnail_image_url fields.

AC-001: ShipmentItemResponse has quantity field
AC-002: Single OrderItem -> 1 row with quantity and thumbnail_image_url
AC-003: Multiple OrderItems -> expanded into N rows
AC-004: No OrderItems (old order) -> fallback with product_name, quantity=None
AC-005: Composite ID format: {shipment_item_id}_{order_item_id}
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderItem
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.schemas.shipment import ShipmentItemResponse
from app.services.shipment_service import ShipmentService


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
def shipment_service(mock_shipment_repo: Any, mock_order_repo: Any, mock_file_storage: Any) -> Any:
    """Create ShipmentService with mocked dependencies."""
    return ShipmentService(
        shipment_repo=mock_shipment_repo,
        order_repo=mock_order_repo,
        file_storage=mock_file_storage,
    )


def create_mock_order_item(
    item_id: str = "oi-001",
    product_name: str = "TestProduct",
    quantity: int = 1,
    thumbnail_image_url: str | None = None,
) -> MagicMock:
    """Create a mock OrderItem with the given fields."""
    item = MagicMock(spec=OrderItem)
    item.id = item_id
    item.product_name = product_name
    item.quantity = quantity
    item.thumbnail_image_url = thumbnail_image_url
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
    order.product_name = product_name
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
    shipment.created_at = datetime.now(UTC)
    shipment.updated_at = datetime.now(UTC)
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


class TestShipmentDetailProductView:
    """Test OrderItem expansion in ShipmentService._to_response()."""

    # ===========================================
    # AC-001: ShipmentItemResponse has quantity field
    # ===========================================

    def test_ac001_shipment_item_response_has_quantity_field(self) -> None:
        """AC-001: ShipmentItemResponse に quantity フィールドが含まれる.

        Given: ShipmentItemResponse スキーマが定義されている
        When: quantity を指定してインスタンスを生成する
        Then: quantity フィールドが正しく設定される（int | None）
        """
        # Act
        response_item = ShipmentItemResponse(
            id="item-001",
            order_id="order-001",
            order_number="ORD-001",
            product_name="Test Product",
            quantity=5,
            thumbnail_image_url=None,
        )

        # Assert
        assert response_item.quantity == 5

    def test_ac001_quantity_field_is_optional(self) -> None:
        """AC-001: quantity フィールドは None を許容する.

        Given: ShipmentItemResponse スキーマが定義されている
        When: quantity を None で生成する
        Then: quantity が None として設定される
        """
        response_item = ShipmentItemResponse(
            id="item-001",
            order_id="order-001",
            order_number="ORD-001",
            product_name="Test Product",
            quantity=None,
            thumbnail_image_url=None,
        )

        assert response_item.quantity is None

    def test_ac001_quantity_field_defaults_to_none(self) -> None:
        """AC-001: quantity フィールドのデフォルト値は None.

        Given: ShipmentItemResponse スキーマが定義されている
        When: quantity を指定せずに生成する
        Then: quantity が None になる
        """
        response_item = ShipmentItemResponse(
            id="item-001",
            order_id="order-001",
            order_number="ORD-001",
            product_name="Test Product",
        )

        assert response_item.quantity is None

    # ===========================================
    # AC-001 (supplement): ShipmentItemResponse has thumbnail_image_url field
    # ===========================================

    def test_ac001_shipment_item_response_has_thumbnail_image_url_field(self) -> None:
        """ShipmentItemResponse に thumbnail_image_url フィールドが含まれる.

        Given: ShipmentItemResponse スキーマが定義されている
        When: thumbnail_image_url を指定してインスタンスを生成する
        Then: thumbnail_image_url フィールドが正しく設定される（str | None）
        """
        response_item = ShipmentItemResponse(
            id="item-001",
            order_id="order-001",
            order_number="ORD-001",
            product_name="Test Product",
            quantity=1,
            thumbnail_image_url="https://example.com/thumb.jpg",
        )

        assert response_item.thumbnail_image_url == "https://example.com/thumb.jpg"

    def test_ac001_thumbnail_image_url_defaults_to_none(self) -> None:
        """thumbnail_image_url フィールドのデフォルト値は None."""
        response_item = ShipmentItemResponse(
            id="item-001",
            order_id="order-001",
            order_number="ORD-001",
            product_name="Test Product",
        )

        assert response_item.thumbnail_image_url is None

    # ===========================================
    # AC-002: Single OrderItem -> 1 row with quantity and thumbnail_image_url
    # ===========================================

    def test_ac002_single_order_item_has_quantity_and_thumbnail(self, shipment_service: Any) -> None:
        """AC-002: OrderItem が1つの注文 -> 1行で quantity, thumbnail_image_url が含まれる.

        Given: 1つの OrderItem (quantity=2, thumbnail_image_url="https://example.com/a.jpg")
               を持つ注文が紐づく配送がある
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: items に 1つの ShipmentItemResponse が含まれ、
              quantity=2, thumbnail_image_url="https://example.com/a.jpg" が正しい
        """
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-001",
            product_name="アクリルキーホルダーA",
            quantity=2,
            thumbnail_image_url="https://example.com/a.jpg",
        )
        order = create_mock_order(
            product_name=None,
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
        assert response.items[0].quantity == 2
        assert response.items[0].thumbnail_image_url == "https://example.com/a.jpg"

    # ===========================================
    # AC-003: Multiple OrderItems -> expanded into N rows
    # ===========================================

    def test_ac003_multiple_order_items_expanded(self, shipment_service: Any) -> None:
        """AC-003: OrderItem が複数の注文 -> OrderItem 数分の行に展開される.

        Given: 1つの注文に 3つの OrderItem
               (商品A:数量2, 商品B:数量1, 商品C:数量3) が紐づく配送がある
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: items に 3つの ShipmentItemResponse が含まれ、
              各 product_name, quantity, thumbnail_image_url が正しい
        """
        # Arrange
        order_item_a = create_mock_order_item(
            item_id="oi-001",
            product_name="商品A",
            quantity=2,
            thumbnail_image_url="https://example.com/a.jpg",
        )
        order_item_b = create_mock_order_item(
            item_id="oi-002",
            product_name="商品B",
            quantity=1,
            thumbnail_image_url=None,
        )
        order_item_c = create_mock_order_item(
            item_id="oi-003",
            product_name="商品C",
            quantity=3,
            thumbnail_image_url="https://example.com/c.jpg",
        )
        order = create_mock_order(
            order_id="order-001",
            order_number="ORD-001",
            product_name=None,
            order_items=[order_item_a, order_item_b, order_item_c],
        )
        shipment = create_mock_shipment(
            shipment_items=[("item-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 3

        assert response.items[0].product_name == "商品A"
        assert response.items[0].quantity == 2
        assert response.items[0].thumbnail_image_url == "https://example.com/a.jpg"
        assert response.items[0].order_number == "ORD-001"

        assert response.items[1].product_name == "商品B"
        assert response.items[1].quantity == 1
        assert response.items[1].thumbnail_image_url is None

        assert response.items[2].product_name == "商品C"
        assert response.items[2].quantity == 3
        assert response.items[2].thumbnail_image_url == "https://example.com/c.jpg"

    # ===========================================
    # AC-004: No OrderItems -> fallback with product_name, quantity=None
    # ===========================================

    def test_ac004_no_order_items_fallback(self, shipment_service: Any) -> None:
        """AC-004: OrderItem がない古い注文 -> product_name フォールバック、quantity=None.

        Given: 注文に OrderItem が紐づいていない配送がある
               (Order.product_name = "Legacy Product")
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: items に product_name="Legacy Product" の1件が含まれ、
              quantity=None, thumbnail_image_url=None
        """
        # Arrange
        order = create_mock_order(
            product_name="Legacy Product",
            order_items=[],
        )
        shipment = create_mock_shipment(
            shipment_items=[("item-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 1
        assert response.items[0].product_name == "Legacy Product"
        assert response.items[0].quantity is None
        assert response.items[0].thumbnail_image_url is None

    def test_ac004_no_order_items_no_legacy_product_name(self, shipment_service: Any) -> None:
        """AC-004: OrderItem もなく Order.product_name も null の場合.

        Given: 注文に OrderItem もなく、Order.product_name も None
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: items に product_name=None の1件が含まれ、
              quantity=None, thumbnail_image_url=None
        """
        # Arrange
        order = create_mock_order(
            product_name=None,
            order_items=[],
        )
        shipment = create_mock_shipment(
            shipment_items=[("item-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 1
        assert response.items[0].product_name is None
        assert response.items[0].quantity is None
        assert response.items[0].thumbnail_image_url is None

    def test_ac004_order_is_none(self, shipment_service: Any) -> None:
        """AC-004: Order が None の場合もエラーにならない.

        Given: ShipmentItem の order が None
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: items に product_name=None, quantity=None, thumbnail_image_url=None の1件
        """
        # Arrange
        shipment = MagicMock(spec=Shipment)
        shipment.id = "shipment-001"
        shipment.status = ShipmentStatus.PENDING.value
        shipment.tracking_number = None
        shipment.carrier = None
        shipment.packing_photo_path = None
        shipment.shipped_at = None
        shipment.delivered_at = None
        shipment.note = None
        shipment.created_at = datetime.now(UTC)
        shipment.updated_at = datetime.now(UTC)

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
        assert response.items[0].quantity is None
        assert response.items[0].thumbnail_image_url is None

    # ===========================================
    # AC-005: Composite ID format: {shipment_item_id}_{order_item_id}
    # ===========================================

    def test_ac005_composite_id_format(self, shipment_service: Any) -> None:
        """AC-005: 複合ID形式 {shipment_item_id}_{order_item_id}.

        Given: ShipmentItem (id="si-001") に OrderItem (id="oi-001") が紐づく
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: ShipmentItemResponse の id が "si-001_oi-001" となる
        """
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-001",
            product_name="Test Product",
            quantity=1,
            thumbnail_image_url=None,
        )
        order = create_mock_order(
            order_items=[order_item],
        )
        shipment = create_mock_shipment(
            shipment_items=[("si-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 1
        assert response.items[0].id == "si-001_oi-001"

    def test_ac005_composite_id_for_multiple_items(self, shipment_service: Any) -> None:
        """AC-005: 複数 OrderItem の場合、各行の複合IDが正しい.

        Given: ShipmentItem (id="si-001") に 2つの OrderItem
               (id="oi-001", id="oi-002") が紐づく
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: 各 ShipmentItemResponse の id が
              "si-001_oi-001", "si-001_oi-002" となる
        """
        # Arrange
        order_item_a = create_mock_order_item(
            item_id="oi-001",
            product_name="Product A",
            quantity=1,
        )
        order_item_b = create_mock_order_item(
            item_id="oi-002",
            product_name="Product B",
            quantity=2,
        )
        order = create_mock_order(
            order_items=[order_item_a, order_item_b],
        )
        shipment = create_mock_shipment(
            shipment_items=[("si-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 2
        assert response.items[0].id == "si-001_oi-001"
        assert response.items[1].id == "si-001_oi-002"

    def test_ac005_fallback_id_when_no_order_items(self, shipment_service: Any) -> None:
        """AC-005: OrderItem がない場合は shipment_item.id をそのまま使う.

        Given: ShipmentItem (id="si-001") に OrderItem がない (フォールバック)
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: ShipmentItemResponse の id が "si-001" のまま
        """
        # Arrange
        order = create_mock_order(
            product_name="Legacy Product",
            order_items=[],
        )
        shipment = create_mock_shipment(
            shipment_items=[("si-001", order)],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 1
        assert response.items[0].id == "si-001"

    # ===========================================
    # Additional: Multiple orders with multiple OrderItems
    # ===========================================

    def test_multiple_orders_each_with_order_items_expanded(self, shipment_service: Any) -> None:
        """複数注文が含まれる配送で、各注文の OrderItem が正しく展開される.

        Given: 2つの注文（注文A: OrderItem 2件、注文B: OrderItem 1件）が含まれる配送
        When: _to_response メソッドで ShipmentResponse を生成する
        Then: items に 3つの ShipmentItemResponse が含まれ、
              各 order_number が正しい注文に紐づく
        """
        # Arrange
        order1_item_a = create_mock_order_item(
            item_id="oi-001",
            product_name="商品X",
            quantity=1,
            thumbnail_image_url="https://example.com/x.jpg",
        )
        order1_item_b = create_mock_order_item(
            item_id="oi-002",
            product_name="商品Y",
            quantity=2,
            thumbnail_image_url=None,
        )
        order1 = create_mock_order(
            order_id="order-001",
            order_number="ORD-001",
            product_name=None,
            order_items=[order1_item_a, order1_item_b],
        )

        order2_item = create_mock_order_item(
            item_id="oi-003",
            product_name="商品Z",
            quantity=5,
            thumbnail_image_url="https://example.com/z.jpg",
        )
        order2 = create_mock_order(
            order_id="order-002",
            order_number="ORD-002",
            product_name=None,
            order_items=[order2_item],
        )

        shipment = create_mock_shipment(
            shipment_items=[
                ("si-001", order1),
                ("si-002", order2),
            ],
        )

        # Act
        response = shipment_service._to_response(shipment)

        # Assert
        assert len(response.items) == 3

        # Order 1, Item A
        assert response.items[0].order_number == "ORD-001"
        assert response.items[0].product_name == "商品X"
        assert response.items[0].quantity == 1
        assert response.items[0].thumbnail_image_url == "https://example.com/x.jpg"
        assert response.items[0].id == "si-001_oi-001"

        # Order 1, Item B
        assert response.items[1].order_number == "ORD-001"
        assert response.items[1].product_name == "商品Y"
        assert response.items[1].quantity == 2
        assert response.items[1].thumbnail_image_url is None
        assert response.items[1].id == "si-001_oi-002"

        # Order 2, Item
        assert response.items[2].order_number == "ORD-002"
        assert response.items[2].product_name == "商品Z"
        assert response.items[2].quantity == 5
        assert response.items[2].thumbnail_image_url == "https://example.com/z.jpg"
        assert response.items[2].id == "si-002_oi-003"
