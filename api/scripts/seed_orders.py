"""
テスト発注データ挿入スクリプト
請求書発行機能の動作確認用に発注データを挿入します。

使用方法:
    # テスト発注データを挿入
    python scripts/seed_orders.py

    # 既存の発注データを削除して再挿入
    python scripts/seed_orders.py --reset
"""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker
from app.models.manufacturer import Manufacturer
from app.models.order import Order, OrderItem, OrderStatus
from app.models.order_source import OrderSource
from app.models.product import Product


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def generate_order_number(index: int) -> str:
    """Generate order number."""
    return f"ORD-{datetime.now().strftime('%Y%m%d')}-{index:04d}"


async def reset_orders(session: AsyncSession) -> None:
    """Delete all order data."""
    print("Resetting order data...")

    # Delete in order to respect foreign key constraints
    await session.execute(text("DELETE FROM shipment_items"))
    await session.execute(text("DELETE FROM shipments"))
    await session.execute(text("DELETE FROM order_items"))
    await session.execute(text("DELETE FROM orders"))

    await session.commit()
    print("Order data reset complete.")


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


async def get_manufacturers(session: AsyncSession) -> list[Manufacturer]:
    """Get all manufacturers."""
    result = await session.execute(
        select(Manufacturer).where(Manufacturer.is_active == True)
    )
    return list(result.scalars().all())


async def get_products_by_manufacturer(
    session: AsyncSession, manufacturer_id: str
) -> list[Product]:
    """Get products by manufacturer."""
    result = await session.execute(
        select(Product).where(
            Product.manufacturer_id == manufacturer_id,
            Product.is_active == True,
        )
    )
    return list(result.scalars().all())


# Sample customer data
CUSTOMERS = [
    {
        "name": "山田 太郎",
        "postal_code": "150-0001",
        "address_prefecture": "東京都",
        "address_city": "渋谷区神宮前1-2-3",
        "address_building": "サンプルマンション101",
        "phone": "090-1234-5678",
        "email": "yamada@example.com",
    },
    {
        "name": "佐藤 花子",
        "postal_code": "160-0022",
        "address_prefecture": "東京都",
        "address_city": "新宿区新宿4-5-6",
        "address_building": "テストビル2F",
        "phone": "080-2345-6789",
        "email": "sato@example.com",
    },
    {
        "name": "鈴木 一郎",
        "postal_code": "106-0032",
        "address_prefecture": "東京都",
        "address_city": "港区六本木7-8-9",
        "address_building": None,
        "phone": "070-3456-7890",
        "email": "suzuki@example.com",
    },
    {
        "name": "田中 美咲",
        "postal_code": "141-0021",
        "address_prefecture": "東京都",
        "address_city": "品川区上大崎2-3-4",
        "address_building": "品川タワー15F",
        "phone": "090-4567-8901",
        "email": "tanaka@example.com",
    },
    {
        "name": "高橋 健太",
        "postal_code": "171-0022",
        "address_prefecture": "埼玉県",
        "address_city": "さいたま市浦和区常盤5-6-7",
        "address_building": None,
        "phone": "080-5678-9012",
        "email": "takahashi@example.com",
    },
]

# Sample product names
PRODUCT_NAMES = {
    "tshirt": [
        "オリジナルTシャツ A柄",
        "限定デザインTシャツ",
        "コラボTシャツ ver.1",
        "イベント記念Tシャツ",
    ],
    "acrylic_keychain": [
        "キャラクターキーホルダー A",
        "キャラクターキーホルダー B",
        "ロゴ入りアクキー",
        "限定アクキー",
    ],
    "acrylic_stand": [
        "キャラクターアクスタ A",
        "キャラクターアクスタ B",
        "イベント限定アクスタ",
    ],
    "sticker": [
        "ロゴステッカー",
        "キャラクターステッカー",
        "イベント記念ステッカー",
    ],
    "tote_bag": [
        "オリジナルトートバッグ",
        "コラボトートバッグ",
        "限定トートバッグ",
    ],
}


async def seed_orders(
    session: AsyncSession,
    num_orders: int = 20,
) -> None:
    """Create test orders with order items."""
    print(f"Creating {num_orders} test orders...")

    # Get or create TEST OrderSource
    test_order_source = await get_or_create_test_order_source(session)
    print(f"  Using OrderSource: {test_order_source.code} (ID: {test_order_source.id[:8]}...)")

    manufacturers = await get_manufacturers(session)
    if not manufacturers:
        print("  Error: No manufacturers found. Run 'python scripts/seed.py' first.")
        return

    # Get products for each manufacturer
    manufacturer_products: dict[str, list[Product]] = {}
    for mfr in manufacturers:
        products = await get_products_by_manufacturer(session, mfr.id)
        if products:
            manufacturer_products[mfr.id] = products

    if not manufacturer_products:
        print("  Error: No products found. Run 'python scripts/seed.py' first.")
        return

    # Create orders
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)

    orders_created = 0
    items_created = 0

    for i in range(num_orders):
        # Random customer
        customer = random.choice(CUSTOMERS)

        # Random ordered date (within last 30 days)
        days_ago = random.randint(0, 30)
        ordered_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))

        # Create order
        order = Order(
            id=generate_uuid(),
            order_number=generate_order_number(i + 1),
            status=OrderStatus.ORDERED.value,
            order_source_id=test_order_source.id,
            customer_name=customer["name"],
            customer_postal_code=customer["postal_code"],
            customer_address_prefecture=customer["address_prefecture"],
            customer_address_city=customer["address_city"],
            customer_address_building=customer["address_building"],
            customer_phone=customer["phone"],
            customer_email=customer["email"],
            ordered_at=ordered_at,
            total_price=0,
        )
        session.add(order)

        # Create 1-3 order items per order
        num_items = random.randint(1, 3)
        total_price = 0

        # Pick a random manufacturer for this order
        mfr_id = random.choice(list(manufacturer_products.keys()))
        products = manufacturer_products[mfr_id]

        for j in range(num_items):
            product = random.choice(products)
            quantity = random.randint(1, 5)
            price = random.randint(1500, 5000)

            # Get product name
            product_type = product.product_type
            product_name_list = PRODUCT_NAMES.get(product_type, ["商品"])
            product_name = random.choice(product_name_list)

            order_item = OrderItem(
                id=generate_uuid(),
                order_id=order.id,
                uid=f"UID-{i+1:04d}-{j+1:02d}",
                product_id=product.id,
                product_name=product_name,
                product_type=product_type,
                price=price,
                quantity=quantity,
                size=product.size,
                position=product.position,
                color=product.color,
                design_image_url=None,
                thumbnail_image_url=None,
            )
            session.add(order_item)
            total_price += price * quantity
            items_created += 1

        order.total_price = total_price
        orders_created += 1

    await session.flush()
    print(f"  Created {orders_created} orders with {items_created} order items")


async def update_manufacturer_invoice_fields(session: AsyncSession) -> None:
    """Update manufacturers with invoice-related fields for testing."""
    print("Updating manufacturers with invoice fields...")

    manufacturers = await get_manufacturers(session)

    invoice_data = [
        {
            "postal_code": "150-0001",
            "address": "東京都渋谷区神宮前1-2-3 シードットビル5F",
            "bank_name": "三菱UFJ銀行",
            "bank_branch": "渋谷支店",
            "bank_account_type": "普通",
            "bank_account_number": "1234567",
            "bank_account_holder": "カ）シードット",
            "representative_name": "代表取締役 山田太郎",
            "invoice_notes": "お支払いは請求月の翌月末日までにお願いいたします。",
        },
        {
            "postal_code": "160-0022",
            "address": "東京都新宿区新宿4-5-6 トートメーカービル3F",
            "bank_name": "みずほ銀行",
            "bank_branch": "新宿支店",
            "bank_account_type": "普通",
            "bank_account_number": "7654321",
            "bank_account_holder": "カ）サンプルメーカー",
            "representative_name": "代表取締役 佐藤花子",
            "invoice_notes": None,
        },
    ]

    for i, mfr in enumerate(manufacturers):
        if i < len(invoice_data):
            data = invoice_data[i]
            mfr.postal_code = data["postal_code"]
            mfr.address = data["address"]
            mfr.bank_name = data["bank_name"]
            mfr.bank_branch = data["bank_branch"]
            mfr.bank_account_type = data["bank_account_type"]
            mfr.bank_account_number = data["bank_account_number"]
            mfr.bank_account_holder = data["bank_account_holder"]
            mfr.representative_name = data["representative_name"]
            mfr.invoice_notes = data["invoice_notes"]

    await session.flush()
    print(f"  Updated {len(manufacturers)} manufacturers")


async def main(reset: bool = False, num_orders: int = 20) -> None:
    """Main seed function."""
    print("=" * 50)
    print("POD Admin - Test Order Data Seeder")
    print("=" * 50)

    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            if reset:
                await reset_orders(session)

            await update_manufacturer_invoice_fields(session)
            await seed_orders(session, num_orders)

            await session.commit()

            print("=" * 50)
            print("Test order data seeding completed!")
            print("=" * 50)
            print("\nYou can now test invoice generation:")
            print("  1. Login to admin panel (admin@example.com / admin123)")
            print("  2. Go to /purchase-orders and select a manufacturer")
            print("  3. Select order items and click '請求書発行' button")
            print("")

        except Exception as e:
            await session.rollback()
            print(f"Error during seeding: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed database with test order data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset order data before seeding (delete all existing orders)",
    )
    parser.add_argument(
        "--num-orders",
        type=int,
        default=20,
        help="Number of orders to create (default: 20)",
    )
    args = parser.parse_args()

    asyncio.run(main(reset=args.reset, num_orders=args.num_orders))
