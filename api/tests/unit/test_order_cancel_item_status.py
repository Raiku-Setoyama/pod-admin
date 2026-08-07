"""注文キャンセルの明細ステータス波及 ユニットテスト.

注文が cancelled になっても明細（OrderItem）が「発注済み」のまま残り、メーカー画面・
メーカーポータルでキャンセルが分からなかった問題の修正。
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import Order, OrderItem, OrderItemStatus, OrderStatus
from app.repositories.order_repository import OrderRepository
from app.services.external_service import ExternalService
from app.services.manufacturer_order_service import ManufacturerOrderService
from app.services.order_service import OrderService


@pytest.fixture
def mock_order_repo() -> Any:
    repo = AsyncMock()
    # apply_cancellation_to_items は同期メソッド（ロード済み Order を書き換えるだけ）
    repo.apply_cancellation_to_items = MagicMock()
    return repo


def test_cancelled_matches_order_status() -> None:
    """明細と注文の cancelled は同じ値（画面のラベル解決を共通化できる）."""
    assert OrderItemStatus.CANCELLED.value == OrderStatus.CANCELLED.value


# ============================================================
# OrderRepository.apply_cancellation_to_items（波及ロジック本体）
# ============================================================


def make_item(status: str, *, mfg_status: str | None = None) -> OrderItem:
    """明細を1件作る。mfg_status=None なら製造データ不要（v1 = 常に ready 扱い）."""
    item = OrderItem(status=status)
    if mfg_status is not None:
        item.manufacturing_data_id = "md-1"
        item.manufacturing_data = ManufacturingData(status=mfg_status)
    return item


def apply(items: list[OrderItem], *, cancelled: bool) -> list[str]:
    """波及を適用して、明細ステータスの結果を返す."""
    order = MagicMock(spec=Order)
    order.items = items
    OrderRepository(db=MagicMock()).apply_cancellation_to_items(order, cancelled=cancelled)
    return [item.status for item in items]


class TestApplyCancellationToItems:
    """キャンセルの開始/解除が明細ステータスへ反映されること."""

    def test_cancel_marks_every_item_cancelled(self) -> None:
        """工程の進み具合にかかわらず全明細をキャンセル済みにする."""
        items = [
            make_item(OrderItemStatus.ORDERED.value),
            make_item(OrderItemStatus.MANUFACTURING.value),
            make_item(OrderItemStatus.PREPARING_ORDER.value),
        ]

        assert apply(items, cancelled=True) == ["cancelled"] * 3

    def test_uncancel_restores_ready_items_to_ordered(self) -> None:
        """製造データ不要／ready の明細は「発注済み」へ戻す."""
        items = [
            make_item(OrderItemStatus.CANCELLED.value),
            make_item(OrderItemStatus.CANCELLED.value, mfg_status=MfgDataStatus.READY.value),
        ]

        assert apply(items, cancelled=False) == ["ordered", "ordered"]

    def test_uncancel_restores_unready_items_to_preparing_order(self) -> None:
        """製造データが未 ready の明細は「発注準備中」へ戻す（発注ゲートを維持）."""
        items = [
            make_item(
                OrderItemStatus.CANCELLED.value, mfg_status=MfgDataStatus.GENERATING.value
            )
        ]

        assert apply(items, cancelled=False) == ["preparing_order"]

    def test_uncancel_leaves_non_cancelled_items_untouched(self) -> None:
        """キャンセル済み以外の明細には触れない."""
        items = [make_item(OrderItemStatus.MANUFACTURING.value)]

        assert apply(items, cancelled=False) == ["manufacturing"]


# ============================================================
# 外部販売サイトAPIからのキャンセル
# ============================================================


def create_mock_order(
    order_id: str = "order-123",
    status: str = OrderStatus.ORDERED.value,
) -> MagicMock:
    """テスト用の Order モック（OrderResponse に変換できる最低限の属性を持つ）."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.status = status
    order.order_number = "ORD-001"
    order.items = []
    order.order_source = None
    order.order_source_id = None
    order.customer_name = "Test Customer"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "東京都"
    order.customer_address_city = "千代田区"
    order.customer_address_building = None
    order.customer_phone = "090-1234-5678"
    order.customer_email = "test@example.com"
    order.ordered_at = datetime.now(UTC)
    order.total_price = 1000
    order.estimated_shipping_date = None
    order.product_id = None
    order.product_name = None
    order.price = None
    order.quantity = None
    order.manufacturing_data_path = None
    order.manufacturing_data_filename = None
    order.manufacturing_data_size = None
    order.created_at = datetime.now(UTC)
    order.updated_at = datetime.now(UTC)
    return order


class TestExternalCancelPropagatesToItems:
    """ExternalService.cancel_order が明細へキャンセルを波及させること."""

    @pytest.mark.asyncio
    async def test_cancel_order_syncs_items(self, mock_order_repo: Any) -> None:
        service = ExternalService(product_repo=AsyncMock(), order_repo=mock_order_repo)
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_order_number.return_value = order
        mock_order_repo.update_status.return_value = create_mock_order(
            status=OrderStatus.CANCELLED.value
        )

        await service.cancel_order("ORD-001")

        mock_order_repo.apply_cancellation_to_items.assert_called_once_with(
            order, cancelled=True
        )


# ============================================================
# 管理画面からのステータス更新
# ============================================================


@pytest.fixture
def order_service(mock_order_repo: Any) -> Any:
    shipment_repo = AsyncMock()
    shipment_repo.find_by_order_ids.return_value = {}
    return OrderService(
        order_repo=mock_order_repo,
        product_repo=AsyncMock(),
        shipment_repo=shipment_repo,
    )


class TestOrderServiceCancellationSync:
    """update_status / bulk_update_status のキャンセル波及."""

    @pytest.mark.asyncio
    async def test_update_status_to_cancelled_syncs_items(
        self, order_service: Any, mock_order_repo: Any
    ) -> None:
        """ordered -> cancelled で明細もキャンセル済みにする."""
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order

        await order_service.update_status("order-123", OrderStatus.CANCELLED)

        mock_order_repo.apply_cancellation_to_items.assert_called_once_with(
            order, cancelled=True
        )

    @pytest.mark.asyncio
    async def test_update_status_from_cancelled_restores_items(
        self, order_service: Any, mock_order_repo: Any
    ) -> None:
        """cancelled -> ordered でキャンセルを解除し明細をライフサイクルへ戻す."""
        order = create_mock_order(status=OrderStatus.CANCELLED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order

        await order_service.update_status("order-123", OrderStatus.ORDERED)

        mock_order_repo.apply_cancellation_to_items.assert_called_once_with(
            order, cancelled=False
        )

    @pytest.mark.asyncio
    async def test_update_status_unrelated_transition_does_not_sync(
        self, order_service: Any, mock_order_repo: Any
    ) -> None:
        """キャンセルが絡まない遷移では波及処理を呼ばない."""
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order

        await order_service.update_status("order-123", OrderStatus.MANUFACTURING)

        mock_order_repo.apply_cancellation_to_items.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_update_status_to_cancelled_syncs_items(
        self, order_service: Any, mock_order_repo: Any
    ) -> None:
        """一括更新でも明細へキャンセルを波及させる."""
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_id.return_value = order
        mock_order_repo.update.return_value = order

        await order_service.bulk_update_status(["order-123"], OrderStatus.CANCELLED)

        mock_order_repo.apply_cancellation_to_items.assert_called_once_with(
            order, cancelled=True
        )


# ============================================================
# 発注資料（ZIP）
# ============================================================


@pytest.fixture
def manufacturer_order_service(mock_order_repo: Any) -> Any:
    manufacturer_repo = AsyncMock()
    manufacturer_repo.find_by_id.return_value = MagicMock(name="メーカー")
    return ManufacturerOrderService(
        order_repo=mock_order_repo,
        manufacturer_repo=manufacturer_repo,
        shipment_repo=AsyncMock(),
    )


def create_row(item_id: str, status: str) -> tuple[Any, ...]:
    """find_ordered_items_by_manufacturer_detail が返す行タプルのモック."""
    order_item = MagicMock()
    order_item.id = item_id
    order_item.product_type = "tshirt"
    order_item.position = "正面"
    order_item.quantity = 1
    order_item.size = "M"
    order_item.color = "白"
    order_item.uid = f"UID-{item_id}"
    order_item.product_name = "Tシャツ"
    order_item.design_image_url = None
    order_item.thumbnail_image_url = None
    order_item.manufacturing_data_id = None
    order_item.manufacturing_data = None
    order_item.is_manufacturing_ready = True
    ordered_at = datetime.now(UTC)
    # (OrderItem, order_number, ordered_at, customer_name, cost, item_status,
    #  order_status, lead_time_days)
    return (order_item, "ORD-001", ordered_at, "顧客", 500, status, status, 7)


class TestOrderDocumentsExcludeCancelled:
    """キャンセル済み明細は発注資料に含めない."""

    @pytest.mark.asyncio
    async def test_cancelled_items_are_excluded(
        self, manufacturer_order_service: Any, mock_order_repo: Any
    ) -> None:
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = [
            create_row("item-ordered", OrderItemStatus.ORDERED.value),
            create_row("item-cancelled", OrderItemStatus.CANCELLED.value),
        ]
        mock_order_repo.update_item_status_by_manufacturer.return_value = ([], set())

        await manufacturer_order_service.generate_order_documents("mfr-1")

        # 製造中への更新対象はキャンセル済みを除いた明細のみ
        _, kwargs = mock_order_repo.update_item_status_by_manufacturer.call_args
        assert kwargs["order_item_ids"] == ["item-ordered"]

    @pytest.mark.asyncio
    async def test_all_cancelled_raises_no_ordered_items(
        self, manufacturer_order_service: Any, mock_order_repo: Any
    ) -> None:
        """全明細がキャンセル済みならダウンロード対象なしとして扱う."""
        from app.utils.exceptions import NoOrderedItemsError

        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = [
            create_row("item-cancelled", OrderItemStatus.CANCELLED.value),
        ]

        with pytest.raises(NoOrderedItemsError):
            await manufacturer_order_service.generate_order_documents("mfr-1")
