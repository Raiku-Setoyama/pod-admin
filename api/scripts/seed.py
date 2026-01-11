"""
シードデータスクリプト
動作確認用のサンプルデータをDBに挿入します。

使用方法:
    # シードデータを挿入
    python scripts/seed.py

    # データをリセットして再挿入
    python scripts/seed.py --reset
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_engine, get_session_maker
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.manufacturer import Manufacturer, SharingMethod
from app.models.product import Product, ProductType
from app.models.order import Order, OrderItem, OrderStatus
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.models.chat_message import ChatMessage, ChatAttachment, MessageSender
from app.utils.security import hash_password


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


async def reset_database(session: AsyncSession) -> None:
    """Delete all data from tables (in correct order to handle foreign keys)."""
    print("Resetting database...")

    # Delete in order to respect foreign key constraints
    tables_to_clear = [
        "chat_attachments",
        "chat_messages",
        "shipment_items",
        "shipments",
        "order_items",
        "orders",
        "products",
        "manufacturers",
        "users",
    ]

    for table in tables_to_clear:
        await session.execute(text(f"DELETE FROM {table}"))

    await session.commit()
    print("Database reset complete.")


async def seed_users(session: AsyncSession) -> dict[str, User]:
    """Create test users."""
    print("Creating users...")

    users = {}

    # Admin user
    admin = User(
        id=generate_uuid(),
        email="admin@example.com",
        password_hash=hash_password("admin123"),
        name="管理者",
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    users["admin"] = admin

    # Operator user
    operator = User(
        id=generate_uuid(),
        email="operator@example.com",
        password_hash=hash_password("operator123"),
        name="オペレーター",
        role=UserRole.OPERATOR,
        is_active=True,
    )
    session.add(operator)
    users["operator"] = operator

    await session.flush()
    print(f"  Created {len(users)} users")
    return users


async def seed_manufacturers(session: AsyncSession) -> dict[str, Manufacturer]:
    """Create test manufacturers."""
    print("Creating manufacturers...")

    manufacturers_data = [
        {
            "id": generate_uuid(),
            "name": "Tシャツプリント",
            "email": "support@tshirt-print.jp",
            "phone": "092-4567-8901",
            "supported_products": ["tshirt"],
            "unit_prices": {"tshirt": 1000},
            "lead_time_days": 10,
            "daily_order_limit": 200,
            "sharing_method": SharingMethod.PORTAL.value,
            "password_hash": hash_password("manufacturer123"),
            "is_active": True,
        },
    ]

    manufacturers = {}
    for data in manufacturers_data:
        mfr = Manufacturer(**data)
        session.add(mfr)
        manufacturers[data["name"]] = mfr

    await session.flush()
    print(f"  Created {len(manufacturers)} manufacturers")
    return manufacturers


async def seed_products(session: AsyncSession, manufacturers: dict[str, Manufacturer]) -> dict[str, Product]:
    """Create test products."""
    print("Creating products...")

    products_data = [
        {
            "id": generate_uuid(),
            "product_type": ProductType.TSHIRT.value,
            "name": "オリジナルTシャツ",
            "size": "M/L/XL",
            "color": "白",
            "manufacturer_id": manufacturers["Tシャツプリント"].id,
            "cost": 1000,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
    ]

    products = {}
    for data in products_data:
        product = Product(**data)
        session.add(product)
        products[data["name"]] = product

    await session.flush()
    print(f"  Created {len(products)} products")
    return products


async def seed_orders(session: AsyncSession, products: dict[str, Product]) -> dict[str, Order]:
    """Create test orders with order items."""
    print("Creating orders...")

    now = datetime.now(timezone.utc)
    tshirt = products["オリジナルTシャツ"]

    # Order data with items
    orders_data = [
        {
            "order": {
                "id": generate_uuid(),
                "order_number": "ORD-2024-0001",
                "status": OrderStatus.ORDERED.value,
                "customer_name": "田中太郎",
                "customer_postal_code": "160-0023",
                "customer_address": "東京都新宿区西新宿1-1-1 新宿ビル101",
                "customer_phone": "090-1234-5678",
                "customer_email": "tanaka@example.com",
                "ordered_at": now - timedelta(days=7),
            },
            "items": [
                {
                    "product": tshirt,
                    "uid": "EXT-001-001",
                    "price": 2500,
                    "quantity": 2,
                    "size": "L",
                    "color": "白",
                },
            ],
        },
        {
            "order": {
                "id": generate_uuid(),
                "order_number": "ORD-2024-0002",
                "status": OrderStatus.ORDERED.value,
                "customer_name": "山田花子",
                "customer_postal_code": "542-0076",
                "customer_address": "大阪府大阪市中央区難波2-2-2",
                "customer_phone": "080-2345-6789",
                "customer_email": "yamada@example.com",
                "ordered_at": now - timedelta(days=6),
            },
            "items": [
                {
                    "product": tshirt,
                    "uid": "EXT-002-001",
                    "price": 2500,
                    "quantity": 3,
                    "size": "M",
                    "color": "白",
                },
            ],
        },
        {
            "order": {
                "id": generate_uuid(),
                "order_number": "ORD-2024-0003",
                "status": OrderStatus.SHIPPED.value,
                "customer_name": "佐藤一郎",
                "customer_postal_code": "450-0002",
                "customer_address": "愛知県名古屋市中村区名駅3-3-3",
                "customer_phone": "070-3456-7890",
                "customer_email": "sato@example.com",
                "ordered_at": now - timedelta(days=9),
            },
            "items": [
                {
                    "product": tshirt,
                    "uid": "EXT-003-001",
                    "price": 2500,
                    "quantity": 5,
                    "size": "XL",
                    "color": "白",
                },
            ],
        },
        {
            "order": {
                "id": generate_uuid(),
                "order_number": "ORD-2024-0004",
                "status": OrderStatus.SHIPPED.value,
                "customer_name": "鈴木美咲",
                "customer_postal_code": "812-0011",
                "customer_address": "福岡県福岡市博多区博多駅前4-4-4",
                "customer_phone": "090-4567-8901",
                "customer_email": "suzuki@example.com",
                "ordered_at": now - timedelta(days=12),
            },
            "items": [
                {
                    "product": tshirt,
                    "uid": "EXT-004-001",
                    "price": 2500,
                    "quantity": 1,
                    "size": "M",
                    "color": "白",
                },
            ],
        },
        {
            "order": {
                "id": generate_uuid(),
                "order_number": "ORD-2024-0005",
                "status": OrderStatus.MANUFACTURING.value,
                "customer_name": "高橋健太",
                "customer_postal_code": "060-0042",
                "customer_address": "北海道札幌市中央区大通西5-5-5",
                "customer_phone": "080-5678-9012",
                "customer_email": "takahashi@example.com",
                "ordered_at": now - timedelta(days=5),
            },
            "items": [
                {
                    "product": tshirt,
                    "uid": "EXT-005-001",
                    "price": 2500,
                    "quantity": 3,
                    "size": "L",
                    "color": "白",
                },
            ],
        },
        {
            "order": {
                "id": generate_uuid(),
                "order_number": "ORD-2024-0006",
                "status": OrderStatus.DELIVERED.value,
                "customer_name": "伊藤めぐみ",
                "customer_postal_code": "980-0811",
                "customer_address": "宮城県仙台市青葉区一番町6-6-6",
                "customer_phone": "070-6789-0123",
                "customer_email": "ito@example.com",
                "ordered_at": now - timedelta(days=8),
            },
            "items": [
                {
                    "product": tshirt,
                    "uid": "EXT-006-001",
                    "price": 2500,
                    "quantity": 4,
                    "size": "M",
                    "color": "白",
                },
            ],
        },
        {
            "order": {
                "id": generate_uuid(),
                "order_number": "ORD-2024-0007",
                "status": OrderStatus.ORDERED.value,
                "customer_name": "渡辺健一",
                "customer_postal_code": "530-0001",
                "customer_address": "大阪府大阪市北区梅田1-1-1",
                "customer_phone": "090-7890-1234",
                "customer_email": "watanabe@example.com",
                "ordered_at": now - timedelta(days=3),
            },
            "items": [
                {
                    "product": tshirt,
                    "uid": "EXT-007-001",
                    "price": 2500,
                    "quantity": 2,
                    "size": "L",
                    "color": "白",
                },
                {
                    "product": tshirt,
                    "uid": "EXT-007-002",
                    "price": 2500,
                    "quantity": 3,
                    "size": "XL",
                    "color": "白",
                },
            ],
        },
    ]

    orders = {}
    total_items = 0

    for data in orders_data:
        order_data = data["order"]

        # Calculate total price from items
        total_price = sum(
            item["price"] * item["quantity"] for item in data["items"]
        )
        order_data["total_price"] = total_price

        # Create order
        order = Order(**order_data)
        session.add(order)

        # Create order items
        for item_data in data["items"]:
            product = item_data["product"]
            order_item = OrderItem(
                id=generate_uuid(),
                order_id=order_data["id"],
                uid=item_data["uid"],
                product_id=product.id,
                product_name=product.name,
                product_type=product.product_type,
                price=item_data["price"],
                quantity=item_data["quantity"],
                size=item_data.get("size"),
                color=item_data.get("color"),
                position=item_data.get("position"),
                design_image_url=item_data.get("design_image_url"),
                thumbnail_image_url=item_data.get("thumbnail_image_url"),
            )
            session.add(order_item)
            total_items += 1

        orders[order_data["order_number"]] = order

    await session.flush()
    print(f"  Created {len(orders)} orders with {total_items} order items")
    return orders


async def seed_shipments(session: AsyncSession, orders: dict[str, Order]) -> dict[str, Shipment]:
    """Create test shipments."""
    print("Creating shipments...")

    now = datetime.now(timezone.utc)

    shipments_data = [
        {
            "id": generate_uuid(),
            "status": ShipmentStatus.SHIPPED.value,
            "tracking_number": "1234-5678-9012",
            "carrier": "yamato",
            "shipped_at": now - timedelta(days=5),
            "delivered_at": now - timedelta(days=2),
            "customer_name": "佐藤一郎",
            "customer_postal_code": "450-0002",
            "customer_address": "愛知県名古屋市中村区名駅3-3-3",
            "customer_phone": "070-3456-7890",
            "order_number": "ORD-2024-0003",
        },
        {
            "id": generate_uuid(),
            "status": ShipmentStatus.SHIPPED.value,
            "tracking_number": "9876-5432-1098",
            "carrier": "sagawa",
            "shipped_at": now - timedelta(days=8),
            "delivered_at": now - timedelta(days=4),
            "customer_name": "鈴木美咲",
            "customer_postal_code": "812-0011",
            "customer_address": "福岡県福岡市博多区博多駅前4-4-4",
            "customer_phone": "090-4567-8901",
            "order_number": "ORD-2024-0004",
        },
        {
            "id": generate_uuid(),
            "status": ShipmentStatus.SHIPPED.value,
            "tracking_number": "5555-6666-7777",
            "carrier": "yamato",
            "shipped_at": now - timedelta(days=1),
            "delivered_at": now + timedelta(days=2),
            "customer_name": "田中太郎",
            "customer_postal_code": "160-0023",
            "customer_address": "東京都新宿区西新宿1-1-1 新宿ビル101",
            "customer_phone": "090-1234-5678",
            "order_number": "ORD-2024-0001",
        },
        {
            "id": generate_uuid(),
            "status": ShipmentStatus.PENDING.value,
            "tracking_number": None,
            "carrier": None,
            "shipped_at": None,
            "delivered_at": None,
            "customer_name": "高橋健太",
            "customer_postal_code": "060-0042",
            "customer_address": "北海道札幌市中央区大通西5-5-5",
            "customer_phone": "080-5678-9012",
            "order_number": "ORD-2024-0005",
        },
    ]

    shipments = {}
    for data in shipments_data:
        order_number = data.pop("order_number")
        shipment = Shipment(**data)
        session.add(shipment)

        # Add shipment item
        item = ShipmentItem(
            id=generate_uuid(),
            shipment_id=data["id"],
            order_id=orders[order_number].id,
        )
        session.add(item)

        shipments[data["id"]] = shipment

    await session.flush()
    print(f"  Created {len(shipments)} shipments")
    return shipments


async def seed_chat_messages(session: AsyncSession, manufacturers: dict[str, Manufacturer]) -> None:
    """Create test chat messages."""
    print("Creating chat messages...")

    now = datetime.now(timezone.utc)

    # Chat with Tシャツプリント
    mfr = manufacturers["Tシャツプリント"]
    messages = [
        {
            "sender_type": MessageSender.ADMIN.value,
            "sender_name": "管理者",
            "content": "年末の発注について確認させてください。Tシャツの在庫状況はいかがでしょうか？",
            "created_at": now - timedelta(days=7, hours=3),
        },
        {
            "sender_type": MessageSender.MANUFACTURER.value,
            "sender_name": "Tシャツプリント",
            "content": "はい、ご連絡ありがとうございます。現在在庫は十分にございます。12/30納品で承っております。",
            "created_at": now - timedelta(days=7, hours=2, minutes=30),
        },
        {
            "sender_type": MessageSender.ADMIN.value,
            "sender_name": "管理者",
            "content": "ありがとうございます。追加で50枚発注したいのですが、可能でしょうか？",
            "created_at": now - timedelta(days=7, hours=2),
        },
        {
            "sender_type": MessageSender.MANUFACTURER.value,
            "sender_name": "Tシャツプリント",
            "content": "追加50枚、承りました。同梱で対応いたします。",
            "created_at": now - timedelta(days=7, hours=1, minutes=30),
        },
        {
            "sender_type": MessageSender.ADMIN.value,
            "sender_name": "管理者",
            "content": "新しいデザインのサンプルについて相談があります。",
            "created_at": now - timedelta(days=5, hours=2),
        },
        {
            "sender_type": MessageSender.MANUFACTURER.value,
            "sender_name": "Tシャツプリント",
            "content": "サンプル作成も可能です。デザインデータをお送りいただければ、確認いたします。",
            "created_at": now - timedelta(days=5, hours=1, minutes=30),
        },
    ]

    for msg_data in messages:
        msg = ChatMessage(
            id=generate_uuid(),
            manufacturer_id=mfr.id,
            **msg_data,
        )
        session.add(msg)

    await session.flush()
    print(f"  Created {len(messages)} chat messages")


async def main(reset: bool = False) -> None:
    """Main seed function."""
    print("=" * 50)
    print("POD Admin - Database Seeder")
    print("=" * 50)

    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            if reset:
                await reset_database(session)

            # Seed data in order
            users = await seed_users(session)
            manufacturers = await seed_manufacturers(session)
            products = await seed_products(session, manufacturers)
            orders = await seed_orders(session, products)
            shipments = await seed_shipments(session, orders)
            await seed_chat_messages(session, manufacturers)

            await session.commit()

            print("=" * 50)
            print("Seed completed successfully!")
            print("=" * 50)
            print("\nTest accounts:")
            print("  Admin:        admin@example.com / admin123")
            print("  Operator:     operator@example.com / operator123")
            print("  Manufacturer: support@tshirt-print.jp / manufacturer123")
            print("")

        except Exception as e:
            await session.rollback()
            print(f"Error during seeding: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed database with test data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database before seeding (delete all existing data)",
    )
    args = parser.parse_args()

    asyncio.run(main(reset=args.reset))
