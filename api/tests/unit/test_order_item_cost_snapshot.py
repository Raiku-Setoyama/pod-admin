"""受注明細に作成時点のメーカー原価を残すことのテスト（#207）.

請求書・発注リストは明細の原価（OrderItem.cost）を使う。製品の原価を後から変えても、
既にある明細の原価は変わらないことを確かめる。
"""

from datetime import date

from app.models.product import Product, ProductType
from app.schemas.order import OrderItemCreate, OrderItemCreateV2, SourceImage
from app.services.order_service import OrderService


def _product(cost: int) -> Product:
    return Product(id="prod-1", product_type=ProductType.STICKER.value, cost=cost)


def _v1_item() -> OrderItemCreate:
    return OrderItemCreate(
        uid="0000001",
        product_type=ProductType.STICKER,
        product_name="ステッカー",
        price=500,
        quantity=2,
        size="50x50mm",
    )


def _v2_item() -> OrderItemCreateV2:
    return OrderItemCreateV2(
        uid="0000002",
        product_type=ProductType.STICKER,
        product_name="ステッカー",
        price=500,
        quantity=1,
        size="50x50mm",
        product_code="code-1",
        source_images=[SourceImage(layer_type="color", url="https://example.com/c.png")],
    )


class TestOrderItemCostSnapshot:
    def test_v1_item_takes_product_cost_at_creation(self) -> None:
        product = _product(cost=120)
        item = OrderService._build_v1_item(_v1_item(), product, date(2026, 11, 30))
        assert item.cost == 120

    def test_v2_item_takes_product_cost_at_creation(self) -> None:
        product = _product(cost=150)
        item = OrderService._build_v2_item(_v2_item(), product, date(2026, 11, 30))
        assert item.cost == 150

    def test_changing_product_cost_later_keeps_item_cost(self) -> None:
        product = _product(cost=120)
        item = OrderService._build_v1_item(_v1_item(), product, date(2026, 11, 30))

        product.cost = 300

        assert item.cost == 120
