"""Integration tests for v2 order intake and manufacturing-data generation.

外部注文 v2（POST /api/v2/orders）の受付・製造データ紐付け・キャッシュ再利用・発注ゲートを
API -> Service -> Repository -> DB の一連の流れで検証する。

illustrator-vm は未設定（テスト環境）のため、バックグラウンド生成は最終的に failed になる。
本テストは「同期的に確定する状態（行の作成・紐付け・キャッシュキー・発注ゲート）」のみを検証し、
非同期生成の最終状態には依存しない。
"""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def mfg_manufacturer(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
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
async def mfg_keychain_product(db_session: AsyncSession, mfg_manufacturer: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
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
async def mfg_order_source(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
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


def _customer() -> dict[str, Any]:
    return {
        "name": "山田太郎",
        "postal_code": "123-4567",
        "address_prefecture": "東京都",
        "address_city": "渋谷区1-2-3",
        "phone": "03-1234-5678",
        "email": "yamada@example.com",
    }


def _keychain_item(uid: str, product_code: str, *, with_white: bool = False) -> dict[str, Any]:
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
        mfg_keychain_product: dict[str, Any],
        mfg_order_source: dict[str, Any],
    ) -> None:
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
                    "SELECT size, variant, product_type, status FROM manufacturing_data "
                    "WHERE product_code = :pc AND order_source_id = :sid"
                ),
                {"pc": product_code, "sid": mfg_order_source["id"]},
            )
        ).fetchone()
        assert md is not None
        assert md[0] == "50x50mm"  # pod-admin サイズをそのまま保持
        # 受付は行を作るだけで、生成には入らない（生成はワーカーが拾う。ADR-0026）。
        # レスポンスを返す前後に生成が走っていれば、外部VM未設定のこの環境では
        # failed になっているはずなので、pending のままであることが証拠になる。
        assert md[3] == "pending"
        assert md[1] == "clear"  # white レイヤーなし → clear
        assert md[2] == "acrylic_keychain"

    @pytest.mark.asyncio
    async def test_cache_reuse_across_orders_same_product_code(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mfg_keychain_product: dict[str, Any],
        mfg_order_source: dict[str, Any],
    ) -> None:
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
        auth_headers: dict[str, Any],
        mfg_keychain_product: dict[str, Any],
        mfg_order_source: dict[str, Any],
    ) -> None:
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
        auth_headers: dict[str, Any],
        db_session: AsyncSession,
        mfg_keychain_product: dict[str, Any],
        mfg_order_source: dict[str, Any],
    ) -> None:
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

        # 統合ステータスでは未 ready の v2 注文は「発注準備中(preparing_order)」に導出される。
        # 前進遷移（→manufacturing）はゲートでブロックされたまま。
        status_value = (
            await db_session.execute(
                text("SELECT status FROM orders WHERE id = :oid"),
                {"oid": order_id},
            )
        ).scalar()
        assert status_value == "preparing_order"

    @pytest.mark.asyncio
    async def test_intake_rejects_item_missing_required_layer(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mfg_keychain_product: dict[str, Any],
        mfg_order_source: dict[str, Any],
    ) -> None:
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

    @pytest.mark.asyncio
    async def test_reaffirming_manufacturing_is_not_gated(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        db_session: AsyncSession,
        mfg_keychain_product: dict[str, Any],
        mfg_order_source: dict[str, Any],
    ) -> None:
        # メーカーが明細単位で一部を製造中にした結果、注文が既に MANUFACTURING の場合、
        # 未ready明細が残っていても「manufacturing のまま」への再確定は 409 にならない
        # （注文レベルゲートと明細レベルゲートの不整合を避ける = 前進遷移でのみゲート）。
        product_code = f"RKSYO-{uuid4().hex[:6]}"
        resp = await client.post(
            "/api/v2/orders",
            json={
                "order_number": "1000070",
                "customer": _customer(),
                "items": [_keychain_item("2000070", product_code)],
            },
            headers={"X-API-Key": mfg_order_source["api_key"]},
        )
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        # 明細単位フロー経由で到達しうる manufacturing 状態を直接再現する
        await db_session.execute(
            text("UPDATE orders SET status = 'manufacturing' WHERE id = :oid"),
            {"oid": order_id},
        )
        await db_session.commit()

        # 既に manufacturing の注文を manufacturing に再確定 → 未ready明細があっても 409 にしない
        resp2 = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "manufacturing"},
            headers=auth_headers,
        )
        assert resp2.status_code == 200, resp2.text


class TestV1BackwardCompatibility:
    @pytest.mark.asyncio
    async def test_v1_intake_unchanged_and_not_gated(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        mfg_keychain_product: dict[str, Any],
        mfg_order_source: dict[str, Any],
    ) -> None:
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


class TestRegenerateEndpoint:
    """製造データ GUI 再作成（POST /manufacturing-data/{id}/regenerate）のE2E."""

    @pytest.mark.asyncio
    async def test_regenerate_demotes_shared_items_and_blocks_when_manufacturing(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        db_session: AsyncSession,
        mfg_keychain_product: dict[str, Any],
        mfg_order_source: dict[str, Any],
    ) -> None:
        # 同一 product_code の v2 注文を2件作成 → 同一製造データ行を共有する。
        product_code = f"RKSYO-{uuid4().hex[:6]}"
        headers = {"X-API-Key": mfg_order_source["api_key"]}
        r1 = await client.post(
            "/api/v2/orders",
            json={
                "order_number": "1000080",
                "customer": _customer(),
                "items": [_keychain_item("2000080", product_code)],
            },
            headers=headers,
        )
        r2 = await client.post(
            "/api/v2/orders",
            json={
                "order_number": "1000081",
                "customer": _customer(),
                "items": [_keychain_item("2000081", product_code)],
            },
            headers=headers,
        )
        assert r1.status_code == 201, r1.text
        assert r2.status_code == 201, r2.text
        order1_id = r1.json()["id"]
        order2_id = r2.json()["id"]

        md_id = (
            await db_session.execute(
                text(
                    "SELECT id FROM manufacturing_data "
                    "WHERE product_code = :pc AND order_source_id = :sid"
                ),
                {"pc": product_code, "sid": mfg_order_source["id"]},
            )
        ).scalar()
        assert md_id is not None

        # 生成完了を模擬: 製造データ ready + 両注文の明細/注文を発注済みへ。
        await db_session.execute(
            text(
                "UPDATE manufacturing_data SET status = 'ready', "
                "file_path = 'manufacturing_data/x.ai' WHERE id = :id"
            ),
            {"id": md_id},
        )
        await db_session.execute(
            text("UPDATE order_items SET status = 'ordered' WHERE manufacturing_data_id = :id"),
            {"id": md_id},
        )
        await db_session.execute(
            text("UPDATE orders SET status = 'ordered' WHERE id IN (:o1, :o2)"),
            {"o1": order1_id, "o2": order2_id},
        )
        await db_session.commit()

        # ケースA: 全共有が発注前 → 再作成OK。md は pending に戻り、明細/注文は発注準備中へ demote。
        ok = await client.post(
            f"/api/v1/manufacturing-data/{md_id}/regenerate", headers=auth_headers
        )
        assert ok.status_code == 200, ok.text

        # 再作成で ready から巻き戻る（enqueue された背景生成は VM 未設定のため最終的に
        # failed になりうる。ここで重要なのは ready でなくなり再生成が起動したこと）。
        md_status = (
            await db_session.execute(
                text("SELECT status FROM manufacturing_data WHERE id = :id"), {"id": md_id}
            )
        ).scalar()
        assert md_status != "ready"
        item_statuses = (
            await db_session.execute(
                text("SELECT status FROM order_items WHERE manufacturing_data_id = :id"),
                {"id": md_id},
            )
        ).scalars().all()
        assert set(item_statuses) == {"preparing_order"}
        order_statuses = (
            await db_session.execute(
                text("SELECT status FROM orders WHERE id IN (:o1, :o2)"),
                {"o1": order1_id, "o2": order2_id},
            )
        ).scalars().all()
        assert set(order_statuses) == {"preparing_order"}

        # ケースB: 片方の注文を製造中に進め、製造データを ready に戻す → 共有に製造中があるため 409。
        await db_session.execute(
            text("UPDATE manufacturing_data SET status = 'ready' WHERE id = :id"), {"id": md_id}
        )
        await db_session.execute(
            text("UPDATE order_items SET status = 'manufacturing' WHERE order_id = :oid"),
            {"oid": order1_id},
        )
        await db_session.execute(
            text("UPDATE order_items SET status = 'ordered' WHERE order_id = :oid"),
            {"oid": order2_id},
        )
        await db_session.commit()

        blocked = await client.post(
            f"/api/v1/manufacturing-data/{md_id}/regenerate", headers=auth_headers
        )
        assert blocked.status_code == 409, blocked.text
        # 製造データは ready のまま（保護のため巻き戻さない）。
        md_status2 = (
            await db_session.execute(
                text("SELECT status FROM manufacturing_data WHERE id = :id"), {"id": md_id}
            )
        ).scalar()
        assert md_status2 == "ready"
