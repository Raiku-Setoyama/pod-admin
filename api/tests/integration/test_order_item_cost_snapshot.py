"""明細の原価は製品の原価を後から変えても変わらないことの統合テスト（#207）.

請求書 PDF（find_ordered_items_by_manufacturer_detail）・発注リスト CSV
（find_items_by_manufacturer）・全メーカー横断の明細一覧（find_all_ordered_items_detail）が
実 DB から返す原価が、製品の今の原価ではなく明細の原価であることを確かめる。
原価が NULL の明細（デプロイの間に旧リビジョンが登録したもの）は製品の原価に戻る。
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturer import Manufacturer
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.repositories.order_repository import OrderRepository

COST_AT_CREATION = 100
COST_AFTER_CHANGE = 300


async def test_item_cost_survives_product_cost_change(db_session: AsyncSession) -> None:
    token = uuid4().hex[:10]
    manufacturer = Manufacturer(
        name=f"原価テストメーカー {token}",
        email="cost-mfg@example.com",
        supported_products=["sticker"],
        unit_prices={},
        lead_time_days=3,
        daily_order_limit=100,
    )
    db_session.add(manufacturer)
    await db_session.flush()

    product = Product(
        product_type="sticker", size="50x50mm", position=f"CS{token}",
        manufacturer_id=manufacturer.id, cost=COST_AT_CREATION, lead_time_days=3,
    )
    db_session.add(product)
    await db_session.flush()

    order = Order(
        order_number=f"CS-{token}",
        status="ordered",
        total_price=500,
        ordered_at=datetime(2026, 11, 1, 3, 0, tzinfo=UTC),
        customer_name=f"原価 {token}",
        customer_phone="090-0000-0000",
        customer_postal_code="150-0001",
        customer_address_prefecture="東京都",
        customer_address_city="渋谷区1-2-3",
    )
    db_session.add(order)
    await db_session.flush()
    item = OrderItem(
        order_id=order.id, uid="0000001", product_id=product.id,
        product_name="ステッカー", product_type="sticker", status="ordered",
        price=500, cost=product.cost, quantity=2, size="50x50mm",
    )
    # 旧リビジョンが原価なしで登録した明細
    legacy_item = OrderItem(
        order_id=order.id, uid="0000002", product_id=product.id,
        product_name="ステッカー", product_type="sticker", status="ordered",
        price=500, cost=None, quantity=1, size="50x50mm",
    )
    db_session.add_all([item, legacy_item])
    await db_session.commit()

    # 製品画面で原価を変える
    product.cost = COST_AFTER_CHANGE
    await db_session.commit()

    repo = OrderRepository(db_session)

    expected = {"0000001": COST_AT_CREATION, "0000002": COST_AFTER_CHANGE}

    detail_rows = await repo.find_ordered_items_by_manufacturer_detail(manufacturer.id)
    assert {row[0].uid: row[4] for row in detail_rows} == expected

    csv_items = await repo.find_items_by_manufacturer(manufacturer.id)
    assert {i["uid"]: i["cost"] for i in csv_items} == expected

    all_rows = await repo.find_all_ordered_items_detail(manufacturer_id=manufacturer.id)
    assert {row[0].uid: row[4] for row in all_rows} == expected
