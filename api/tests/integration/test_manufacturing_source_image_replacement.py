"""Integration tests for 元画像差し替え API（製造データの元画像アップロード）.

v2 受注で作られた製造データ行に対し、管理画面からの元画像差し替えが
API -> Service -> FileStorage/DB まで一貫して機能することを検証する。

illustrator-vm は未設定（テスト環境）のため、差し替え後のバックグラウンド生成は最終的に
failed になる。本テストは同期的に確定する状態（source_images の置き換え・保存・明細の降格・
拒否条件）のみを検証する。
"""

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PNG = b"\x89PNG\r\n\x1a\n" + b"replaced-color-layer"


def _order_number() -> str:
    """テスト用のユニークな受注番号（7桁数字）."""
    return f"{uuid4().int % 10**7:07d}"


@pytest.fixture
async def keychain_setup(db_session: AsyncSession):
    """acrylic_keychain のメーカー・商品マスタ・API キー付き受注元を用意する."""
    manufacturer_id = str(uuid4())
    await db_session.execute(
        text("""
            INSERT INTO manufacturers (
                id, name, email, supported_products, unit_prices, lead_time_days,
                daily_order_limit, sharing_method, is_active, created_at, updated_at
            )
            VALUES (
                :id, :name, :email, :supported_products, :unit_prices, 5,
                100, 'portal', true, NOW(), NOW()
            )
        """),
        {
            "id": manufacturer_id,
            "name": f"SRCIMG_{manufacturer_id[:8]}",
            "email": f"srcimg-{manufacturer_id[:8]}@example.com",
            "supported_products": ["acrylic_keychain"],
            "unit_prices": json.dumps({"acrylic_keychain": 300}),
            "lead_time_days": 5,
        },
    )

    product_id = str(uuid4())
    await db_session.execute(
        text("""
            INSERT INTO products (
                id, product_type, size, position, color, manufacturer_id, cost,
                lead_time_days, is_active, created_at, updated_at
            )
            VALUES (
                :id, 'acrylic_keychain', :size, NULL, NULL, :manufacturer_id, 300,
                5, true, NOW(), NOW()
            )
        """),
        {"id": product_id, "size": f"KC-{product_id[:8]}", "manufacturer_id": manufacturer_id},
    )

    source_id = str(uuid4())
    api_key = f"srcimg-api-key-{source_id}"
    await db_session.execute(
        text("""
            INSERT INTO order_sources (
                id, code, name, api_key, phone, postal_code,
                address_prefecture, address_city, is_active, created_at, updated_at
            )
            VALUES (
                :id, :code, 'SRCIMG Source', :api_key, '090-1234-5678', '100-0001',
                '東京都', '千代田区', true, NOW(), NOW()
            )
        """),
        {"id": source_id, "code": f"SRC{source_id[:8].upper()}", "api_key": api_key},
    )
    await db_session.commit()
    yield {"order_source_id": source_id, "api_key": api_key}


async def _create_v2_order(
    client: AsyncClient, db_session: AsyncSession, api_key: str, order_number: str
) -> dict:
    """v2 受注を1件作成し、注文IDと紐付いた製造データIDを返す.

    製造データの紐付けは受注レスポンス生成後（prepare_for_order）に確定するため、
    id は DB から引く。
    """
    payload = {
        "order_number": order_number,
        "customer": {
            "name": "山田太郎",
            "postal_code": "123-4567",
            "address_prefecture": "東京都",
            "address_city": "渋谷区1-2-3",
            "phone": "03-1234-5678",
            "email": "yamada@example.com",
        },
        "items": [
            {
                "uid": "2000001",
                "product_type": "acrylic_keychain",
                "product_name": "アクリルキーホルダー デザインA",
                "price": 1200,
                "quantity": 1,
                "size": "50x50mm",
                "color": "アクリル",
                "product_code": f"RKSYO-{uuid4().hex[:6]}",
                "source_images": [
                    {"layer_type": "color", "url": "https://example.com/color.png"},
                    {"layer_type": "cutline", "url": "https://example.com/cutline.png"},
                ],
            }
        ],
    }
    resp = await client.post(
        "/api/v2/orders", json=payload, headers={"X-API-Key": api_key}
    )
    assert resp.status_code == 201, resp.text
    order_id = resp.json()["id"]
    mfg_id = (
        await db_session.execute(
            text("SELECT manufacturing_data_id FROM order_items WHERE order_id = :oid"),
            {"oid": order_id},
        )
    ).scalar_one()
    assert mfg_id is not None
    return {"order_id": order_id, "mfg_id": str(mfg_id)}


class TestReplaceSourceImagesAPI:
    @pytest.mark.asyncio
    async def test_detail_reports_external_layers_before_replacement(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        keychain_setup: dict,
        auth_headers: dict,
    ):
        created = await _create_v2_order(client, db_session, keychain_setup["api_key"], _order_number())

        resp = await client.get(
            f"/api/v1/manufacturing-data/{created['mfg_id']}", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["source_images_replaced_at"] is None
        assert {(ly["layer_type"], ly["origin"]) for ly in body["source_images"]} == {
            ("color", "external"),
            ("cutline", "external"),
        }

    @pytest.mark.asyncio
    async def test_replace_stores_upload_and_restarts_generation(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        keychain_setup: dict,
        auth_headers: dict,
    ):
        created = await _create_v2_order(client, db_session, keychain_setup["api_key"], _order_number())
        mfg_id = created["mfg_id"]

        resp = await client.post(
            f"/api/v1/manufacturing-data/{mfg_id}/source-images",
            headers=auth_headers,
            files={"color": ("fixed_color.png", PNG, "image/png")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "pending"  # 再生成待ちへ戻る
        assert body["source_images_replaced_at"] is not None
        assert body["source_images_replaced_by"] == "test-admin@example.com"
        layers = {ly["layer_type"]: ly for ly in body["source_images"]}
        assert layers["color"]["origin"] == "uploaded"
        assert layers["color"]["filename"] == "fixed_color.png"
        assert layers["cutline"]["origin"] == "external"  # 未指定レイヤーは元のURLのまま

        # DB の source_images が file_path 形式へ置き換わっている
        stored = (
            await db_session.execute(
                text("SELECT source_images FROM manufacturing_data WHERE id = :id"),
                {"id": mfg_id},
            )
        ).scalar_one()
        by_layer = {img["layer_type"]: img for img in stored}
        assert by_layer["color"]["file_path"].startswith("source_images/")
        assert by_layer["cutline"]["url"] == "https://example.com/cutline.png"

        # 保存済み元画像を取得できる（プレビュー用）
        preview = await client.get(
            f"/api/v1/manufacturing-data/{mfg_id}/source-images/color", headers=auth_headers
        )
        assert preview.status_code == 200
        assert preview.content == PNG

        # 外部URLのみのレイヤーは実体を持たないため 404
        missing = await client.get(
            f"/api/v1/manufacturing-data/{mfg_id}/source-images/cutline", headers=auth_headers
        )
        assert missing.status_code == 404

    @pytest.mark.asyncio
    async def test_replace_demotes_referencing_items(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        keychain_setup: dict,
        auth_headers: dict,
    ):
        created = await _create_v2_order(client, db_session, keychain_setup["api_key"], _order_number())
        # 生成完了済み（発注可能）の状態を作る
        await db_session.execute(
            text(
                "UPDATE manufacturing_data SET status = 'ready', file_path = 'x.ai' "
                "WHERE id = :id"
            ),
            {"id": created["mfg_id"]},
        )
        await db_session.execute(
            text("UPDATE order_items SET status = 'ordered' WHERE order_id = :oid"),
            {"oid": created["order_id"]},
        )
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/manufacturing-data/{created['mfg_id']}/source-images",
            headers=auth_headers,
            files={"color": ("fixed_color.png", PNG, "image/png")},
        )
        assert resp.status_code == 200, resp.text

        # 未完成の製造データで発注されないよう、明細は「発注準備中」へ戻る
        statuses = (
            await db_session.execute(
                text("SELECT status FROM order_items WHERE order_id = :oid"),
                {"oid": created["order_id"]},
            )
        ).scalars().all()
        assert set(statuses) == {"preparing_order"}

    @pytest.mark.asyncio
    async def test_rejects_when_shared_order_is_in_manufacturing(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        keychain_setup: dict,
        auth_headers: dict,
    ):
        created = await _create_v2_order(client, db_session, keychain_setup["api_key"], _order_number())
        await db_session.execute(
            text("UPDATE order_items SET status = 'manufacturing' WHERE order_id = :oid"),
            {"oid": created["order_id"]},
        )
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/manufacturing-data/{created['mfg_id']}/source-images",
            headers=auth_headers,
            files={"color": ("fixed_color.png", PNG, "image/png")},
        )
        assert resp.status_code == 409, resp.text

    @pytest.mark.asyncio
    async def test_rejects_non_png_upload(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        keychain_setup: dict,
        auth_headers: dict,
    ):
        created = await _create_v2_order(client, db_session, keychain_setup["api_key"], _order_number())

        resp = await client.post(
            f"/api/v1/manufacturing-data/{created['mfg_id']}/source-images",
            headers=auth_headers,
            files={"color": ("fake.png", b"GIF89a-not-a-png", "image/png")},
        )
        assert resp.status_code == 400, resp.text

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client: AsyncClient):
        resp = await client.post(
            f"/api/v1/manufacturing-data/{uuid4()}/source-images",
            files={"color": ("fixed_color.png", PNG, "image/png")},
        )
        assert resp.status_code == 401, resp.text
