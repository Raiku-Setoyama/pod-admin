"""
配送準備中ステータスのテスト配送データを1件作成するスクリプト

使用方法:
    python scripts/seed_test_shipment.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker
from app.models.order import Order, OrderItem, OrderStatus
from app.models.order_source import OrderSource
from app.models.product import Product
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


async def get_first_product(session: AsyncSession) -> Product | None:
    """Get any active product."""
    result = await session.execute(
        select(Product).where(Product.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


async def get_or_create_test_order_source(session: AsyncSession) -> OrderSource:
    """Get or create TEST OrderSource."""
    result = await session.execute(
        select(OrderSource).where(OrderSource.code == "TEST")
    )
    order_source = result.scalar_one_or_none()
    if order_source:
        return order_source

    # Create TEST OrderSource if it doesn't exist
    order_source = OrderSource(
        id=generate_uuid(),
        code="TEST",
        api_key="test-api-key",
        name="テスト配送元",
        phone="03-0000-0000",
        postal_code="000-0000",
        address_prefecture="東京都",
        address_city="テスト市1-1-1",
        is_active=True,
    )
    session.add(order_source)
    await session.flush()
    return order_source


async def create_test_shipment(session: AsyncSession) -> None:
    """Create a test order with shipment in pending status."""
    print("Creating test shipment data...")

    # Get a product
    product = await get_first_product(session)
    if not product:
        print("  Error: No active products found. Run 'python scripts/seed.py' first.")
        return

    # Get or create TEST OrderSource
    test_order_source = await get_or_create_test_order_source(session)
    print(f"  Using OrderSource: {test_order_source.code} (ID: {test_order_source.id[:8]}...)")

    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)

    # Create order
    order_id = generate_uuid()
    order_number = f"TEST-{now.strftime('%Y%m%d%H%M%S')}"

    order = Order(
        id=order_id,
        order_number=order_number,
        status=OrderStatus.DELIVERED.value,  # Set to delivered so shipment can be created
        order_source_id=test_order_source.id,
        customer_name="テスト 太郎",
        customer_postal_code="150-0001",
        customer_address_prefecture="東京都",
        customer_address_city="渋谷区神宮前1-2-3",
        customer_address_building="テストビル101",
        customer_phone="090-1234-5678",
        customer_email="test@example.com",
        ordered_at=now,
        total_price=3000,
    )
    session.add(order)
    await session.flush()

    # Create order item
    order_item = OrderItem(
        id=generate_uuid(),
        order_id=order_id,
        uid=f"TEST-ITEM-{now.strftime('%H%M%S')}",
        product_id=product.id,
        product_name="テスト商品 アクリルキーホルダー",
        product_type=product.product_type,
        price=1500,
        quantity=2,
        size=product.size,
        position=product.position,
        color=product.color,
    )
    session.add(order_item)
    await session.flush()

    # Create shipment with pending status
    shipment_id = generate_uuid()
    shipment = Shipment(
        id=shipment_id,
        status=ShipmentStatus.PENDING.value,
    )
    session.add(shipment)
    await session.flush()

    # Create shipment item linking to order
    shipment_item = ShipmentItem(
        id=generate_uuid(),
        shipment_id=shipment_id,
        order_id=order_id,
    )
    session.add(shipment_item)
    await session.flush()

    print(f"  Created order: {order_number} (ID: {order_id[:8]}...)")
    print(f"  Created shipment: {shipment_id[:8]}... (status: pending)")
    print(f"  Customer: {order.customer_name}")
    print(f"  Address: {order.customer_address_prefecture}{order.customer_address_city} {order.customer_address_building or ''}")


async def main() -> None:
    """Main function."""
    print("=" * 50)
    print("POD Admin - Test Shipment Data Creator")
    print("=" * 50)

    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            await create_test_shipment(session)
            await session.commit()

            print("=" * 50)
            print("Test data created successfully!")
            print("=" * 50)
            print("\nYou can now test:")
            print("  1. Go to /shipments in the admin panel")
            print("  2. Find the shipment with status '配送準備中'")
            print("  3. Test CSV export and other functions")
            print("")

        except Exception as e:
            await session.rollback()
            print(f"Error during creation: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
