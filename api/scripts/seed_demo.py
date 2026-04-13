"""
受注・配送のデモデータ挿入スクリプト
各ステータスをカバーするリアルなデモデータを作成します。

使用方法:
    # デモデータを挿入（既存データをリセットしてから挿入）
    python scripts/seed_demo.py

    # リセットせずに追加挿入
    python scripts/seed_demo.py --no-reset
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
from app.models.order import Order, OrderItem, OrderItemStatus, OrderStatus
from app.models.order_source import OrderSource
from app.models.product import Product
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)


def gen_id() -> str:
    return str(uuid.uuid4())


# --- 顧客データ ---
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
    {
        "name": "伊藤 由美",
        "postal_code": "220-0011",
        "address_prefecture": "神奈川県",
        "address_city": "横浜市西区高島2-19-12",
        "address_building": "スカイビル8F",
        "phone": "090-6789-0123",
        "email": "ito@example.com",
    },
    {
        "name": "渡辺 大輔",
        "postal_code": "530-0001",
        "address_prefecture": "大阪府",
        "address_city": "大阪市北区梅田1-3-1",
        "address_building": "大阪駅前ビル12F",
        "phone": "080-7890-1234",
        "email": "watanabe@example.com",
    },
    {
        "name": "中村 さくら",
        "postal_code": "460-0008",
        "address_prefecture": "愛知県",
        "address_city": "名古屋市中区栄3-5-1",
        "address_building": None,
        "phone": "070-8901-2345",
        "email": "nakamura@example.com",
    },
]

# 商品名バリエーション
PRODUCT_NAMES = {
    "tshirt": [
        "オリジナルTシャツ A柄",
        "限定デザインTシャツ",
        "コラボTシャツ ver.1",
        "イベント記念Tシャツ",
        "推しTシャツ 夏限定",
    ],
    "acrylic_keychain": [
        "キャラクターキーホルダー A",
        "キャラクターキーホルダー B",
        "ロゴ入りアクキー",
        "限定アクキー 春ver.",
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

CARRIERS = ["ヤマト運輸", "佐川急便", "日本郵便"]


async def reset_data(session: AsyncSession) -> None:
    """注文・配送データを削除（マスタデータは残す）。"""
    print("Resetting order/shipment data...")
    await session.execute(text("DELETE FROM shipment_items"))
    await session.execute(text("DELETE FROM shipments"))
    await session.execute(text("DELETE FROM order_items"))
    await session.execute(text("DELETE FROM orders"))
    await session.commit()
    print("  Done.")


async def get_or_create_order_sources(session: AsyncSession) -> list[OrderSource]:
    """受注元を取得または作成。"""
    sources_data = [
        {
            "code": "SUZURI",
            "name": "SUZURI",
            "phone": "03-1111-1111",
            "postal_code": "150-0001",
            "address_prefecture": "東京都",
            "address_city": "渋谷区神宮前6-25-16",
        },
        {
            "code": "BASE",
            "name": "BASE",
            "phone": "03-2222-2222",
            "postal_code": "106-0032",
            "address_prefecture": "東京都",
            "address_city": "港区六本木3-2-1",
        },
    ]

    sources = []
    for data in sources_data:
        result = await session.execute(
            select(OrderSource).where(OrderSource.code == data["code"])
        )
        source = result.scalar_one_or_none()
        if not source:
            source = OrderSource(
                id=gen_id(),
                api_key=f"api-key-{data['code'].lower()}",
                is_active=True,
                **data,
            )
            session.add(source)
        sources.append(source)

    await session.flush()
    return sources


async def get_products_map(session: AsyncSession) -> dict[str, list[Product]]:
    """製造委託先ごとの製品マップを取得。"""
    result = await session.execute(select(Product).where(Product.is_active == True))
    products = list(result.scalars().all())
    if not products:
        raise RuntimeError("No products found. Run 'python scripts/seed.py' first.")

    by_manufacturer: dict[str, list[Product]] = {}
    for p in products:
        by_manufacturer.setdefault(p.manufacturer_id, []).append(p)
    return by_manufacturer


def make_order_items(
    order_id: str,
    order_index: int,
    products: list[Product],
    num_items: int,
    item_status: str,
) -> tuple[list[OrderItem], int]:
    """注文明細を生成。"""
    items = []
    total = 0
    for j in range(num_items):
        product = random.choice(products)
        quantity = random.randint(1, 5)
        price = random.randint(1500, 5000)
        name_list = PRODUCT_NAMES.get(product.product_type, ["商品"])

        item = OrderItem(
            id=gen_id(),
            order_id=order_id,
            uid=f"{(order_index + 1) * 100 + (j + 1):07d}",
            product_id=product.id,
            product_name=random.choice(name_list),
            product_type=product.product_type,
            status=item_status,
            price=price,
            quantity=quantity,
            size=product.size,
            position=product.position,
            color=product.color,
        )
        items.append(item)
        total += price * quantity
    return items, total


async def seed_demo_data(session: AsyncSession) -> None:
    """デモデータを一括作成。"""
    sources = await get_or_create_order_sources(session)
    products_map = await get_products_map(session)
    mfr_ids = list(products_map.keys())

    order_counter = 0
    all_orders: list[tuple[Order, str]] = []  # (order, category)

    # ========================================
    # 1) 受注済み（未着手）: 8件
    # ========================================
    print("Creating 受注済み orders (8)...")
    for i in range(8):
        customer = random.choice(CUSTOMERS)
        source = random.choice(sources)
        mfr_id = random.choice(mfr_ids)
        days_ago = random.randint(0, 5)
        ordered_at = NOW - timedelta(days=days_ago, hours=random.randint(0, 12))

        order_id = gen_id()
        order = Order(
            id=order_id,
            order_number=f"ORD-{NOW.strftime('%Y%m')}-{order_counter + 1:04d}",
            status=OrderStatus.ORDERED.value,
            order_source_id=source.id,
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

        num_items = random.randint(1, 3)
        items, total = make_order_items(
            order_id, order_counter, products_map[mfr_id], num_items,
            OrderItemStatus.ORDERED.value,
        )
        for item in items:
            session.add(item)
        order.total_price = total

        all_orders.append((order, "ordered"))
        order_counter += 1

    # ========================================
    # 2) 製造中: 6件
    # ========================================
    print("Creating 製造中 orders (6)...")
    for i in range(6):
        customer = random.choice(CUSTOMERS)
        source = random.choice(sources)
        mfr_id = random.choice(mfr_ids)
        days_ago = random.randint(3, 10)
        ordered_at = NOW - timedelta(days=days_ago)

        order_id = gen_id()
        order = Order(
            id=order_id,
            order_number=f"ORD-{NOW.strftime('%Y%m')}-{order_counter + 1:04d}",
            status=OrderStatus.MANUFACTURING.value,
            order_source_id=source.id,
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

        num_items = random.randint(1, 3)
        items, total = make_order_items(
            order_id, order_counter, products_map[mfr_id], num_items,
            OrderItemStatus.MANUFACTURING.value,
        )
        for item in items:
            session.add(item)
        order.total_price = total

        all_orders.append((order, "manufacturing"))
        order_counter += 1

    # ========================================
    # 3) 納入済み（配送待ち）: 10件
    # ========================================
    print("Creating 納入済み orders (10)...")
    delivered_orders: list[Order] = []
    for i in range(10):
        customer = random.choice(CUSTOMERS)
        source = random.choice(sources)
        mfr_id = random.choice(mfr_ids)
        days_ago = random.randint(5, 15)
        ordered_at = NOW - timedelta(days=days_ago)

        order_id = gen_id()
        order = Order(
            id=order_id,
            order_number=f"ORD-{NOW.strftime('%Y%m')}-{order_counter + 1:04d}",
            status=OrderStatus.DELIVERED.value,
            order_source_id=source.id,
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

        num_items = random.randint(1, 4)
        items, total = make_order_items(
            order_id, order_counter, products_map[mfr_id], num_items,
            OrderItemStatus.DELIVERED.value,
        )
        for item in items:
            session.add(item)
        order.total_price = total

        delivered_orders.append(order)
        all_orders.append((order, "delivered"))
        order_counter += 1

    # ========================================
    # 4) 発送完了: 8件
    # ========================================
    print("Creating 発送完了 orders (8)...")
    shipped_orders: list[Order] = []
    for i in range(8):
        customer = random.choice(CUSTOMERS)
        source = random.choice(sources)
        mfr_id = random.choice(mfr_ids)
        days_ago = random.randint(10, 25)
        ordered_at = NOW - timedelta(days=days_ago)

        order_id = gen_id()
        order = Order(
            id=order_id,
            order_number=f"ORD-{NOW.strftime('%Y%m')}-{order_counter + 1:04d}",
            status=OrderStatus.SHIPPED.value,
            order_source_id=source.id,
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

        num_items = random.randint(1, 3)
        items, total = make_order_items(
            order_id, order_counter, products_map[mfr_id], num_items,
            OrderItemStatus.DELIVERED.value,
        )
        for item in items:
            session.add(item)
        order.total_price = total

        shipped_orders.append(order)
        all_orders.append((order, "shipped"))
        order_counter += 1

    # ========================================
    # 5) キャンセル: 3件
    # ========================================
    print("Creating キャンセル orders (3)...")
    for i in range(3):
        customer = random.choice(CUSTOMERS)
        source = random.choice(sources)
        mfr_id = random.choice(mfr_ids)
        days_ago = random.randint(5, 20)
        ordered_at = NOW - timedelta(days=days_ago)

        order_id = gen_id()
        order = Order(
            id=order_id,
            order_number=f"ORD-{NOW.strftime('%Y%m')}-{order_counter + 1:04d}",
            status=OrderStatus.CANCELLED.value,
            order_source_id=source.id,
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

        num_items = random.randint(1, 2)
        items, total = make_order_items(
            order_id, order_counter, products_map[mfr_id], num_items,
            OrderItemStatus.ORDERED.value,
        )
        for item in items:
            session.add(item)
        order.total_price = total

        all_orders.append((order, "cancelled"))
        order_counter += 1

    await session.flush()
    print(f"  Total orders created: {order_counter}")

    # ========================================
    # 配送データ
    # ========================================

    shipment_count = 0

    # 6) 配送準備待ち (pending): 納入済み注文から4件
    print("Creating 配送準備待ち shipments (4)...")
    for order in delivered_orders[:4]:
        shipment_id = gen_id()
        shipment = Shipment(
            id=shipment_id,
            status=ShipmentStatus.PENDING.value,
        )
        session.add(shipment)
        session.add(ShipmentItem(
            id=gen_id(),
            shipment_id=shipment_id,
            order_id=order.id,
        ))
        shipment_count += 1

    # 7) 配送準備完了 (ready): 納入済み注文から3件
    print("Creating 配送準備完了 shipments (3)...")
    for order in delivered_orders[4:7]:
        shipment_id = gen_id()
        tracking = f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
        shipment = Shipment(
            id=shipment_id,
            status=ShipmentStatus.READY.value,
            tracking_number=tracking,
            carrier=random.choice(CARRIERS),
        )
        session.add(shipment)
        session.add(ShipmentItem(
            id=gen_id(),
            shipment_id=shipment_id,
            order_id=order.id,
        ))
        shipment_count += 1

    # 8) 複数注文をまとめた配送 (pending): 残りの納入済み注文
    print("Creating 複数注文まとめ shipment (1)...")
    if len(delivered_orders) > 7:
        shipment_id = gen_id()
        shipment = Shipment(
            id=shipment_id,
            status=ShipmentStatus.PENDING.value,
            note="同一顧客の複数注文をまとめて配送",
        )
        session.add(shipment)
        for order in delivered_orders[7:]:
            session.add(ShipmentItem(
                id=gen_id(),
                shipment_id=shipment_id,
                order_id=order.id,
            ))
        shipment_count += 1

    # 9) 発送完了 (shipped): 発送完了注文から配送データ
    print("Creating 発送完了 shipments (8)...")
    for i, order in enumerate(shipped_orders):
        shipment_id = gen_id()
        days_ago = random.randint(3, 15)
        shipped_at = NOW - timedelta(days=days_ago)

        shipment = Shipment(
            id=shipment_id,
            status=ShipmentStatus.SHIPPED.value,
            tracking_number=f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
            carrier=random.choice(CARRIERS),
            shipped_at=shipped_at,
            delivered_at=shipped_at + timedelta(days=random.randint(1, 3)) if i < 5 else None,
            shipping_email_sent=True if i < 6 else False,
            note="お届け完了" if i < 5 else None,
        )
        session.add(shipment)
        session.add(ShipmentItem(
            id=gen_id(),
            shipment_id=shipment_id,
            order_id=order.id,
        ))
        shipment_count += 1

    await session.flush()
    print(f"  Total shipments created: {shipment_count}")


async def main(reset: bool = True) -> None:
    print("=" * 50)
    print("POD Admin - Demo Data Seeder")
    print("=" * 50)

    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            if not reset:
                # Check if data already exists
                result = await session.execute(
                    select(Order).limit(1)
                )
                if result.scalar_one_or_none() is not None:
                    print("Data already exists, skipping seed (use without --no-reset to reset)")
                    return

            if reset:
                await reset_data(session)

            await seed_demo_data(session)
            await session.commit()

            print("=" * 50)
            print("Demo data created!")
            print("=" * 50)
            print()
            print("受注データ:")
            print("  受注済み:     8件")
            print("  製造中:       6件")
            print("  納入済み:    10件")
            print("  発送完了:     8件")
            print("  キャンセル:   3件")
            print("  合計:        35件")
            print()
            print("配送データ:")
            print("  配送準備待ち:   4件 + 1件(複数注文まとめ)")
            print("  配送準備完了:   3件")
            print("  発送完了:       8件")
            print("  合計:          16件")
            print()
            print("Login: admin@example.com / admin123")

        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not reset existing data before seeding",
    )
    args = parser.parse_args()

    asyncio.run(main(reset=not args.no_reset))
