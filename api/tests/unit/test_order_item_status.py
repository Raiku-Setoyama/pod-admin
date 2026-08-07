"""OrderItem単位のステータス管理ユニットテスト

製品単位でのステータス管理機能のテスト:
- OrderItem.statusのCRUD
- Order.statusの導出ロジック
- 全OrderItemがdeliveredになった場合のShipment作成
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.order import Order, OrderItemStatus, OrderStatus
from app.repositories.order_repository import OrderRepository
from app.schemas.manufacturer import ManufacturerOrderStatusUpdate
from app.services.manufacturer_order_service import ManufacturerOrderService


class TestDeriveOrderStatus:
    """Order.statusの導出ロジックテスト"""

    def test_derive_status_all_ordered(self):
        """全OrderItemがorderedの場合、Order.statusはorderedになる"""
        order = MagicMock(spec=Order)
        items = [MagicMock(status=OrderItemStatus.ORDERED.value) for _ in range(3)]
        order.items = items

        repo = OrderRepository(AsyncMock())
        result = repo.derive_order_status(order)

        assert result == OrderStatus.ORDERED.value

    def test_derive_status_all_manufacturing(self):
        """全OrderItemがmanufacturingの場合、Order.statusはmanufacturingになる"""
        order = MagicMock(spec=Order)
        items = [MagicMock(status=OrderItemStatus.MANUFACTURING.value) for _ in range(3)]
        order.items = items

        repo = OrderRepository(AsyncMock())
        result = repo.derive_order_status(order)

        assert result == OrderStatus.MANUFACTURING.value

    def test_derive_status_all_delivered(self):
        """全OrderItemがdeliveredの場合、Order.statusはdeliveredになる"""
        order = MagicMock(spec=Order)
        items = [MagicMock(status=OrderItemStatus.DELIVERED.value) for _ in range(3)]
        order.items = items

        repo = OrderRepository(AsyncMock())
        result = repo.derive_order_status(order)

        assert result == OrderStatus.DELIVERED.value

    def test_derive_status_mixed_with_manufacturing(self):
        """1つでもmanufacturingがあればOrder.statusはmanufacturingになる"""
        order = MagicMock(spec=Order)
        items = [
            MagicMock(status=OrderItemStatus.ORDERED.value),
            MagicMock(status=OrderItemStatus.MANUFACTURING.value),
            MagicMock(status=OrderItemStatus.DELIVERED.value),
        ]
        order.items = items

        repo = OrderRepository(AsyncMock())
        result = repo.derive_order_status(order)

        assert result == OrderStatus.MANUFACTURING.value

    def test_derive_status_ordered_and_delivered(self):
        """orderedとdeliveredが混在（manufacturingなし）の場合はorderedになる"""
        order = MagicMock(spec=Order)
        items = [
            MagicMock(status=OrderItemStatus.ORDERED.value),
            MagicMock(status=OrderItemStatus.DELIVERED.value),
        ]
        order.items = items

        repo = OrderRepository(AsyncMock())
        result = repo.derive_order_status(order)

        assert result == OrderStatus.ORDERED.value

    def test_derive_status_empty_items(self):
        """itemsが空の場合はorderedになる"""
        order = MagicMock(spec=Order)
        order.items = []

        repo = OrderRepository(AsyncMock())
        result = repo.derive_order_status(order)

        assert result == OrderStatus.ORDERED.value

    def test_derive_status_any_preparing_order(self):
        """1つでも発注準備中があり manufacturing が無ければ preparing_order になる"""
        order = MagicMock(spec=Order)
        items = [
            MagicMock(status=OrderItemStatus.PREPARING_ORDER.value),
            MagicMock(status=OrderItemStatus.ORDERED.value),
        ]
        order.items = items

        repo = OrderRepository(AsyncMock())
        result = repo.derive_order_status(order)

        assert result == OrderStatus.PREPARING_ORDER.value

    def test_derive_status_manufacturing_beats_preparing_order(self):
        """manufacturing と preparing_order が混在する場合は manufacturing を優先する"""
        order = MagicMock(spec=Order)
        items = [
            MagicMock(status=OrderItemStatus.PREPARING_ORDER.value),
            MagicMock(status=OrderItemStatus.MANUFACTURING.value),
        ]
        order.items = items

        repo = OrderRepository(AsyncMock())
        result = repo.derive_order_status(order)

        assert result == OrderStatus.MANUFACTURING.value


class TestUpdateOrderStatus:
    """ステータス更新サービステスト"""

    @pytest.fixture
    def mock_order_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_shipment_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_repo, mock_manufacturer_repo, mock_shipment_repo):
        return ManufacturerOrderService(
            order_repo=mock_order_repo,
            manufacturer_repo=mock_manufacturer_repo,
            shipment_repo=mock_shipment_repo,
        )

    @pytest.fixture
    def mock_manufacturer(self):
        manufacturer = MagicMock()
        manufacturer.id = str(uuid4())
        manufacturer.name = "テストメーカー"
        return manufacturer

    @pytest.mark.asyncio
    async def test_update_item_status_to_manufacturing(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
    ):
        """OrderItemのステータスをmanufacturingに更新"""
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        # モック設定
        updated_items = [MagicMock(id=str(uuid4()), order_id=str(uuid4()))]
        affected_order_ids = {updated_items[0].order_id}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            updated_items,
            affected_order_ids,
        )
        mock_order_repo.update_order_derived_status.return_value = MagicMock(
            id=updated_items[0].order_id,
            status=OrderStatus.MANUFACTURING.value,
        )

        data = ManufacturerOrderStatusUpdate(status="manufacturing")
        updated_count, shipments_created = await service.update_order_status(manufacturer_id, data)

        assert updated_count == 1
        assert shipments_created == 0
        mock_order_repo.update_item_status_by_manufacturer.assert_called_once()
        mock_order_repo.update_order_derived_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_item_status_to_delivered_creates_shipment_when_all_delivered(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_shipment_repo: AsyncMock,
        mock_manufacturer,
    ):
        """全OrderItemがdeliveredになった場合のみShipmentが作成される"""
        manufacturer_id = mock_manufacturer.id
        order_id = str(uuid4())
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        # モック設定
        updated_items = [MagicMock(id=str(uuid4()), order_id=order_id)]
        affected_order_ids = {order_id}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            updated_items,
            affected_order_ids,
        )

        mock_order = MagicMock(
            id=order_id,
            status=OrderStatus.DELIVERED.value,
        )
        mock_order_repo.update_order_derived_status.return_value = mock_order
        mock_order_repo.check_all_items_delivered.return_value = True
        mock_shipment_repo.exists_for_order.return_value = False

        data = ManufacturerOrderStatusUpdate(status="delivered")
        updated_count, shipments_created = await service.update_order_status(manufacturer_id, data)

        assert updated_count == 1
        assert shipments_created == 1
        mock_order_repo.check_all_items_delivered.assert_called_once_with(order_id)
        mock_shipment_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_item_status_to_delivered_no_shipment_when_partial(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_shipment_repo: AsyncMock,
        mock_manufacturer,
    ):
        """一部のOrderItemのみdeliveredの場合はShipmentが作成されない"""
        manufacturer_id = mock_manufacturer.id
        order_id = str(uuid4())
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        # モック設定
        updated_items = [MagicMock(id=str(uuid4()), order_id=order_id)]
        affected_order_ids = {order_id}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            updated_items,
            affected_order_ids,
        )

        mock_order = MagicMock(
            id=order_id,
            status=OrderStatus.MANUFACTURING.value,  # まだ全部deliveredじゃない
        )
        mock_order_repo.update_order_derived_status.return_value = mock_order
        mock_order_repo.check_all_items_delivered.return_value = False

        data = ManufacturerOrderStatusUpdate(status="delivered")
        updated_count, shipments_created = await service.update_order_status(manufacturer_id, data)

        assert updated_count == 1
        assert shipments_created == 0
        mock_order_repo.check_all_items_delivered.assert_called_once_with(order_id)
        mock_shipment_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_item_status_no_duplicate_shipment(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_shipment_repo: AsyncMock,
        mock_manufacturer,
    ):
        """既にShipmentが存在する場合は重複作成されない"""
        manufacturer_id = mock_manufacturer.id
        order_id = str(uuid4())
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        # モック設定
        updated_items = [MagicMock(id=str(uuid4()), order_id=order_id)]
        affected_order_ids = {order_id}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            updated_items,
            affected_order_ids,
        )

        mock_order = MagicMock(
            id=order_id,
            status=OrderStatus.DELIVERED.value,
        )
        mock_order_repo.update_order_derived_status.return_value = mock_order
        mock_order_repo.check_all_items_delivered.return_value = True
        mock_shipment_repo.exists_for_order.return_value = True  # 既存

        data = ManufacturerOrderStatusUpdate(status="delivered")
        updated_count, shipments_created = await service.update_order_status(manufacturer_id, data)

        assert updated_count == 1
        assert shipments_created == 0  # 既存のため作成されない
        mock_shipment_repo.exists_for_order.assert_called_once_with(order_id)
        mock_shipment_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_item_status_with_specific_item_ids(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
    ):
        """特定のOrderItem IDを指定してステータス更新"""
        manufacturer_id = mock_manufacturer.id
        target_item_ids = [str(uuid4()), str(uuid4())]
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        # モック設定
        updated_items = [
            MagicMock(id=target_item_ids[0], order_id=str(uuid4())),
            MagicMock(id=target_item_ids[1], order_id=str(uuid4())),
        ]
        affected_order_ids = {item.order_id for item in updated_items}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            updated_items,
            affected_order_ids,
        )
        mock_order_repo.update_order_derived_status.return_value = MagicMock()

        data = ManufacturerOrderStatusUpdate(
            status="manufacturing",
            order_item_ids=target_item_ids,
        )
        updated_count, shipments_created = await service.update_order_status(manufacturer_id, data)

        assert updated_count == 2
        assert shipments_created == 0
        call_args = mock_order_repo.update_item_status_by_manufacturer.call_args
        assert call_args.kwargs["order_item_ids"] == target_item_ids


class TestOrderItemStatusIndependence:
    """同一Order内のOrderItem独立性テスト"""

    @pytest.fixture
    def mock_order_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_shipment_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_repo, mock_manufacturer_repo, mock_shipment_repo):
        return ManufacturerOrderService(
            order_repo=mock_order_repo,
            manufacturer_repo=mock_manufacturer_repo,
            shipment_repo=mock_shipment_repo,
        )

    @pytest.fixture
    def mock_manufacturer(self):
        manufacturer = MagicMock()
        manufacturer.id = str(uuid4())
        manufacturer.name = "テストメーカー"
        return manufacturer

    @pytest.mark.asyncio
    async def test_update_single_item_in_multi_item_order(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
    ):
        """複数アイテムを持つOrderの1アイテムのみ更新

        given: 注文#0001にTシャツ（メーカーA）とステッカー（メーカーB）がある
        when: メーカーAがTシャツを「製造中」に更新
        then:
          - Tシャツのみステータスが更新される
          - ステッカーのステータスは変わらない
          - Order.statusは導出ロジックで決定される
        """
        manufacturer_id = mock_manufacturer.id
        order_id = str(uuid4())
        item_a_id = str(uuid4())  # Tシャツ（対象）

        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        # メーカーAの1アイテムのみ更新される
        updated_items = [MagicMock(id=item_a_id, order_id=order_id)]
        affected_order_ids = {order_id}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            updated_items,
            affected_order_ids,
        )

        # Order内に他のアイテムがあるため、全部deliveredにはならない
        mock_order_repo.update_order_derived_status.return_value = MagicMock(
            id=order_id,
            status=OrderStatus.MANUFACTURING.value,
        )

        data = ManufacturerOrderStatusUpdate(
            status="manufacturing",
            order_item_ids=[item_a_id],
        )
        updated_count, shipments_created = await service.update_order_status(manufacturer_id, data)

        assert updated_count == 1
        assert shipments_created == 0
        # 指定したアイテムIDのみが更新対象
        call_args = mock_order_repo.update_item_status_by_manufacturer.call_args
        assert call_args.kwargs["order_item_ids"] == [item_a_id]
