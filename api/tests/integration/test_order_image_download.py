"""統合テスト: 受注イメージ画像ZIPダウンロードAPI

FEAT-0018: 受注イメージ画像ZIPダウンロード

受け入れ基準:
- AC-003: APIエンドポイントが選択された受注IDに紐づくdesign_image_urlを収集してZIPを返す
- AC-010: 管理者認証が必要

NOTE: These tests are written in TDD Red phase - the implementation does not exist yet.
Tests will fail until the implementation is completed.
"""

import io
import json
import zipfile
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TestOrderImageDownloadAPI:
    """受注イメージ画像ZIPダウンロードAPIの統合テスト."""

    @pytest.fixture
    async def test_product(self, db_session: AsyncSession, test_order_source: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
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
                "email": "test-mfr@example.com",
                "phone": "03-0000-0000",
                "supported_products": ["tshirt"],
                "unit_prices": json.dumps({}),
                "lead_time_days": 7,
                "daily_order_limit": 100,
                "sharing_method": "portal",
                "is_active": True,
            }
        )

        product_id = str(uuid4())
        unique_size = f"IMG-{product_id[:8]}"

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
    async def orders_with_images(
        self,
        db_session: AsyncSession,
        test_order_source: dict[str, Any],
        test_product: dict[str, Any],
    ) -> AsyncIterator[Any]:
        """design_image_urlを持つOrderItemが紐づく受注を2件作成."""
        orders = []
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
                    "order_number": f"IMG-{i+1}-{order_id[:8]}",
                    "order_source_id": test_order_source["id"],
                    "product_name": f"テスト商品{i+1}",
                    "quantity": 1,
                    "customer_name": f"テスト顧客{i+1}",
                    "customer_email": f"img-customer{i+1}@example.com",
                    "customer_phone": f"090-8888-000{i}",
                    "customer_postal_code": "100-0001",
                    "customer_address_prefecture": "東京都",
                    "customer_address_city": "千代田区",
                    "status": "ordered",
                    "total_price": 3000,
                }
            )

            await db_session.execute(
                text("""
                    INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, price, quantity, size, position, color, design_image_url, created_at, updated_at)
                    VALUES (:id, :order_id, :uid, :product_id, :product_name, :product_type, :price, :quantity, :size, :position, :color, :design_image_url, NOW(), NOW())
                """),
                {
                    "id": order_item_id,
                    "order_id": order_id,
                    "uid": f"IMG-UID-{i+1}",
                    "product_id": test_product["id"],
                    "product_name": f"テスト商品{i+1}",
                    "product_type": "tshirt",
                    "price": 3000,
                    "quantity": 1,
                    "size": "M",
                    "position": "正面",
                    "color": "白",
                    "design_image_url": f"https://example.com/designs/design{i+1}.png",
                }
            )

            orders.append({"order_id": order_id, "order_item_id": order_item_id})

        await db_session.commit()
        yield orders

    # ======================================
    # AC-003: APIがZIPを返す
    # ======================================

    @pytest.mark.asyncio
    async def test_download_images_returns_zip(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        orders_with_images: list[dict[str, Any]],
    ) -> None:
        """AC-003: POST /api/v1/orders/download-images が対象画像を含むZIPファイルを返す.

        given: design_image_urlを持つOrderItemが紐づく受注が存在する
        when: POST /api/v1/orders/download-images に対象のorder_idsを送信する
        then: 対象画像を含むZIPファイルがレスポンスとして返される
        """
        order_ids = [item["order_id"] for item in orders_with_images]

        # Mock httpx image fetch (外部URL取得をモック)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake-image-data-for-integration-test"
        mock_response.headers = {"content-type": "image/png"}

        with patch("httpx.AsyncClient") as MockHttpxClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockHttpxClient.return_value = mock_client_instance

            response = await client.post(
                "/api/v1/orders/download-images",
                json={"order_ids": order_ids},
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
            # 2件の受注 x 各1アイテム = 2ファイル
            assert len(file_list) == 2, (
                f"Expected 2 files in ZIP, but got {len(file_list)}: {file_list}"
            )

    @pytest.mark.asyncio
    async def test_download_images_zip_filename_header(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        orders_with_images: list[dict[str, Any]],
    ) -> None:
        """ZIPファイル名が「受注画像_{YYYYMMDD_HHMMSS}.zip」形式であること."""
        order_ids = [item["order_id"] for item in orders_with_images]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake-image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("httpx.AsyncClient") as MockHttpxClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockHttpxClient.return_value = mock_client_instance

            response = await client.post(
                "/api/v1/orders/download-images",
                json={"order_ids": order_ids},
                headers=auth_headers,
            )

        assert response.status_code == 200

        # Content-Disposition ヘッダーにファイル名が含まれること
        content_disposition = response.headers.get("content-disposition", "")
        assert "受注画像_" in content_disposition or "attachment" in content_disposition, (
            f"Expected Content-Disposition with filename, but got '{content_disposition}'"
        )

    # ======================================
    # AC-010: 管理者認証が必要
    # ======================================

    @pytest.mark.asyncio
    async def test_download_images_returns_401_without_auth(
        self,
        client: AsyncClient,
        orders_with_images: list[dict[str, Any]],
    ) -> None:
        """AC-010: 認証されていないユーザーは401エラーが返される.

        given: 認証されていないユーザー
        when: POST /api/v1/orders/download-images を呼び出す
        then: 401 Unauthorizedエラーが返される
        """
        order_ids = [item["order_id"] for item in orders_with_images]

        response = await client.post(
            "/api/v1/orders/download-images",
            json={"order_ids": order_ids},
            # headers なし（認証トークンなし）
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized, but got {response.status_code}: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_download_images_empty_order_ids_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
    ) -> None:
        """空のorder_idsリストで422バリデーションエラーが返される."""
        response = await client.post(
            "/api/v1/orders/download-images",
            json={"order_ids": []},
            headers=auth_headers,
        )

        assert response.status_code == 422, (
            f"Expected 422 Validation Error, but got {response.status_code}: {response.text}"
        )
