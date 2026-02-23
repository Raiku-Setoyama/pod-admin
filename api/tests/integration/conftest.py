"""統合テスト用のフィクスチャ

実際のDBを使用するテスト用の設定。
Docker環境で実行することを前提としています。
"""

import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from uuid import uuid4

from app.main import app
from app.config import settings
from app.utils.security import create_access_token
from app.models.user import UserRole
from app import database


@pytest.fixture(autouse=True)
async def reset_db_cache():
    """各テスト前にDBエンジンのキャッシュをクリア

    lru_cacheでキャッシュされたエンジンが異なるイベントループに
    紐づいている問題を回避するため、各テスト前にキャッシュをクリアします。
    """
    # キャッシュをクリアしてエンジンを閉じる
    if database.get_engine.cache_info().hits > 0 or database.get_engine.cache_info().misses > 0:
        try:
            engine = database.get_engine()
            await engine.dispose()
        except Exception:
            pass
    database.get_engine.cache_clear()
    database.get_session_maker.cache_clear()
    yield
    # テスト後もクリーンアップ
    try:
        engine = database.get_engine()
        await engine.dispose()
    except Exception:
        pass
    database.get_engine.cache_clear()
    database.get_session_maker.cache_clear()


@pytest.fixture
async def client():
    """非同期HTTPクライアント"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def db_session():
    """データベースセッション

    各テスト関数ごとに新しいセッションとエンジンを作成します。
    """
    engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_maker() as session:
        yield session
        # セッション終了前にコミット
        try:
            await session.commit()
        except Exception:
            await session.rollback()

    # エンジンを明示的にクローズ
    await engine.dispose()


@pytest.fixture
async def test_admin_user(db_session: AsyncSession):
    """テスト用管理者ユーザー"""
    from app.utils.security import hash_password

    # 有効なUUID形式で生成
    user_id = "00000000-0000-0000-0000-000000000001"

    try:
        # 既存のユーザーを確認
        result = await db_session.execute(
            text("SELECT id FROM users WHERE id = :id"),
            {"id": user_id}
        )
        existing = result.fetchone()

        if not existing:
            await db_session.execute(
                text("""
                    INSERT INTO users (id, email, name, password_hash, role, is_active, created_at, updated_at)
                    VALUES (:id, :email, :name, :password_hash, :role, :is_active, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": user_id,
                    "email": "test-admin@example.com",
                    "name": "Test Admin",
                    "password_hash": hash_password("password"),
                    "role": "admin",
                    "is_active": True,
                }
            )
            await db_session.commit()

        yield {"id": user_id, "email": "test-admin@example.com"}

    finally:
        # クリーンアップは別セッションで行う（接続が切れている可能性があるため）
        pass


@pytest.fixture
def auth_headers(test_admin_user: dict):
    """認証済みリクエスト用のヘッダー

    管理者権限を持つテストユーザー用のトークンを生成します。
    """
    # テスト用の管理者トークンを生成
    token = create_access_token({"sub": test_admin_user["id"], "role": UserRole.ADMIN.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_order_source(db_session: AsyncSession):
    """テスト用の注文ソース"""
    source_id = str(uuid4())
    source_code = f"TEST{source_id[:8].upper()}"

    await db_session.execute(
        text("""
            INSERT INTO order_sources (id, code, name, api_key, phone, postal_code, address_prefecture, address_city, is_active, created_at, updated_at)
            VALUES (:id, :code, :name, :api_key, :phone, :postal_code, :address_prefecture, :address_city, :is_active, NOW(), NOW())
        """),
        {
            "id": source_id,
            "code": source_code,
            "name": "Test Source",
            "api_key": f"test-api-key-{source_id}",
            "phone": "090-1234-5678",
            "postal_code": "100-0001",
            "address_prefecture": "東京都",
            "address_city": "千代田区",
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {"id": source_id}

    # クリーンアップはしない（次のテストで新しいIDが使われるため問題ない）


@pytest.fixture
async def test_order(db_session: AsyncSession, test_order_source: dict):
    """テスト用の注文"""
    order_id = str(uuid4())

    await db_session.execute(
        text("""
            INSERT INTO orders (id, order_number, order_source_id, product_name, quantity, customer_name, customer_email, customer_phone, customer_postal_code, customer_address_prefecture, customer_address_city, status, ordered_at, created_at, updated_at)
            VALUES (:id, :order_number, :order_source_id, :product_name, :quantity, :customer_name, :customer_email, :customer_phone, :customer_postal_code, :customer_address_prefecture, :customer_address_city, :status, NOW(), NOW(), NOW())
        """),
        {
            "id": order_id,
            "order_number": f"TEST-{order_id[:8]}",
            "order_source_id": test_order_source["id"],
            "product_name": "Test Product",
            "quantity": 1,
            "customer_name": "Test Customer",
            "customer_email": "customer@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区1-1-1",
            "status": "delivered",
        }
    )
    await db_session.commit()

    yield {"id": order_id, "order_source_id": test_order_source["id"]}

    # クリーンアップはしない（次のテストで新しいIDが使われるため問題ない）


@pytest.fixture
async def shipment_with_photo(db_session: AsyncSession, test_admin_user: dict, test_order: dict):
    """梱包写真がアップロード済みの配送データ"""
    shipment_id = str(uuid4())
    photo_path = f"shipments/{shipment_id}/photo.jpg"

    # テスト用の画像ファイルを作成
    upload_dir = settings.UPLOAD_DIR
    photo_dir = os.path.join(upload_dir, "shipments", shipment_id)
    os.makedirs(photo_dir, exist_ok=True)

    photo_file_path = os.path.join(photo_dir, "photo.jpg")
    # 最小限の有効なJPEGファイルを作成
    # JPEG magic bytes + minimal valid JPEG structure
    jpeg_data = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xFF, 0xD9
    ])
    with open(photo_file_path, "wb") as f:
        f.write(jpeg_data)

    # DBに配送データを作成
    await db_session.execute(
        text("""
            INSERT INTO shipments (id, status, packing_photo_path, created_at, updated_at)
            VALUES (:id, :status, :packing_photo_path, NOW(), NOW())
        """),
        {
            "id": shipment_id,
            "status": "pending",
            "packing_photo_path": photo_path,
        }
    )

    # ShipmentItem を作成
    item_id = str(uuid4())
    await db_session.execute(
        text("""
            INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
            VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
        """),
        {
            "id": item_id,
            "shipment_id": shipment_id,
            "order_id": test_order["id"],
        }
    )
    await db_session.commit()

    yield {"id": shipment_id, "packing_photo_path": photo_path}

    # クリーンアップはしない（次のテストで新しいIDが使われるため問題ない）
    # ファイルはテスト環境でのみ存在するため、削除不要


@pytest.fixture
async def shipment_without_photo(db_session: AsyncSession, test_admin_user: dict):
    """梱包写真がない配送データ

    他のフィクスチャ（test_order_source）に依存せず、自己完結したデータを作成します。
    """
    shipment_id = str(uuid4())
    order_source_id = str(uuid4())
    source_code = f"SRC{order_source_id[:8].upper()}"

    # 自己完結した注文ソースを作成
    await db_session.execute(
        text("""
            INSERT INTO order_sources (id, code, name, api_key, phone, postal_code, address_prefecture, address_city, is_active, created_at, updated_at)
            VALUES (:id, :code, :name, :api_key, :phone, :postal_code, :address_prefecture, :address_city, :is_active, NOW(), NOW())
        """),
        {
            "id": order_source_id,
            "code": source_code,
            "name": "Test Source for No Photo",
            "api_key": f"test-api-key-nophoto-{order_source_id}",
            "phone": "090-1234-5679",
            "postal_code": "100-0003",
            "address_prefecture": "東京都",
            "address_city": "千代田区",
            "is_active": True,
        }
    )

    # DBに配送データを作成（packing_photo_path = NULL）
    await db_session.execute(
        text("""
            INSERT INTO shipments (id, status, packing_photo_path, created_at, updated_at)
            VALUES (:id, :status, :packing_photo_path, NOW(), NOW())
        """),
        {
            "id": shipment_id,
            "status": "pending",
            "packing_photo_path": None,
        }
    )

    # 自己完結した注文を作成
    order_id = str(uuid4())
    await db_session.execute(
        text("""
            INSERT INTO orders (id, order_number, order_source_id, product_name, quantity, customer_name, customer_email, customer_phone, customer_postal_code, customer_address_prefecture, customer_address_city, status, ordered_at, created_at, updated_at)
            VALUES (:id, :order_number, :order_source_id, :product_name, :quantity, :customer_name, :customer_email, :customer_phone, :customer_postal_code, :customer_address_prefecture, :customer_address_city, :status, NOW(), NOW(), NOW())
        """),
        {
            "id": order_id,
            "order_number": f"TEST2-{order_id[:8]}",
            "order_source_id": order_source_id,
            "product_name": "Test Product 2",
            "quantity": 1,
            "customer_name": "Test Customer 2",
            "customer_email": "customer2@example.com",
            "customer_phone": "090-0000-0001",
            "customer_postal_code": "100-0002",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区2-2-2",
            "status": "delivered",
        }
    )

    # ShipmentItem を作成
    item_id = str(uuid4())
    await db_session.execute(
        text("""
            INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
            VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
        """),
        {
            "id": item_id,
            "shipment_id": shipment_id,
            "order_id": order_id,
        }
    )
    await db_session.commit()

    yield {"id": shipment_id, "packing_photo_path": None}

    # クリーンアップはしない（次のテストで新しいIDが使われるため問題ない）
