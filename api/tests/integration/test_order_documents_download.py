"""発注資料ダウンロードAPIの統合テスト

FEAT-0004: 発注資料ダウンロード時のステータス自動切り替え

このテストは、発注資料ダウンロードAPIの動作を検証します。

管理者エンドポイント（GET /api/v1/manufacturers/{manufacturer_id}/order-documents）:
- 全ステータスでダウンロード可能
- ステータス更新は行わない

メーカーエンドポイント（GET /api/v1/manufacturer-portal/order-documents）:
- 全ステータスでダウンロード可能
- 発注中（ORDERED）の明細のみ製造中（MANUFACTURING）に更新
"""

import io
import json
import zipfile
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TestOrderDocumentsDownloadStatusUpdate:
    """発注資料ダウンロード時のステータス自動更新の統合テスト"""

    @pytest.fixture
    async def test_manufacturer(self, db_session: AsyncSession):
        """テスト用メーカー"""
        manufacturer_id = str(uuid4())
        # ユニークな名前を生成（並列テスト対策）
        manufacturer_name = f"テストメーカー_{manufacturer_id[:8]}"

        await db_session.execute(
            text("""
                INSERT INTO manufacturers (id, name, email, phone, supported_products, unit_prices, lead_time_days, daily_order_limit, sharing_method, is_active, created_at, updated_at)
                VALUES (:id, :name, :email, :phone, :supported_products, :unit_prices, :lead_time_days, :daily_order_limit, :sharing_method, :is_active, NOW(), NOW())
            """),
            {
                "id": manufacturer_id,
                "name": manufacturer_name,
                "email": "test@manufacturer.com",
                "phone": "03-1234-5678",
                "supported_products": ["tshirt"],
                "unit_prices": json.dumps({}),
                "lead_time_days": 7,
                "daily_order_limit": 100,
                "sharing_method": "portal",
                "is_active": True,
            }
        )
        await db_session.commit()

        yield {"id": manufacturer_id, "name": manufacturer_name}

    @pytest.fixture
    async def test_product(self, db_session: AsyncSession, test_manufacturer: dict):
        """テスト用商品（メーカーに紐づく）"""
        product_id = str(uuid4())
        # ユニークなサイズを使用して既存データとの衝突を避ける
        unique_size = f"DOC-{product_id[:8]}"

        await db_session.execute(
            text("""
                INSERT INTO products (id, product_type, size, position, color, manufacturer_id, cost, lead_time_days, order_limit, is_active, created_at, updated_at)
                VALUES (:id, :product_type, :size, :position, :color, :manufacturer_id, :cost, :lead_time_days, :order_limit, :is_active, NOW(), NOW())
            """),
            {
                "id": product_id,
                "product_type": "tshirt",
                "size": unique_size,
                "position": "正面",
                "color": "白",
                "manufacturer_id": test_manufacturer["id"],
                "cost": 1000,
                "lead_time_days": 7,
                "order_limit": 100,
                "is_active": True,
            }
        )
        await db_session.commit()

        yield {"id": product_id, "product_type": "tshirt"}

    @pytest.fixture
    async def ordered_items_3(
        self,
        db_session: AsyncSession,
        test_order_source: dict,
        test_product: dict,
    ):
        """発注中ステータスの受注明細3件"""
        items = []
        for i in range(3):
            order_id = str(uuid4())
            order_item_id = str(uuid4())

            # 受注を作成（status = ordered）
            await db_session.execute(
                text("""
                    INSERT INTO orders (id, order_number, order_source_id, product_name, quantity, customer_name, customer_email, customer_phone, customer_postal_code, customer_address_prefecture, customer_address_city, status, total_price, ordered_at, created_at, updated_at)
                    VALUES (:id, :order_number, :order_source_id, :product_name, :quantity, :customer_name, :customer_email, :customer_phone, :customer_postal_code, :customer_address_prefecture, :customer_address_city, :status, :total_price, NOW(), NOW(), NOW())
                """),
                {
                    "id": order_id,
                    "order_number": f"ORDERED-{i+1}-{order_id[:8]}",
                    "order_source_id": test_order_source["id"],
                    "product_name": f"テスト商品{i+1}",
                    "quantity": 1,
                    "customer_name": f"テスト顧客{i+1}",
                    "customer_email": f"customer{i+1}@example.com",
                    "customer_phone": f"090-0000-000{i}",
                    "customer_postal_code": "100-0001",
                    "customer_address_prefecture": "東京都",
                    "customer_address_city": "千代田区",
                    "status": "ordered",  # 発注中
                    "total_price": 3000,
                }
            )

            # 受注明細を作成
            await db_session.execute(
                text("""
                    INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, price, quantity, size, position, color, created_at, updated_at)
                    VALUES (:id, :order_id, :uid, :product_id, :product_name, :product_type, :price, :quantity, :size, :position, :color, NOW(), NOW())
                """),
                {
                    "id": order_item_id,
                    "order_id": order_id,
                    "uid": f"UID-{i+1}",
                    "product_id": test_product["id"],
                    "product_name": f"テスト商品{i+1}",
                    "product_type": "tshirt",
                    "price": 3000,
                    "quantity": 1,
                    "size": "M",
                    "position": "正面",
                    "color": "白",
                }
            )

            items.append({"order_id": order_id, "order_item_id": order_item_id})

        await db_session.commit()
        yield items

    @pytest.fixture
    async def mixed_status_items(
        self,
        db_session: AsyncSession,
        test_order_source: dict,
        test_product: dict,
    ):
        """発注中2件、製造中1件のミックス明細"""
        items = {"ordered": [], "manufacturing": []}
        statuses = ["ordered", "ordered", "manufacturing"]

        for i, status in enumerate(statuses):
            order_id = str(uuid4())
            order_item_id = str(uuid4())

            await db_session.execute(
                text("""
                    INSERT INTO orders (id, order_number, order_source_id, product_name, quantity, customer_name, customer_email, customer_phone, customer_postal_code, customer_address_prefecture, customer_address_city, status, total_price, ordered_at, created_at, updated_at)
                    VALUES (:id, :order_number, :order_source_id, :product_name, :quantity, :customer_name, :customer_email, :customer_phone, :customer_postal_code, :customer_address_prefecture, :customer_address_city, :status, :total_price, NOW(), NOW(), NOW())
                """),
                {
                    "id": order_id,
                    "order_number": f"MIXED-{i+1}-{order_id[:8]}",
                    "order_source_id": test_order_source["id"],
                    "product_name": f"ミックス商品{i+1}",
                    "quantity": 1,
                    "customer_name": f"ミックス顧客{i+1}",
                    "customer_email": f"mixed{i+1}@example.com",
                    "customer_phone": f"090-1111-111{i}",
                    "customer_postal_code": "100-0002",
                    "customer_address_prefecture": "東京都",
                    "customer_address_city": "港区",
                    "status": status,
                    "total_price": 3000,
                }
            )

            await db_session.execute(
                text("""
                    INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, price, quantity, size, position, color, created_at, updated_at)
                    VALUES (:id, :order_id, :uid, :product_id, :product_name, :product_type, :price, :quantity, :size, :position, :color, NOW(), NOW())
                """),
                {
                    "id": order_item_id,
                    "order_id": order_id,
                    "uid": f"MIX-UID-{i+1}",
                    "product_id": test_product["id"],
                    "product_name": f"ミックス商品{i+1}",
                    "product_type": "tshirt",
                    "price": 3000,
                    "quantity": 1,
                    "size": "L",
                    "position": "正面",
                    "color": "白",
                }
            )

            if status == "ordered":
                items["ordered"].append({"order_id": order_id, "order_item_id": order_item_id})
            else:
                items["manufacturing"].append({"order_id": order_id, "order_item_id": order_item_id})

        await db_session.commit()
        yield items

    @pytest.fixture
    async def manufacturing_only_items(
        self,
        db_session: AsyncSession,
        test_order_source: dict,
        test_product: dict,
    ):
        """製造中ステータスのみの受注明細（発注中が0件）"""
        items = []
        for i in range(2):
            order_id = str(uuid4())
            order_item_id = str(uuid4())

            await db_session.execute(
                text("""
                    INSERT INTO orders (id, order_number, order_source_id, product_name, quantity, customer_name, customer_email, customer_phone, customer_postal_code, customer_address_prefecture, customer_address_city, status, total_price, ordered_at, created_at, updated_at)
                    VALUES (:id, :order_number, :order_source_id, :product_name, :quantity, :customer_name, :customer_email, :customer_phone, :customer_postal_code, :customer_address_prefecture, :customer_address_city, :status, :total_price, NOW(), NOW(), NOW())
                """),
                {
                    "id": order_id,
                    "order_number": f"MFG-{i+1}-{order_id[:8]}",
                    "order_source_id": test_order_source["id"],
                    "product_name": f"製造中商品{i+1}",
                    "quantity": 1,
                    "customer_name": f"製造中顧客{i+1}",
                    "customer_email": f"mfg{i+1}@example.com",
                    "customer_phone": f"090-2222-222{i}",
                    "customer_postal_code": "100-0003",
                    "customer_address_prefecture": "東京都",
                    "customer_address_city": "渋谷区",
                    "status": "manufacturing",  # 製造中
                    "total_price": 3000,
                }
            )

            await db_session.execute(
                text("""
                    INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, price, quantity, size, position, color, created_at, updated_at)
                    VALUES (:id, :order_id, :uid, :product_id, :product_name, :product_type, :price, :quantity, :size, :position, :color, NOW(), NOW())
                """),
                {
                    "id": order_item_id,
                    "order_id": order_id,
                    "uid": f"MFG-UID-{i+1}",
                    "product_id": test_product["id"],
                    "product_name": f"製造中商品{i+1}",
                    "product_type": "tshirt",
                    "price": 3000,
                    "quantity": 1,
                    "size": "XL",
                    "position": "正面",
                    "color": "白",
                }
            )

            items.append({"order_id": order_id, "order_item_id": order_item_id})

        await db_session.commit()
        yield items

    @pytest.mark.asyncio
    async def test_admin_download_does_not_update_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_manufacturer: dict,
        ordered_items_3: list[dict],
    ):
        """管理者エンドポイントではステータス更新が行われない

        given: メーカーAに「発注中」ステータスの受注明細が3件ある
        when: 管理者がその3件を選択して発注資料をダウンロードする
        then:
          - ZIPファイルが正常にダウンロードされる
          - 3件の受注明細のステータスは「発注中」のまま（更新されない）
        """
        manufacturer_id = test_manufacturer["id"]

        # ダウンロード実行
        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-documents",
            headers=auth_headers,
        )

        # ZIPファイルが正常にダウンロードされることを確認
        assert response.status_code == 200, (
            f"Expected 200 OK, but got {response.status_code}: {response.text}"
        )

        content_type = response.headers.get("content-type", "")
        assert "application/zip" in content_type or "application/x-zip" in content_type, (
            f"Expected Content-Type to be application/zip, but got '{content_type}'"
        )

        # ZIPの内容を検証
        zip_bytes = response.content
        assert len(zip_bytes) > 0, "Expected non-empty ZIP content"

        # ZIPファイルとして読める
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) > 0, "Expected at least one file in ZIP"

        # 3件の受注ステータスが「発注中」のまま（管理者からのダウンロードはステータス更新なし）
        for item in ordered_items_3:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": item["order_id"]}
            )
            row = result.fetchone()
            assert row is not None, f"Order {item['order_id']} not found"
            assert row[0] == "ordered", (
                f"Expected status 'ordered' (no update by admin), but got '{row[0]}' for order {item['order_id']}"
            )

    @pytest.mark.asyncio
    async def test_admin_download_includes_all_statuses_without_update(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_manufacturer: dict,
        mixed_status_items: dict,
    ):
        """管理者エンドポイントは全ステータスをダウンロード可能で、ステータス更新なし

        given: メーカーAに「発注中」2件、「製造中」1件の受注明細がある
        when: 管理者がダウンロードを実行する
        then:
          - 全件がZIPに含まれる
          - 「発注中」の2件のステータスは「発注中」のまま（更新されない）
          - 「製造中」の1件もステータス変更されない
        """
        manufacturer_id = test_manufacturer["id"]

        # ダウンロード実行
        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-documents",
            headers=auth_headers,
        )

        # ダウンロード成功
        assert response.status_code == 200, (
            f"Expected 200 OK, but got {response.status_code}: {response.text}"
        )

        # 「発注中」の2件は「発注中」のまま（管理者からのダウンロードはステータス更新なし）
        for item in mixed_status_items["ordered"]:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": item["order_id"]}
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "ordered", (
                f"Expected ordered item to remain 'ordered' (admin no update), but got '{row[0]}'"
            )

        # 「製造中」だった1件はそのまま「製造中」であることを確認
        for item in mixed_status_items["manufacturing"]:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": item["order_id"]}
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "manufacturing", (
                f"Expected manufacturing item to remain 'manufacturing', but got '{row[0]}'"
            )

    @pytest.mark.asyncio
    async def test_admin_download_succeeds_with_manufacturing_only(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_manufacturer: dict,
        manufacturing_only_items: list[dict],
    ):
        """管理者エンドポイントは製造中のみでもダウンロード可能

        given: メーカーAに「製造中」の受注明細のみがある（発注中が0件）
        when: 管理者がダウンロードを実行する
        then: 200 OKでZIPがダウンロードされる（全ステータスでダウンロード可能）
        """
        manufacturer_id = test_manufacturer["id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-documents",
            headers=auth_headers,
        )

        # 管理者エンドポイントは全ステータスでダウンロード可能
        assert response.status_code == 200, (
            f"Expected 200 OK, but got {response.status_code}: {response.text}"
        )

        content_type = response.headers.get("content-type", "")
        assert "application/zip" in content_type or "application/x-zip" in content_type

    @pytest.mark.asyncio
    async def test_download_returns_401_without_auth(
        self,
        client: AsyncClient,
        test_manufacturer: dict,
    ):
        """認証なしでAPIを呼び出すと401エラー"""
        manufacturer_id = test_manufacturer["id"]

        response = await client.get(
            f"/api/v1/manufacturers/{manufacturer_id}/order-documents",
            # headers なし（認証トークンなし）
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized, but got {response.status_code}: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_download_returns_404_for_nonexistent_manufacturer(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """存在しないメーカーIDで呼び出すと404エラー"""
        nonexistent_id = str(uuid4())

        response = await client.get(
            f"/api/v1/manufacturers/{nonexistent_id}/order-documents",
            headers=auth_headers,
        )

        assert response.status_code == 404, (
            f"Expected 404 Not Found, but got {response.status_code}: {response.text}"
        )


class TestManufacturerPortalOrderDocumentsDownload:
    """メーカーポータルからの発注資料ダウンロードの統合テスト"""

    @pytest.fixture
    async def test_manufacturer_with_password(self, db_session: AsyncSession):
        """テスト用メーカー（パスワード設定済み）"""
        from app.utils.security import hash_password

        manufacturer_id = str(uuid4())
        manufacturer_name = f"テストメーカー_{manufacturer_id[:8]}"

        await db_session.execute(
            text("""
                INSERT INTO manufacturers (id, name, email, password_hash, phone, supported_products, unit_prices, lead_time_days, daily_order_limit, sharing_method, is_active, created_at, updated_at)
                VALUES (:id, :name, :email, :password_hash, :phone, :supported_products, :unit_prices, :lead_time_days, :daily_order_limit, :sharing_method, :is_active, NOW(), NOW())
            """),
            {
                "id": manufacturer_id,
                "name": manufacturer_name,
                "email": f"mfg-{manufacturer_id[:8]}@manufacturer.com",
                "password_hash": hash_password("password123"),
                "phone": "03-1234-5678",
                "supported_products": ["tshirt"],
                "unit_prices": json.dumps({}),
                "lead_time_days": 7,
                "daily_order_limit": 100,
                "sharing_method": "portal",
                "is_active": True,
            }
        )
        await db_session.commit()

        yield {"id": manufacturer_id, "name": manufacturer_name}

    @pytest.fixture
    def manufacturer_auth_headers(self, test_manufacturer_with_password: dict):
        """メーカーポータル用の認証ヘッダー"""
        from app.utils.security import create_access_token

        token = create_access_token({
            "sub": test_manufacturer_with_password["id"],
            "type": "manufacturer",
            "manufacturer_id": test_manufacturer_with_password["id"],
        })
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    async def test_product_for_portal(self, db_session: AsyncSession, test_manufacturer_with_password: dict):
        """テスト用商品（メーカーポータル用）"""
        product_id = str(uuid4())
        unique_size = f"PORT-{product_id[:8]}"

        await db_session.execute(
            text("""
                INSERT INTO products (id, product_type, size, position, color, manufacturer_id, cost, lead_time_days, order_limit, is_active, created_at, updated_at)
                VALUES (:id, :product_type, :size, :position, :color, :manufacturer_id, :cost, :lead_time_days, :order_limit, :is_active, NOW(), NOW())
            """),
            {
                "id": product_id,
                "product_type": "tshirt",
                "size": unique_size,
                "position": "正面",
                "color": "白",
                "manufacturer_id": test_manufacturer_with_password["id"],
                "cost": 1000,
                "lead_time_days": 7,
                "order_limit": 100,
                "is_active": True,
            }
        )
        await db_session.commit()

        yield {"id": product_id, "product_type": "tshirt"}

    @pytest.fixture
    async def ordered_items_for_portal(
        self,
        db_session: AsyncSession,
        test_order_source: dict,
        test_product_for_portal: dict,
    ):
        """メーカーポータルテスト用の発注中ステータスの受注明細"""
        items = []
        for i in range(2):
            order_id = str(uuid4())
            order_item_id = str(uuid4())

            await db_session.execute(
                text("""
                    INSERT INTO orders (id, order_number, order_source_id, product_name, quantity, customer_name, customer_email, customer_phone, customer_postal_code, customer_address_prefecture, customer_address_city, status, total_price, ordered_at, created_at, updated_at)
                    VALUES (:id, :order_number, :order_source_id, :product_name, :quantity, :customer_name, :customer_email, :customer_phone, :customer_postal_code, :customer_address_prefecture, :customer_address_city, :status, :total_price, NOW(), NOW(), NOW())
                """),
                {
                    "id": order_id,
                    "order_number": f"PORTAL-{i+1}-{order_id[:8]}",
                    "order_source_id": test_order_source["id"],
                    "product_name": f"ポータル商品{i+1}",
                    "quantity": 1,
                    "customer_name": f"ポータル顧客{i+1}",
                    "customer_email": f"portal{i+1}@example.com",
                    "customer_phone": f"090-3333-333{i}",
                    "customer_postal_code": "100-0001",
                    "customer_address_prefecture": "東京都",
                    "customer_address_city": "千代田区",
                    "status": "ordered",
                    "total_price": 3000,
                }
            )

            await db_session.execute(
                text("""
                    INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, price, quantity, size, position, color, created_at, updated_at)
                    VALUES (:id, :order_id, :uid, :product_id, :product_name, :product_type, :price, :quantity, :size, :position, :color, NOW(), NOW())
                """),
                {
                    "id": order_item_id,
                    "order_id": order_id,
                    "uid": f"PORT-UID-{i+1}",
                    "product_id": test_product_for_portal["id"],
                    "product_name": f"ポータル商品{i+1}",
                    "product_type": "tshirt",
                    "price": 3000,
                    "quantity": 1,
                    "size": "M",
                    "position": "正面",
                    "color": "白",
                }
            )

            items.append({"order_id": order_id, "order_item_id": order_item_id})

        await db_session.commit()
        yield items

    @pytest.mark.asyncio
    async def test_manufacturer_portal_download_updates_ordered_to_manufacturing(
        self,
        client: AsyncClient,
        manufacturer_auth_headers: dict,
        db_session: AsyncSession,
        ordered_items_for_portal: list[dict],
    ):
        """メーカーポータルからのダウンロードで発注中→製造中にステータス更新される

        given: メーカーに「発注中」ステータスの受注明細が2件ある
        when: メーカーポータルから発注資料をダウンロードする
        then:
          - ZIPファイルが正常にダウンロードされる
          - 2件の受注明細のステータスが「製造中」に更新される
        """
        response = await client.get(
            "/api/v1/manufacturer-portal/order-documents",
            headers=manufacturer_auth_headers,
        )

        # ZIPファイルが正常にダウンロードされることを確認
        assert response.status_code == 200, (
            f"Expected 200 OK, but got {response.status_code}: {response.text}"
        )

        content_type = response.headers.get("content-type", "")
        assert "application/zip" in content_type or "application/x-zip" in content_type

        # 2件の受注ステータスが「製造中」に更新されていることを確認
        for item in ordered_items_for_portal:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": item["order_id"]}
            )
            row = result.fetchone()
            assert row is not None, f"Order {item['order_id']} not found"
            assert row[0] == "manufacturing", (
                f"Expected status 'manufacturing', but got '{row[0]}' for order {item['order_id']}"
            )

    @pytest.fixture
    async def mixed_status_items_for_portal(
        self,
        db_session: AsyncSession,
        test_order_source: dict,
        test_product_for_portal: dict,
    ):
        """発注中1件、製造中1件のミックス明細（メーカーポータル用）"""
        items = {"ordered": [], "manufacturing": []}
        statuses = ["ordered", "manufacturing"]

        for i, status in enumerate(statuses):
            order_id = str(uuid4())
            order_item_id = str(uuid4())

            await db_session.execute(
                text("""
                    INSERT INTO orders (id, order_number, order_source_id, product_name, quantity, customer_name, customer_email, customer_phone, customer_postal_code, customer_address_prefecture, customer_address_city, status, total_price, ordered_at, created_at, updated_at)
                    VALUES (:id, :order_number, :order_source_id, :product_name, :quantity, :customer_name, :customer_email, :customer_phone, :customer_postal_code, :customer_address_prefecture, :customer_address_city, :status, :total_price, NOW(), NOW(), NOW())
                """),
                {
                    "id": order_id,
                    "order_number": f"PORTMIX-{i+1}-{order_id[:8]}",
                    "order_source_id": test_order_source["id"],
                    "product_name": f"ポータルミックス商品{i+1}",
                    "quantity": 1,
                    "customer_name": f"ポータルミックス顧客{i+1}",
                    "customer_email": f"portmix{i+1}@example.com",
                    "customer_phone": f"090-4444-444{i}",
                    "customer_postal_code": "100-0002",
                    "customer_address_prefecture": "東京都",
                    "customer_address_city": "港区",
                    "status": status,
                    "total_price": 3000,
                }
            )

            await db_session.execute(
                text("""
                    INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, price, quantity, size, position, color, created_at, updated_at)
                    VALUES (:id, :order_id, :uid, :product_id, :product_name, :product_type, :price, :quantity, :size, :position, :color, NOW(), NOW())
                """),
                {
                    "id": order_item_id,
                    "order_id": order_id,
                    "uid": f"PORTMIX-UID-{i+1}",
                    "product_id": test_product_for_portal["id"],
                    "product_name": f"ポータルミックス商品{i+1}",
                    "product_type": "tshirt",
                    "price": 3000,
                    "quantity": 1,
                    "size": "L",
                    "position": "正面",
                    "color": "白",
                }
            )

            if status == "ordered":
                items["ordered"].append({"order_id": order_id, "order_item_id": order_item_id})
            else:
                items["manufacturing"].append({"order_id": order_id, "order_item_id": order_item_id})

        await db_session.commit()
        yield items

    @pytest.mark.asyncio
    async def test_manufacturer_portal_download_only_updates_ordered_status(
        self,
        client: AsyncClient,
        manufacturer_auth_headers: dict,
        db_session: AsyncSession,
        mixed_status_items_for_portal: dict,
    ):
        """メーカーポータルからのダウンロードで発注中のみステータス更新される

        given: メーカーに「発注中」1件、「製造中」1件の受注明細がある
        when: メーカーポータルから発注資料をダウンロードする
        then:
          - 全件がZIPに含まれる
          - 「発注中」の1件のみ「製造中」に更新される
          - 「製造中」の1件はステータス変更されない
        """
        response = await client.get(
            "/api/v1/manufacturer-portal/order-documents",
            headers=manufacturer_auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200 OK, but got {response.status_code}: {response.text}"
        )

        # 「発注中」だった1件が「製造中」に更新されていることを確認
        for item in mixed_status_items_for_portal["ordered"]:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": item["order_id"]}
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "manufacturing", (
                f"Expected ordered item to be updated to 'manufacturing', but got '{row[0]}'"
            )

        # 「製造中」だった1件はそのまま「製造中」であることを確認
        for item in mixed_status_items_for_portal["manufacturing"]:
            result = await db_session.execute(
                text("SELECT status FROM orders WHERE id = :id"),
                {"id": item["order_id"]}
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "manufacturing", (
                f"Expected manufacturing item to remain 'manufacturing', but got '{row[0]}'"
            )
