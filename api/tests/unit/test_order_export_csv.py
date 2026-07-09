"""Unit tests for OrderService.export_csv() product type column (Issue #79).

OrderService.export_csv generates the delivery-company CSV for pending orders
(orders that do not have a Shipment yet). Its "商品種類" column (4th) must be
formatted identically to the shipment CSV and the order list (発注リスト):
{商品種類} - {サイズ} - {位置} - {色}.
"""

import csv
import io
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderItem
from app.models.order_source import OrderSource
from app.services.order_service import OrderService

# 商品種類 column index in the delivery CSV (0-based)
PRODUCT_TYPE_COL = 3


@pytest.fixture
def order_service():
    """OrderService with mocked dependencies (order_source_repo configured)."""
    return OrderService(
        order_repo=AsyncMock(),
        product_repo=AsyncMock(),
        shipment_repo=AsyncMock(),
        order_source_repo=AsyncMock(),
    )


def _order_source() -> MagicMock:
    source = MagicMock(spec=OrderSource)
    source.name = "テスト配送元"
    source.phone = "03-1234-5678"
    source.postal_code = "100-0001"
    source.address_prefecture = "東京都"
    source.address_city = "千代田区1-1-1"
    source.address_building = "テストビル101"
    return source


def _order_item(
    product_type: str,
    size: str | None = None,
    position: str | None = None,
    color: str | None = None,
) -> MagicMock:
    item = MagicMock(spec=OrderItem)
    item.product_name = "テスト商品"
    item.product_type = product_type
    item.quantity = 1
    item.uid = "ITEM-001"
    item.size = size
    item.position = position
    item.color = color
    return item


def _order(item: MagicMock) -> MagicMock:
    order = MagicMock(spec=Order)
    order.id = "order-001"
    order.order_number = "ORD-0001"
    order.customer_name = "テスト顧客"
    order.customer_phone = "090-0000-0000"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "東京都"
    order.customer_address_city = "千代田区1-1-1"
    order.customer_address_building = ""
    order.items = [item]
    order.order_source = _order_source()
    return order


class TestOrderExportCsvProductDetail:
    """Issue #79: order delivery CSV 商品種類 column uses the unified format."""

    async def _export_detail(self, order_service, item) -> str:
        order_service._order_repo.find_by_id.return_value = _order(item)
        csv_bytes, _ = await order_service.export_csv(["order-001"])
        rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
        return rows[1][PRODUCT_TYPE_COL]

    @pytest.mark.asyncio
    async def test_includes_size_position_color(self, order_service):
        """Tシャツはサイズ・位置・色を半角 ' - ' で連結して出力する."""
        detail = await self._export_detail(
            order_service, _order_item("tshirt", "L", "正面", "白")
        )
        assert detail == "Tシャツ - L - 正面 - 白"

    @pytest.mark.asyncio
    async def test_acrylic_stand_maps_to_acrylic_figure_and_skips_empty(
        self, order_service
    ):
        """acrylic_stand は「アクリルフィギュア」となり、位置なしはスキップされる."""
        detail = await self._export_detail(
            order_service, _order_item("acrylic_stand", "100mm", None, "クリア")
        )
        assert detail == "アクリルフィギュア - 100mm - クリア"
