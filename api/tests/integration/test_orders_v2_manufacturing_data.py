"""Integration tests for v2 order intake and manufacturing-data generation.

外部注文 v2（POST /api/v2/orders）の受付・製造データ紐付け・キャッシュ再利用・発注ゲートを
API -> Service -> Repository -> DB の一連の流れで検証する。

illustrator-vm は未設定（テスト環境）のため、バックグラウンド生成は最終的に failed になる。
本テストは「同期的に確定する状態（行の作成・紐付け・キャッシュキー・発注ゲート）」のみを検証し、
非同期生成の最終状態には依存しない。
"""

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def mfg_manufacturer(db_session: AsyncSession):
    """acrylic_keychain を扱うメーカー."""
    manufacturer_id = str(uuid4())
    await db_session.execute(
        text("""
            INSERT INTO manufacturers (
                id, name, email, supported_products, unit_prices, lead_time_days,
                daily_order_limit, sharing_method, is_active, created_at, updated_at
            )
            VALUES (
                :id, :name, :email, :supported_products, :unit_prices, :lead_time_days,
                :daily_order_limit, :sharing_method, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": manufacturer_id,
            "name": f"MFGテスト_{manufacturer_id[:8]}",
            "email": f"mfg-{manufacturer_id[:8]}@example.com",
            "supported_products": ["acrylic_keychain"],
            "unit_prices": json.dumps({"acrylic_keychain": 300}),
            "lead_time_days": 5,
            "daily_order_limit": 100,
            "sharing_method": "portal",
            "is_active": True,
        },
    )
    await db_session.commit()
    yield {"id": manufacturer_id}


@pytest.fixture
async def mfg_keychain_product(db_session: AsyncSession, mfg_manufacturer: dict):
    """acrylic_keychain のマスタ商品."""
    product_id = str(uuid4())
    await db_session.execute(
        text("""
            INSERT INTO products (
                id, product_type, size, position, color, manufacturer_id, cost,
                lead_time_days, is_active, created_at, updated_at
            )
            VALUES (
                :id, :product_type, :size, :position, :color, :manufacturer_id, :cost,
                :lead_time_days, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": product_id,
            "product_type": "acrylic_keychain",
            "size": f"KC-{product_id[:8]}",
            "position": None,
            "color": None,
            "manufacturer_id": mfg_manufacturer["id"],
            "cost": 300,
            "lead_time_days": 5,
            "is_active": True,
        },
    )
    await db_session.commit()
    yield {"id": product_id}


@pytest.fixture
async def mfg_order_source(db_session: AsyncSession):
    """API キー付きの受注元."""
    source_id = str(uuid4())
    api_key = f"mfg-api-key-{source_id}"
    await db_session.execute(
        text("""
            INSERT INTO order_sources (
                id, code, name, api_key, phone, postal_code,
                address_prefecture, address_city, is_active, created_at, updated_at
            )
            VALUES (
                :id, :code, :name, :api_key, :phone, :postal_code,
                :address_prefecture, :address_city, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": source_id,
            "code": f"MFG{source_id[:8].upper()}",
            "name": "MFG Source",
            "api_key": api_key,
            "phone": "090-1234-5678",
            "postal_code": "100-0001",
            "address_prefecture": "東京都",
            "address_city": "千代田区",
            "is_active": True,
        },
    )
    await db_session.commit()
    yield {"id": source_id, "api_key": api_key}


def _customer() -> dict:
    return {
        "name": "山田太郎",
        "postal_code": "123-4567",
        "address_prefecture": "東京都",
        "address_city": "渋谷区1-2-3",
        "phone": "03-1234-5678",
        "email": "yamada@example.com",
    }


def _keychain_item(uid: str, product_code: str, *, with_white: bool = False) -> dict:
    layers = [
        {"layer_type": "color", "url": "https://example.com/color.png"},
        {"layer_type": "cutline", "url": "https://example.com/cutline.png"},
    ]
    if with_white:
        layers.append({"layer_type": "white", "url": "https://example.com/white.png"})
    return {
        "uid": uid,
        "product_type": "acrylic_keychain",
        "product_name": "アクリルキーホルダー デザインA",
        "price": 1200,
        "quantity": 1,
        "size": "50x50mm",
        "color": "アクリル",
        "product_code": product_code,
        "source_images": layers,
        "thumbnail_image_url": "https://example.com/thumb.png",
    }


class TestV2Intake:
    @pytest.mark.asyncio
    async def test_intake_creates_order_and_links_manufacturing_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mfg_keychain_product: dict,
        mfg_order_source: dict,
    ):
        product_code = f"RKSYO-{uuid4().hex[:6]}"
        payload = {
            "order_number": "1000001",
            "customer": _customer(),
            "items": [_keychain_item("2000001", product_code)],
        }
        resp = await client.post(
            "/api/v2/orders",
            json=payload,
            headers={"X-API-Key": mfg_order_source["api_key"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["items"][0]["product_code"] == product_code

        order_id = body["id"]
        # 明細に製造データが紐付いている
        row = (
            await db_session.execute(
                text(
                    "SELECT product_code, source_images, manufacturing_data_id "
                    "FROM order_items WHERE order_id = :oid"
                ),
                {"oid": order_id},
            )
        ).fetchone()
        assert row is not None
        assert row[0] == product_code
        assert row[1] is not None  # source_images JSONB
        assert row[2] is not None  # manufacturing_data_id

        # 製造データ行が作成され、キャッシュキー（size/variant）が期待通り
        md = (
            await db_session.execute(
                text(
                    "SELECT size, variant, product_type FROM manufacturing_data "
                    "WHERE product_code = :pc AND order_source_id = :sid"
                ),
                {"pc": product_code, "sid": mfg_order_source["id"]},
            )
        ).fetchone()
        assert md is not None
        assert md[0] == "50x50mm"  # pod-admin サイズをそのまま保持
        assert md[1] == "clear"  # white レイヤーなし → clear
        assert md[2] == "acrylic_keychain"

    @pytest.mark.asyncio
    async def test_cache_reuse_across_orders_same_product_code(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mfg_keychain_product: dict,
        mfg_order_source: dict,
    ):
        product_code = f"RKSYO-{uuid4().hex[:6]}"
        headers = {"X-API-Key": mfg_order_source["api_key"]}

        resp1 = await client.post(
            "/api/v2/orders",
            json={
                "order_number": "1000010",
                "customer": _customer(),
                "items": [_keychain_item("2000010", product_code)],
            },
            headers=headers,
        )
        resp2 = await client.post(
            "/api/v2/orders",
            json={
                "order_number": "1000011",
                "customer": _customer(),
                "items": [_keychain_item("2000011", product_code)],
            },
            headers=headers,
        )
        assert resp1.status_code == 201, resp1.text
        assert resp2.status_code == 201, resp2.text

        # 同一キャッシュキー → 製造データ行は 1 件のみ
        count = (
            await db_session.execute(
                text(
                    "SELECT COUNT(*) FROM manufacturing_data "
                    "WHERE product_code = :pc AND order_source_id = :sid"
                ),
                {"pc": product_code, "sid": mfg_order_source["id"]},
            )
        ).scalar()
        assert count == 1

        # 両注文の明細が同じ manufacturing_data_id を指す
        ids = (
            await db_session.execute(
                text(
                    "SELECT DISTINCT manufacturing_data_id FROM order_items oi "
                    "JOIN orders o ON o.id = oi.order_id "
                    "WHERE o.order_number IN ('1000010', '1000011')"
                )
            )
        ).fetchall()
        assert len(ids) == 1
        assert ids[0][0] is not None

    @pytest.mark.asyncio
    async def test_order_cannot_go_manufacturing_until_ready(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mfg_keychain_product: dict,
        mfg_order_source: dict,
    ):
        product_code = f"RKSYO-{uuid4().hex[:6]}"
        resp = await client.post(
            "/api/v2/orders",
            json={
                "order_number": "1000020",
                "customer": _customer(),
                "items": [_keychain_item("2000020", product_code)],
            },
            headers={"X-API-Key": mfg_order_source["api_key"]},
        )
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        # 製造データが ready でないため、メーカー発注（manufacturing）へ遷移できない
        gate = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )
        assert gate.status_code == 409
        assert gate.json()["error"]["code"] == "MANUFACTURING_DATA_NOT_READY"

    @pytest.mark.asyncio
    async def test_bulk_status_gate_blocks_unready_v2_order(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        mfg_keychain_product: dict,
        mfg_order_source: dict,
    ):
        # 一括ステータス更新でも、未ready の v2 注文は MANUFACTURING に遷移できない
        # （単発 update_status の 409 ゲートと同一規則。一括では failed として記録しスキップ）。
        product_code = f"RKSYO-{uuid4().hex[:6]}"
        resp = await client.post(
            "/api/v2/orders",
            json={
                "order_number": "1000050",
                "customer": _customer(),
                "items": [_keychain_item("2000050", product_code)],
            },
            headers={"X-API-Key": mfg_order_source["api_key"]},
        )
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        bulk = await client.patch(
            "/api/v1/orders/bulk-status",
            json={"order_ids": [order_id], "status": "manufacturing"},
            headers=auth_headers,
        )
        assert bulk.status_code == 200, bulk.text
        body = bulk.json()
        assert body["updated_count"] == 0
        assert body["failed_count"] == 1
        assert order_id in body["failed_ids"]

        # 注文ステータスは ordered のまま（ゲートで遷移がブロックされている）
        status_value = (
            await db_session.execute(
                text("SELECT status FROM orders WHERE id = :oid"),
                {"oid": order_id},
            )
        ).scalar()
        assert status_value == "ordered"

    @pytest.mark.asyncio
    async def test_intake_rejects_item_missing_required_layer(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mfg_keychain_product: dict,
        mfg_order_source: dict,
    ):
        # acrylic_keychain は color+cutline が必須。cutline を欠くと intake で 400 拒否され、
        # 注文・製造データ行は一切作成されない（201受理→恒久保留を防ぐ）。
        product_code = f"RKSYO-{uuid4().hex[:6]}"
        payload = {
            "order_number": "1000060",
            "customer": _customer(),
            "items": [
                {
                    "uid": "2000060",
                    "product_type": "acrylic_keychain",
                    "product_name": "アクリルキーホルダー（cutline欠落）",
                    "price": 1200,
                    "quantity": 1,
                    "size": "50x50mm",
                    "color": "アクリル",
                    "product_code": product_code,
                    "source_images": [
                        {"layer_type": "color", "url": "https://example.com/color.png"}
                    ],
                    "thumbnail_image_url": "https://example.com/thumb.png",
                }
            ],
        }
        resp = await client.post(
            "/api/v2/orders",
            json=payload,
            headers={"X-API-Key": mfg_order_source["api_key"]},
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

        # 生成不能な注文は受理されない（注文・製造データ行ともに未作成）
        order_count = (
            await db_session.execute(
                text("SELECT COUNT(*) FROM orders WHERE order_number = '1000060'")
            )
        ).scalar()
        assert order_count == 0
        md_count = (
            await db_session.execute(
                text("SELECT COUNT(*) FROM manufacturing_data WHERE product_code = :pc"),
                {"pc": product_code},
            )
        ).scalar()
        assert md_count == 0


class TestV1BackwardCompatibility:
    @pytest.mark.asyncio
    async def test_v1_intake_unchanged_and_not_gated(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mfg_keychain_product: dict,
        mfg_order_source: dict,
    ):
        # v1（design_image_url 方式）は従来通り受理され、発注ゲートの対象外
        resp = await client.post(
            "/api/v1/orders",
            json={
                "order_number": "1000030",
                "customer": _customer(),
                "items": [
                    {
                        "uid": "2000030",
                        "product_type": "acrylic_keychain",
                        "product_name": "アクリルキーホルダー（v1）",
                        "price": 1200,
                        "quantity": 1,
                        "size": "50x50mm",
                        "color": "アクリル",
                        "design_image_url": "https://example.com/design1.png",
                        "thumbnail_image_url": "https://example.com/thumb1.png",
                    }
                ],
            },
            headers={"X-API-Key": mfg_order_source["api_key"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["items"][0]["product_code"] is None
        assert body["items"][0]["manufacturing_data"] is None

        order_id = body["id"]
        # v1 明細は製造データ不要 → manufacturing へ遷移可能
        gate = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )
        assert gate.status_code == 200
        assert gate.json()["status"] == "manufacturing"
