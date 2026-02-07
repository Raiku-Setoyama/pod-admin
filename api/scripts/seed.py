"""
シードデータスクリプト
最低限のマスタデータをDBに挿入します。

使用方法:
    # シードデータを挿入
    python scripts/seed.py

    # データをリセットして再挿入
    python scripts/seed.py --reset
"""

import asyncio
import sys
import uuid
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker
from app.models.manufacturer import Manufacturer, SharingMethod
from app.models.product import Product, ProductType
from app.models.user import User, UserRole
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
    """Create manufacturers."""
    print("Creating manufacturers...")

    manufacturers_data = [
        {
            "id": generate_uuid(),
            "name": "シードット",
            "email": "support@seedot.jp",
            "phone": "03-1234-5678",
            "supported_products": ["tshirt", "acrylic_keychain", "acrylic_stand", "sticker"],
            "unit_prices": {
                "tshirt": 870,
                "acrylic_keychain": 350,
                "acrylic_stand": 345,
                "sticker": 79,
            },
            "lead_time_days": 10,
            "daily_order_limit": 200,
            "sharing_method": SharingMethod.PORTAL.value,
            "password_hash": hash_password("manufacturer123"),
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "name": "サンプルメーカー1(トートバッグ)",
            "email": "support@tote-manufacturer.jp",
            "phone": "03-9876-5432",
            "supported_products": ["tote_bag"],
            "unit_prices": {"tote_bag": 780},
            "lead_time_days": 10,
            "daily_order_limit": 100,
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
    """Create products."""
    print("Creating products...")

    seedot_id = manufacturers["シードット"].id
    tote_manufacturer_id = manufacturers["サンプルメーカー1(トートバッグ)"].id

    products_data = [
        # Tシャツ (4種類)
        {
            "id": generate_uuid(),
            "product_type": ProductType.TSHIRT.value,
            "size": "S",
            "position": "正面",
            "color": "白",
            "manufacturer_id": seedot_id,
            "cost": 870,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "product_type": ProductType.TSHIRT.value,
            "size": "M",
            "position": "正面",
            "color": "白",
            "manufacturer_id": seedot_id,
            "cost": 870,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "product_type": ProductType.TSHIRT.value,
            "size": "L",
            "position": "正面",
            "color": "白",
            "manufacturer_id": seedot_id,
            "cost": 870,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "product_type": ProductType.TSHIRT.value,
            "size": "XL",
            "position": "正面",
            "color": "白",
            "manufacturer_id": seedot_id,
            "cost": 870,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        # アクリルキーホルダー (3種類)
        {
            "id": generate_uuid(),
            "product_type": ProductType.ACRYLIC_KEYCHAIN.value,
            "size": "50x50mm",
            "position": None,
            "color": "アクリル",
            "manufacturer_id": seedot_id,
            "cost": 285,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "product_type": ProductType.ACRYLIC_KEYCHAIN.value,
            "size": "70x70mm",
            "position": None,
            "color": "アクリル",
            "manufacturer_id": seedot_id,
            "cost": 350,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "product_type": ProductType.ACRYLIC_KEYCHAIN.value,
            "size": "100x100mm",
            "position": None,
            "color": "アクリル",
            "manufacturer_id": seedot_id,
            "cost": 475,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        # アクリルスタンド (3種類)
        {
            "id": generate_uuid(),
            "product_type": ProductType.ACRYLIC_STAND.value,
            "size": "50x50mm",
            "position": None,
            "color": "アクリル",
            "manufacturer_id": seedot_id,
            "cost": 310,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "product_type": ProductType.ACRYLIC_STAND.value,
            "size": "70x70mm",
            "position": None,
            "color": "アクリル",
            "manufacturer_id": seedot_id,
            "cost": 345,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "product_type": ProductType.ACRYLIC_STAND.value,
            "size": "100x100mm",
            "position": None,
            "color": "アクリル",
            "manufacturer_id": seedot_id,
            "cost": 735,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        # ステッカー (2種類)
        {
            "id": generate_uuid(),
            "product_type": ProductType.STICKER.value,
            "size": "100x100mm",
            "position": None,
            "color": "クリア",
            "manufacturer_id": seedot_id,
            "cost": 105,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "product_type": ProductType.STICKER.value,
            "size": "100x100mm",
            "position": None,
            "color": "ホワイト",
            "manufacturer_id": seedot_id,
            "cost": 79,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
        # トートバッグ (1種類)
        {
            "id": generate_uuid(),
            "product_type": ProductType.TOTE_BAG.value,
            "size": "M",
            "position": "正面",
            "color": "ナチュラル",
            "manufacturer_id": tote_manufacturer_id,
            "cost": 780,
            "lead_time_days": 10,
            "order_limit": None,
            "is_active": True,
        },
    ]

    products = {}
    for data in products_data:
        product = Product(**data)
        session.add(product)
        # Use product_type/size/color combination as key to avoid duplicates
        products[f"{data['product_type']}_{data['size']}_{data.get('color', '')}"] = product

    await session.flush()
    print(f"  Created {len(products)} products")
    return products


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

            # Seed data in order (master data only)
            await seed_users(session)
            manufacturers = await seed_manufacturers(session)
            await seed_products(session, manufacturers)

            await session.commit()

            print("=" * 50)
            print("Seed completed successfully!")
            print("=" * 50)
            print("\nTest accounts:")
            print("  Admin:        admin@example.com / admin123")
            print("  Operator:     operator@example.com / operator123")
            print("  Manufacturer: support@seedot.jp / manufacturer123")
            print("")

        except Exception as e:
            await session.rollback()
            print(f"Error during seeding: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed database with master data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database before seeding (delete all existing data)",
    )
    args = parser.parse_args()

    asyncio.run(main(reset=args.reset))
