"""梱包写真取得APIの統合テスト

FEAT-0003: 管理者が配送詳細画面でアップロード済みの梱包写真をプレビュー表示できる

このテストは、梱包写真取得API（GET /api/v1/shipments/{shipment_id}/packing-photo）の
動作を検証します。
"""

from typing import Any

import pytest
from httpx import AsyncClient


class TestPackingPhotoAPI:
    """梱包写真取得APIの統合テスト"""

    @pytest.mark.asyncio
    async def test_get_packing_photo_returns_image_when_exists(
        self, client: AsyncClient, auth_headers: dict[str, Any], shipment_with_photo: dict[str, Any]
    ) -> None:
        """AC-001: 梱包写真が存在する配送で、APIから画像を取得できる

        given: packing_photo_path が設定された配送データが存在する
        when: GET /api/v1/shipments/{shipment_id}/packing-photo を呼び出す
        then: 画像バイナリが適切なContent-Typeで返される
        """
        shipment_id = shipment_with_photo["id"]

        response = await client.get(
            f"/api/v1/shipments/{shipment_id}/packing-photo",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200 OK for shipment with photo, "
            f"but got {response.status_code}: {response.text}"
        )

        # Content-Typeが画像形式であることを確認
        content_type = response.headers.get("content-type", "")
        assert content_type.startswith("image/"), (
            f"Expected Content-Type to start with 'image/', "
            f"but got '{content_type}'"
        )

        # レスポンスボディが空でないことを確認
        assert len(response.content) > 0, "Expected non-empty image content"

    @pytest.mark.asyncio
    async def test_get_packing_photo_returns_404_when_no_photo(
        self, client: AsyncClient, auth_headers: dict[str, Any], shipment_without_photo: dict[str, Any]
    ) -> None:
        """AC-002: 梱包写真が存在しない配送でAPIを呼び出すと404エラー

        given: packing_photo_path が null の配送データが存在する
        when: GET /api/v1/shipments/{shipment_id}/packing-photo を呼び出す
        then: 404 Not Found エラーが返される
        """
        shipment_id = shipment_without_photo["id"]

        response = await client.get(
            f"/api/v1/shipments/{shipment_id}/packing-photo",
            headers=auth_headers,
        )

        assert response.status_code == 404, (
            f"Expected 404 Not Found for shipment without photo, "
            f"but got {response.status_code}: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_get_packing_photo_returns_404_when_shipment_not_exists(
        self, client: AsyncClient, auth_headers: dict[str, Any]
    ) -> None:
        """AC-003: 存在しない配送IDでAPIを呼び出すと404エラー

        given: 存在しないshipment_id
        when: GET /api/v1/shipments/{shipment_id}/packing-photo を呼び出す
        then: 404 Not Found エラーが返される
        """
        non_existent_id = "00000000-0000-0000-0000-000000000000"

        response = await client.get(
            f"/api/v1/shipments/{non_existent_id}/packing-photo",
            headers=auth_headers,
        )

        assert response.status_code == 404, (
            f"Expected 404 Not Found for non-existent shipment, "
            f"but got {response.status_code}: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_get_packing_photo_returns_401_without_auth(
        self, client: AsyncClient, shipment_with_photo: dict[str, Any]
    ) -> None:
        """AC-004: 認証なしでAPIを呼び出すと401エラー

        given: 認証トークンなし
        when: GET /api/v1/shipments/{shipment_id}/packing-photo を呼び出す
        then: 401 Unauthorized エラーが返される
        """
        shipment_id = shipment_with_photo["id"]

        response = await client.get(
            f"/api/v1/shipments/{shipment_id}/packing-photo",
            # headers なし（認証トークンなし）
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized without auth token, "
            f"but got {response.status_code}: {response.text}"
        )
