"""
動作確認用テストデータシードスクリプト

機能要件一覧（管理者・製造業者）の動作確認に必要なテストデータを投入します。
DBを完全リセットして一からテストデータを投入します。

使用方法:
    docker compose exec api uv run python scripts/seed_operation_test.py
"""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker
from app.models.chat_message import ChatAttachment, ChatMessage, MessageSender
from app.models.manufacturer import Manufacturer, SharingMethod
from app.models.order import Order, OrderItem, OrderStatus
from app.models.order_source import OrderSource
from app.models.product import Product, ProductType
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.models.user import User, UserRole
from app.utils.security import hash_password


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


# =============================================================================
# テスト用サンプル画像URL（Supabase Storage）
# =============================================================================
SAMPLE_DESIGN_IMAGE_URL = "https://jmgzsiogrviyrppxtaqs.supabase.co/storage/v1/object/public/submission-data/sample.ai"
SAMPLE_THUMBNAIL_IMAGE_URL = "https://jmgzsiogrviyrppxtaqs.supabase.co/storage/v1/object/public/submission-data/sample.png"


# =============================================================================
# 顧客データ（5パターン）
# =============================================================================
CUSTOMERS: list[dict[str, Any]] = [
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
        "postal_code": "330-0063",
        "address_prefecture": "埼玉県",
        "address_city": "さいたま市浦和区常盤5-6-7",
        "address_building": None,
        "phone": "080-5678-9012",
        "email": "takahashi@example.com",
    },
]

# =============================================================================
# 商品名パターン
# =============================================================================
PRODUCT_NAMES: dict[str, list[str]] = {
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


async def reset_database(session: AsyncSession) -> None:
    """Delete all data from tables (in correct order to handle foreign keys)."""
    print("データベースをリセット中...")

    tables_to_clear = [
        "chat_attachments",
        "chat_messages",
        "shipment_items",
        "shipments",
        "order_items",
        "orders",
        "products",
        "manufacturers",
        "order_sources",
        "users",
    ]

    for table in tables_to_clear:
        await session.execute(text(f"DELETE FROM {table}"))

    await session.commit()
    print("  データベースリセット完了")


# =============================================================================
# マスタデータ作成
# =============================================================================


async def seed_users(session: AsyncSession) -> dict[str, User]:
    """管理者アカウントを作成."""
    print("ユーザーを作成中...")

    users_data: list[dict[str, Any]] = [
        {
            "id": generate_uuid(),
            "email": "admin@example.com",
            "password_hash": hash_password("admin123"),
            "name": "管理者",
            "role": UserRole.ADMIN,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "email": "operator@example.com",
            "password_hash": hash_password("operator123"),
            "name": "オペレーター",
            "role": UserRole.OPERATOR,
            "is_active": True,
        },
    ]

    users = {}
    for data in users_data:
        user = User(**data)
        session.add(user)
        users[data["email"]] = user

    await session.flush()
    print(f"  {len(users)} 件のユーザーを作成")
    return users


async def seed_manufacturers(session: AsyncSession) -> dict[str, Manufacturer]:
    """メーカーを作成."""
    print("メーカーを作成中...")

    manufacturers_data: list[dict[str, Any]] = [
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
            # Invoice fields
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
            "id": generate_uuid(),
            "name": "サンプルメーカー1",
            "email": "support@tote.jp",
            "phone": "03-9876-5432",
            "supported_products": ["tote_bag"],
            "unit_prices": {"tote_bag": 780},
            "lead_time_days": 10,
            "daily_order_limit": 100,
            "sharing_method": SharingMethod.PORTAL.value,
            "password_hash": hash_password("manufacturer123"),
            "is_active": True,
            # Invoice fields
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

    manufacturers = {}
    for data in manufacturers_data:
        mfr = Manufacturer(**data)
        session.add(mfr)
        manufacturers[data["name"]] = mfr

    await session.flush()
    print(f"  {len(manufacturers)} 件のメーカーを作成")
    return manufacturers


async def seed_products(
    session: AsyncSession, manufacturers: dict[str, Manufacturer]
) -> dict[str, Product]:
    """商品マスタを作成."""
    print("商品を作成中...")

    seedot_id = manufacturers["シードット"].id
    sample1_id = manufacturers["サンプルメーカー1"].id

    products_data: list[dict[str, Any]] = [
        # シードット - Tシャツ (4サイズ)
        {"product_type": ProductType.TSHIRT.value, "size": "S", "position": "正面", "color": "白", "manufacturer_id": seedot_id, "cost": 870, "lead_time_days": 10},
        {"product_type": ProductType.TSHIRT.value, "size": "M", "position": "正面", "color": "白", "manufacturer_id": seedot_id, "cost": 870, "lead_time_days": 10},
        {"product_type": ProductType.TSHIRT.value, "size": "L", "position": "正面", "color": "白", "manufacturer_id": seedot_id, "cost": 870, "lead_time_days": 10},
        {"product_type": ProductType.TSHIRT.value, "size": "XL", "position": "正面", "color": "白", "manufacturer_id": seedot_id, "cost": 870, "lead_time_days": 10},
        # シードット - アクリルキーホルダー (3サイズ)
        {"product_type": ProductType.ACRYLIC_KEYCHAIN.value, "size": "50x50mm", "position": None, "color": "アクリル", "manufacturer_id": seedot_id, "cost": 285, "lead_time_days": 10},
        {"product_type": ProductType.ACRYLIC_KEYCHAIN.value, "size": "70x70mm", "position": None, "color": "アクリル", "manufacturer_id": seedot_id, "cost": 350, "lead_time_days": 10},
        {"product_type": ProductType.ACRYLIC_KEYCHAIN.value, "size": "100x100mm", "position": None, "color": "アクリル", "manufacturer_id": seedot_id, "cost": 475, "lead_time_days": 10},
        # シードット - アクリルスタンド (3サイズ)
        {"product_type": ProductType.ACRYLIC_STAND.value, "size": "50x50mm", "position": None, "color": "アクリル", "manufacturer_id": seedot_id, "cost": 310, "lead_time_days": 10},
        {"product_type": ProductType.ACRYLIC_STAND.value, "size": "70x70mm", "position": None, "color": "アクリル", "manufacturer_id": seedot_id, "cost": 345, "lead_time_days": 10},
        {"product_type": ProductType.ACRYLIC_STAND.value, "size": "100x100mm", "position": None, "color": "アクリル", "manufacturer_id": seedot_id, "cost": 735, "lead_time_days": 10},
        # シードット - ステッカー (3サイズ)
        {"product_type": ProductType.STICKER.value, "size": "50x50mm", "position": None, "color": "ホワイト", "manufacturer_id": seedot_id, "cost": 50, "lead_time_days": 10},
        {"product_type": ProductType.STICKER.value, "size": "70x70mm", "position": None, "color": "ホワイト", "manufacturer_id": seedot_id, "cost": 59, "lead_time_days": 10},
        {"product_type": ProductType.STICKER.value, "size": "100x100mm", "position": None, "color": "ホワイト", "manufacturer_id": seedot_id, "cost": 79, "lead_time_days": 10},
        # サンプルメーカー1 - トートバッグ
        {"product_type": ProductType.TOTE_BAG.value, "size": "M", "position": None, "color": "ナチュラル", "manufacturer_id": sample1_id, "cost": 780, "lead_time_days": 10},
    ]

    products = {}
    for data in products_data:
        product = Product(
            id=generate_uuid(),
            is_active=True,
            order_limit=None,
            **data,
        )
        session.add(product)
        key = f"{data['manufacturer_id']}_{data['product_type']}_{data['size']}"
        products[key] = product

    await session.flush()
    print(f"  {len(products)} 件の商品を作成")
    return products


async def seed_order_sources(session: AsyncSession) -> dict[str, OrderSource]:
    """受注元を作成."""
    print("受注元を作成中...")

    order_sources_data: list[dict[str, Any]] = [
        {
            "id": generate_uuid(),
            "code": "TEST",
            "api_key": "test-api-key-001",
            "name": "テスト配送元",
            "phone": "03-0000-0000",
            "postal_code": "000-0000",
            "address_prefecture": "東京都",
            "address_city": "テスト市1-1-1",
            "address_building": None,
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "code": "SHOP_A",
            "api_key": "shop-a-api-key-002",
            "name": "ECショップA",
            "phone": "03-1111-2222",
            "postal_code": "150-0001",
            "address_prefecture": "東京都",
            "address_city": "渋谷区渋谷1-1-1",
            "address_building": "ショップAビル1F",
            "is_active": True,
        },
        {
            "id": generate_uuid(),
            "code": "SHOP_B",
            "api_key": "shop-b-api-key-003",
            "name": "ECショップB",
            "phone": "03-3333-4444",
            "postal_code": "160-0022",
            "address_prefecture": "東京都",
            "address_city": "新宿区新宿2-2-2",
            "address_building": None,
            "is_active": True,
        },
    ]

    order_sources = {}
    for data in order_sources_data:
        order_source = OrderSource(**data)
        session.add(order_source)
        order_sources[data["code"]] = order_source

    await session.flush()
    print(f"  {len(order_sources)} 件の受注元を作成")
    return order_sources


# =============================================================================
# トランザクションデータ作成
# =============================================================================


def get_products_for_manufacturer(
    products: dict[str, Product], manufacturer_id: str
) -> list[Product]:
    """指定メーカーの商品リストを取得."""
    return [p for p in products.values() if p.manufacturer_id == manufacturer_id]


async def seed_orders(
    session: AsyncSession,
    products: dict[str, Product],
    order_sources: dict[str, OrderSource],
    manufacturers: dict[str, Manufacturer],
) -> dict[str, Order]:
    """受注データを作成.

    - ordered: 10件
    - manufacturing: 8件
    - delivered: 6件
    - shipped: 5件
    合計: 29件
    """
    print("受注データを作成中...")

    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)

    # ステータス別件数
    status_counts = [
        (OrderStatus.ORDERED.value, 10),
        (OrderStatus.MANUFACTURING.value, 8),
        (OrderStatus.DELIVERED.value, 6),
        (OrderStatus.SHIPPED.value, 5),
    ]

    order_sources_list = list(order_sources.values())
    manufacturer_list = list(manufacturers.values())

    orders = {}
    order_index = 1

    for status, count in status_counts:
        for _ in range(count):
            customer = random.choice(CUSTOMERS)
            order_source = random.choice(order_sources_list)

            # ランダムなメーカーを選択
            manufacturer = random.choice(manufacturer_list)
            mfr_products = get_products_for_manufacturer(products, manufacturer.id)

            if not mfr_products:
                continue

            # 受注日（過去30日以内）
            days_ago = random.randint(0, 30)
            ordered_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))

            order_id = generate_uuid()
            order_number = f"{order_index:07d}"

            order = Order(
                id=order_id,
                order_number=order_number,
                status=status,
                order_source_id=order_source.id,
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

            # 1-3件の明細を作成
            num_items = random.randint(1, 3)
            total_price = 0

            for j in range(num_items):
                product = random.choice(mfr_products)
                quantity = random.randint(1, 5)
                price = random.randint(1500, 5000)

                product_name_list = PRODUCT_NAMES.get(product.product_type, ["商品"])
                product_name = random.choice(product_name_list)

                order_item = OrderItem(
                    id=generate_uuid(),
                    order_id=order_id,
                    uid=f"{order_index * 10 + (j + 1):07d}",
                    product_id=product.id,
                    product_name=product_name,
                    product_type=product.product_type,
                    price=price,
                    quantity=quantity,
                    size=product.size,
                    position=product.position,
                    color=product.color,
                    design_image_url=SAMPLE_DESIGN_IMAGE_URL,
                    thumbnail_image_url=SAMPLE_THUMBNAIL_IMAGE_URL,
                )
                session.add(order_item)
                total_price += price * quantity

            order.total_price = total_price
            orders[order_id] = order
            order_index += 1

    await session.flush()
    print(f"  {len(orders)} 件の受注（各1-3件の明細を含む）を作成")
    return orders


async def seed_shipments(
    session: AsyncSession,
    orders: dict[str, Order],
) -> dict[str, Shipment]:
    """配送データを作成.

    - pending: 3件
    - ready: 2件（追跡番号あり）
    - shipped: 2件
    """
    print("配送データを作成中...")

    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)

    # delivered/shipped ステータスの受注を取得
    eligible_orders = [
        o for o in orders.values()
        if o.status in [OrderStatus.DELIVERED.value, OrderStatus.SHIPPED.value]
    ]

    shipments = {}
    shipment_configs = [
        (ShipmentStatus.PENDING.value, 3, False),
        (ShipmentStatus.READY.value, 2, True),
        (ShipmentStatus.SHIPPED.value, 2, True),
    ]

    order_idx = 0
    shipment_idx = 1

    for status, count, has_tracking in shipment_configs:
        for i in range(count):
            if order_idx >= len(eligible_orders):
                break

            order = eligible_orders[order_idx]
            order_idx += 1

            shipment_id = generate_uuid()

            shipment = Shipment(
                id=shipment_id,
                status=status,
                tracking_number=f"TRACK-{shipment_idx:06d}" if has_tracking else None,
                carrier="ヤマト運輸" if has_tracking else None,
                shipped_at=(now - timedelta(days=random.randint(1, 5))) if status == ShipmentStatus.SHIPPED.value else None,
                note=f"配送メモ {shipment_idx}" if i == 0 else None,
            )
            session.add(shipment)

            # ShipmentItem を作成
            shipment_item = ShipmentItem(
                id=generate_uuid(),
                shipment_id=shipment_id,
                order_id=order.id,
            )
            session.add(shipment_item)

            shipments[shipment_id] = shipment
            shipment_idx += 1

    await session.flush()
    print(f"  {len(shipments)} 件の配送を作成")
    return shipments


async def seed_chat_messages(
    session: AsyncSession,
    manufacturers: dict[str, Manufacturer],
) -> dict[str, ChatMessage]:
    """チャットメッセージを作成.

    各メーカーに対して:
    - 管理者→メーカー: 3件
    - メーカー→管理者: 2件
    - 添付ファイル付きメッセージ: 1件
    """
    print("チャットメッセージを作成中...")

    admin_messages = [
        "お世話になっております。今月分の発注についてご確認いただけますでしょうか。",
        "納品予定日を教えていただけますか？",
        "先日の発注分について、進捗状況をお知らせください。",
    ]

    manufacturer_messages = [
        "ご連絡ありがとうございます。確認いたしました。",
        "納品は予定通り進んでおります。ご安心ください。",
    ]

    messages = {}

    for mfr_name, manufacturer in manufacturers.items():
        # 管理者からのメッセージ
        for content in admin_messages:
            msg_id = generate_uuid()

            message = ChatMessage(
                id=msg_id,
                manufacturer_id=manufacturer.id,
                sender_type=MessageSender.ADMIN.value,
                sender_name="管理者",
                content=content,
            )
            # created_at は DB のデフォルト（登録時刻）に任せる
            session.add(message)
            messages[msg_id] = message

        # メーカーからのメッセージ
        for i, content in enumerate(manufacturer_messages):
            msg_id = generate_uuid()

            message = ChatMessage(
                id=msg_id,
                manufacturer_id=manufacturer.id,
                sender_type=MessageSender.MANUFACTURER.value,
                sender_name=mfr_name,
                content=content,
            )
            session.add(message)
            messages[msg_id] = message

            # 最初のメーカーの最初のメッセージに添付ファイルを追加
            if mfr_name == "シードット" and i == 0:
                attachment = ChatAttachment(
                    id=generate_uuid(),
                    message_id=msg_id,
                    filename="納品書_2024年1月.pdf",
                    file_path="/uploads/chat/納品書_2024年1月.pdf",
                    file_size=102400,
                    content_type="application/pdf",
                )
                session.add(attachment)

    await session.flush()
    print(f"  {len(messages)} 件のチャットメッセージを作成")
    return messages


# =============================================================================
# メイン処理
# =============================================================================


async def main() -> None:
    """メイン処理."""
    print("=" * 60)
    print("POD Admin - 動作確認用テストデータシード")
    print("=" * 60)

    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            # DBリセット
            await reset_database(session)

            # マスタデータ作成
            print("\n--- マスタデータ作成 ---")
            await seed_users(session)
            manufacturers = await seed_manufacturers(session)
            products = await seed_products(session, manufacturers)
            order_sources = await seed_order_sources(session)

            # トランザクションデータ作成
            print("\n--- トランザクションデータ作成 ---")
            orders = await seed_orders(session, products, order_sources, manufacturers)
            await seed_shipments(session, orders)
            await seed_chat_messages(session, manufacturers)

            await session.commit()

            print("\n" + "=" * 60)
            print("テストデータの作成が完了しました！")
            print("=" * 60)
            print("\n【テストアカウント】")
            print("  管理者:")
            print("    - admin@example.com / admin123")
            print("    - operator@example.com / operator123")
            print("  メーカー:")
            print("    - support@seedot.jp / manufacturer123")
            print("    - support@tote.jp / manufacturer123")
            print("\n【確認方法】")
            print("  管理者ログイン: /admin/login")
            print("  メーカーログイン: /manufacturer/login")
            print("")

        except Exception as e:
            await session.rollback()
            print(f"\nエラーが発生しました: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
