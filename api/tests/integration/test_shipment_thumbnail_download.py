"""統合テスト: 配送サムネイル画像ZIPダウンロードAPI

FEAT-0022: 配送一覧ページから選択した配送に紐づく商品サムネイル画像をZIPダウンロード

受け入れ基準:
- AC-010: POST /shipments/download-thumbnails が ZIPファイルをレスポンスとして返す
- AC-011: 管理者認証が必要

NOTE: These tests are written in TDD Red phase - the implementation does not exist yet.
Tests will fail until the implementation is completed.
"""

import io
import json
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TestShipmentThumbnailDownloadAPI:
    """配送サムネイル画像ZIPダウンロードAPIの統合テスト."""

    @pytest.fixture
    async def test_product(self, db_session: AsyncSession, test_order_source: dict):
        """テスト用商品（メーカーに紐づく）."""
        manufacturer_id = str(uuid4())
        manufacturer_name = f"テストメーカー_{manufacturer_id[:8]}"

        await db_session.execute(
            text("""
                INSERT INTO manufacturers (id, name, email, phone, supported_products, unit_prices, lead_time_days, daily_order_limit, sharing_method, is_active, created_at, updated_at)
                VALUES (:id, :name, :email, :phone, :supported_products, :unit_prices, :lead_time_days, :daily_order_limit, :sharing_method, :is_active, NOW(), NOW())
            """),
            {
                "id": manufacturer_id,
                "name": manufacturer_name,
                "email": "test-mfr-thumb@example.com",
                "phone": "03-0000-0001",
                "supported_products": ["tshirt"],
                "unit_prices": json.dumps({}),
                "lead_time_days": 7,
                "daily_order_limit": 100,
                "sharing_method": "portal",
                "is_active": True,
            }
        )

        product_id = str(uuid4())
        unique_size = f"THUMB-{product_id[:8]}"

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
                "manufacturer_id": manufacturer_id,
                "cost": 1000,
                "lead_time_days": 7,
                "order_limit": 100,
                "is_active": True,
            }
        )
        await db_session.commit()

        yield {"id": product_id, "product_type": "tshirt"}

    @pytest.fixture
    async def shipment_with_thumbnails(
        self,
        db_session: AsyncSession,
        test_order_source: dict,
        test_product: dict,
    ):
        """thumbnail_image_url を持つ OrderItem が紐づく配送を作成."""
        shipment_id = str(uuid4())
        orders = []

        # 2つの注文を作成し、それぞれの OrderItem に thumbnail_image_url を設定
        for i in range(2):
            order_id = str(uuid4())
            order_item_id = str(uuid4())
            order_number = f"THUMB-{i+1}-{order_id[:8]}"

            await db_session.execute(
                text("""
                    INSERT INTO orders (id, order_number, order_source_id, product_name, quantity, customer_name, customer_email, customer_phone, customer_postal_code, customer_address_prefecture, customer_address_city, status, total_price, ordered_at, created_at, updated_at)
                    VALUES (:id, :order_number, :order_source_id, :product_name, :quantity, :customer_name, :customer_email, :customer_phone, :customer_postal_code, :customer_address_prefecture, :customer_address_city, :status, :total_price, NOW(), NOW(), NOW())
                """),
                {
                    "id": order_id,
                    "order_number": order_number,
                    "order_source_id": test_order_source["id"],
                    "product_name": f"テストサムネイル商品{i+1}",
                    "quantity": 1,
                    "customer_name": f"テスト顧客サムネイル{i+1}",
                    "customer_email": f"thumb-customer{i+1}@example.com",
                    "customer_phone": f"090-7777-000{i}",
                    "customer_postal_code": "100-0001",
                    "customer_address_prefecture": "東京都",
                    "customer_address_city": "千代田区",
                    "status": "delivered",
                    "total_price": 3000,
                }
            )

            await db_session.execute(
                text("""
                    INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, price, quantity, size, position, color, thumbnail_image_url, created_at, updated_at)
                    VALUES (:id, :order_id, :uid, :product_id, :product_name, :product_type, :price, :quantity, :size, :position, :color, :thumbnail_image_url, NOW(), NOW())
                """),
                {
                    "id": order_item_id,
                    "order_id": order_id,
                    "uid": f"THUMB-UID-{i+1}",
                    "product_id": test_product["id"],
                    "product_name": f"テストサムネイル商品{i+1}",
                    "product_type": "tshirt",
                    "price": 3000,
                    "quantity": 1,
                    "size": "M",
                    "position": "正面",
                    "color": "白",
                    "thumbnail_image_url": f"https://example.com/thumbnails/thumb{i+1}.png",
                }
            )

            orders.append({"order_id": order_id, "order_item_id": order_item_id})

        # 配送を作成
        await db_session.execute(
            text("""
                INSERT INTO shipments (id, status, created_at, updated_at)
                VALUES (:id, :status, NOW(), NOW())
            """),
            {
                "id": shipment_id,
                "status": "pending",
            }
        )

        # ShipmentItems を作成
        for order_data in orders:
            si_id = str(uuid4())
            await db_session.execute(
                text("""
                    INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
                    VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
                """),
                {
                    "id": si_id,
                    "shipment_id": shipment_id,
                    "order_id": order_data["order_id"],
                }
            )

        await db_session.commit()
        yield {"shipment_id": shipment_id, "orders": orders}

    # ======================================
    # AC-010: POST /shipments/download-thumbnails が ZIPファイルを返す
    # ======================================

    @pytest.mark.asyncio
    async def test_download_thumbnails_returns_zip(
        self,
        client: AsyncClient,
        auth_headers: dict,
        shipment_with_thumbnails: dict,
    ):
        """AC-010: POST /api/v1/shipments/download-thumbnails が対象サムネイル画像を含むZIPファイルを返す.

        given: thumbnail_image_url を持つ OrderItem が紐づく配送が存在する
        when: POST /api/v1/shipments/download-thumbnails に shipment_ids を送信する
        then: Content-Type が application/zip、Content-Disposition に適切なファイル名が設定されたレスポンスが返される
        """
        shipment_ids = [shipment_with_thumbnails["shipment_id"]]

        # Mock httpx image fetch (外部URL取得をモック)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake-thumbnail-image-data-for-integration-test"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockHttpxClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockHttpxClient.return_value = mock_client_instance

            response = await client.post(
                "/api/v1/shipments/download-thumbnails",
                json={"shipment_ids": shipment_ids},
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

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            # 1配送 x 2注文 x 各1アイテム = 2ファイル
            assert len(file_list) == 2, (
                f"Expected 2 files in ZIP, but got {len(file_list)}: {file_list}"
            )

    @pytest.mark.asyncio
    async def test_download_thumbnails_zip_filename_header(
        self,
        client: AsyncClient,
        auth_headers: dict,
        shipment_with_thumbnails: dict,
    ):
        """ZIPファイル名が「配送サムネイル_{YYYYMMDD_HHMMSS}.zip」形式であること."""
        shipment_ids = [shipment_with_thumbnails["shipment_id"]]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake-thumbnail-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockHttpxClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockHttpxClient.return_value = mock_client_instance

            response = await client.post(
                "/api/v1/shipments/download-thumbnails",
                json={"shipment_ids": shipment_ids},
                headers=auth_headers,
            )

        assert response.status_code == 200

        # Content-Disposition ヘッダーにファイル名が含まれること
        content_disposition = response.headers.get("content-disposition", "")
        assert "配送サムネイル" in content_disposition or "attachment" in content_disposition, (
            f"Expected Content-Disposition with filename, but got '{content_disposition}'"
        )

    # ======================================
    # AC-011: 管理者認証が必要
    # ======================================

    @pytest.mark.asyncio
    async def test_download_thumbnails_returns_401_without_auth(
        self,
        client: AsyncClient,
        shipment_with_thumbnails: dict,
    ):
        """AC-011: 認証されていないユーザーは 401 エラーが返される.

        given: 認証されていないユーザー
        when: POST /api/v1/shipments/download-thumbnails を呼び出す
        then: 401 Unauthorized エラーが返される
        """
        shipment_ids = [shipment_with_thumbnails["shipment_id"]]

        response = await client.post(
            "/api/v1/shipments/download-thumbnails",
            json={"shipment_ids": shipment_ids},
            # headers なし（認証トークンなし）
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized, but got {response.status_code}: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_download_thumbnails_empty_shipment_ids_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """空の shipment_ids リストで 422 バリデーションエラーが返される."""
        response = await client.post(
            "/api/v1/shipments/download-thumbnails",
            json={"shipment_ids": []},
            headers=auth_headers,
        )

        assert response.status_code == 422, (
            f"Expected 422 Validation Error, but got {response.status_code}: {response.text}"
        )
