"""ステッカー「クリア」カラー削除の統合テスト

FEAT-0007: ステッカー商品タイプから「クリア」カラーを削除し、
「ホワイト」のみの単一カラー体制にする。

このテストは、外部API経由でステッカーのカラーバリデーションが
正しく動作することを検証します。

テスト対象エンドポイント:
- GET  /api/v1/external/product-options/sticker
- POST /api/v1/external/price-calculation
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4


class TestStickerColorRemovalAPI:
    """ステッカーカラー削除の統合テスト（API経由）"""

    @pytest.fixture
    async def api_key_headers(self, db_session: AsyncSession):
        """テスト用のAPIキーを作成し、ヘッダーとして返す"""
        source_id = str(uuid4())
        source_code = f"STICKER{source_id[:6].upper()}"
        api_key = f"test-sticker-api-key-{source_id}"

        await db_session.execute(
            text("""
                INSERT INTO order_sources (id, code, name, api_key, phone, postal_code, address_prefecture, address_city, is_active, created_at, updated_at)
                VALUES (:id, :code, :name, :api_key, :phone, :postal_code, :address_prefecture, :address_city, :is_active, NOW(), NOW())
            """),
            {
                "id": source_id,
                "code": source_code,
                "name": "Sticker Test Source",
                "api_key": api_key,
                "phone": "090-0000-0000",
                "postal_code": "100-0001",
                "address_prefecture": "東京都",
                "address_city": "千代田区",
                "is_active": True,
            }
        )
        await db_session.commit()

        yield {"X-API-Key": api_key}

    @pytest.mark.asyncio
    async def test_product_options_sticker_returns_only_white(
        self,
        client: AsyncClient,
        api_key_headers: dict,
    ):
        """AC-004 統合: ステッカーの商品オプションAPIが「ホワイト」のみ返すこと

        given: 外部API認証済み
        when: GET /api/v1/external/product-options/sticker を呼び出す
        then: color リストに「ホワイト」のみが含まれ、「クリア」は含まれない
        """
        response = await client.get(
            "/api/v1/external/product-options/sticker",
            headers=api_key_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200 OK, but got {response.status_code}: {response.text}"
        )

        data = response.json()
        assert data["product_type"] == "sticker"
        assert data["color"] == ["ホワイト"], (
            f"ステッカーのカラーは ['ホワイト'] のみであるべきですが、{data['color']} が返されました。"
        )
        assert "クリア" not in data["color"], (
            "ステッカーのカラーに「クリア」が含まれています。"
        )

    @pytest.mark.asyncio
    async def test_price_calculation_sticker_rejects_clear(
        self,
        client: AsyncClient,
        api_key_headers: dict,
    ):
        """AC-005 統合: ステッカーの価格計算APIで「クリア」が拒否されること

        given: 外部API認証済み
        when: POST /api/v1/external/price-calculation で color=クリア を指定
        then: 400エラーが返される
        """
        response = await client.post(
            "/api/v1/external/price-calculation",
            headers={**api_key_headers, "Content-Type": "application/json"},
            json={
                "product_type": "sticker",
                "size": "100x100mm",
                "color": "クリア",
                "quantity": 1,
            },
        )

        assert response.status_code == 400, (
            f"Expected 400 Bad Request, but got {response.status_code}: {response.text}"
        )

        data = response.json()
        assert "error" in data, "Expected error response"
        assert data["error"]["code"] == "VALIDATION_ERROR", (
            f"Expected error code 'VALIDATION_ERROR', but got '{data['error']['code']}'"
        )

    @pytest.mark.asyncio
    async def test_price_calculation_sticker_accepts_white(
        self,
        client: AsyncClient,
        api_key_headers: dict,
    ):
        """AC-006 統合: ステッカーの価格計算APIで「ホワイト」が成功すること

        given: 外部API認証済み
        when: POST /api/v1/external/price-calculation で color=ホワイト を指定
        then: 単価79円で価格計算が成功する
        """
        response = await client.post(
            "/api/v1/external/price-calculation",
            headers={**api_key_headers, "Content-Type": "application/json"},
            json={
                "product_type": "sticker",
                "size": "100x100mm",
                "color": "ホワイト",
                "quantity": 5,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200 OK, but got {response.status_code}: {response.text}"
        )

        data = response.json()
        assert data["product_type"] == "sticker"
        assert data["color"] == "ホワイト"
        assert data["unit_price"] == 79, (
            f"ステッカー「ホワイト」の単価は79円であるべきですが、{data['unit_price']}円です。"
        )
        assert data["total_price"] == 79 * 5, (
            f"合計金額は {79 * 5}円であるべきですが、{data['total_price']}円です。"
        )
        assert data["quantity"] == 5

    @pytest.mark.asyncio
    async def test_price_calculation_sticker_white_single(
        self,
        client: AsyncClient,
        api_key_headers: dict,
    ):
        """AC-006 統合: ステッカー「ホワイト」の単品価格計算

        given: 外部API認証済み
        when: POST /api/v1/external/price-calculation で color=ホワイト, quantity=1
        then: 単価79円、合計79円で成功する
        """
        response = await client.post(
            "/api/v1/external/price-calculation",
            headers={**api_key_headers, "Content-Type": "application/json"},
            json={
                "product_type": "sticker",
                "size": "100x100mm",
                "color": "ホワイト",
                "quantity": 1,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200 OK, but got {response.status_code}: {response.text}"
        )

        data = response.json()
        assert data["unit_price"] == 79
        assert data["total_price"] == 79

    @pytest.mark.asyncio
    async def test_product_options_sticker_returns_correct_size(
        self,
        client: AsyncClient,
        api_key_headers: dict,
    ):
        """統合: ステッカーの商品オプションAPIがサイズも正しく返すこと

        given: 外部API認証済み
        when: GET /api/v1/external/product-options/sticker を呼び出す
        then: size リストに「100x100mm」のみが含まれる
        """
        response = await client.get(
            "/api/v1/external/product-options/sticker",
            headers=api_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["size"] == ["100x100mm"]
        assert data["position"] == []
