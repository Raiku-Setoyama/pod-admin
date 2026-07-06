"""Integration test for POST /api/v2/orders (v2 intake + manufacturing_data auto-create)."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturer import Manufacturer
from app.models.order_source import OrderSource
from app.models.product import Product


def _digits7() -> str:
    return str(uuid4().int % 10_000_000).zfill(7)


@pytest.fixture
async def v2_setup(db_session: AsyncSession):
    """acrylic_keychain の商品マスタ＋API Key付き受注元を用意する。

    products は (product_type, size, position, color) に一意制約があり、DBは追加的
    （テスト間でクリーンアップしない）ため、既存の acrylic_keychain 商品があれば再利用する。
    """
    existing_product = (
        await db_session.execute(
            text("SELECT id FROM products WHERE product_type = 'acrylic_keychain' LIMIT 1")
        )
    ).fetchone()
    if existing_product is None:
        manufacturer = Manufacturer(
            name=f"MFR {uuid4().hex[:8]}",
            email=f"mfr-{uuid4().hex[:8]}@example.com",
            supported_products=["acrylic_keychain"],
            unit_prices={},
            lead_time_days=3,
            daily_order_limit=100,
            sharing_method="portal",
            is_active=True,
        )
        db_session.add(manufacturer)
        await db_session.flush()
        db_session.add(
            Product(
                product_type="acrylic_keychain",
                size="50x50mm",
                manufacturer_id=manufacturer.id,
                cost=500,
                lead_time_days=3,
                is_active=True,
            )
        )

    api_key = f"v2-key-{uuid4().hex}"
    source = OrderSource(
        code=f"V2SRC{uuid4().hex[:8].upper()}",
        api_key=api_key,
        name="V2 Source",
        phone="090-1111-2222",
        postal_code="100-0001",
        address_prefecture="東京都",
        address_city="千代田区",
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()
    return {"api_key": api_key}


class TestV2Intake:
    @pytest.mark.asyncio
    async def test_v2_order_persists_fields_and_creates_manufacturing_data(
        self, client, db_session: AsyncSession, v2_setup: dict
    ):
        order_number = _digits7()
        payload = {
            "order_number": order_number,
            "customer": {
                "name": "山田太郎",
                "postal_code": "100-0001",
                "address_prefecture": "東京都",
                "address_city": "千代田区1-1",
                "phone": "090-0000-0000",
            },
            "items": [
                {
                    "uid": _digits7(),
                    "product_type": "acrylic_keychain",
                    "product_name": "キーホルダー",
                    "price": 1200,
                    "quantity": 2,
                    "size": "50x50mm",
                    "variant": "clear",
                    "product_code": f"PC-{uuid4().hex[:8]}",
                    "source_images": [
                        {"layer_type": "color", "url": "http://example.com/c.png"},
                        {"layer_type": "cutline", "url": "http://example.com/l.png"},
                    ],
                }
            ],
        }
        resp = await client.post(
            "/api/v2/orders", json=payload, headers={"X-API-Key": v2_setup["api_key"]}
        )
        assert resp.status_code == 201, resp.text
        order_id = resp.json()["id"]

        # OrderItem に v2 フィールドが永続化されている
        row = (
            await db_session.execute(
                text(
                    "SELECT product_code, variant, source_images, manufacturing_data_id "
                    "FROM order_items WHERE order_id = :oid"
                ),
                {"oid": order_id},
            )
        ).fetchone()
        assert row is not None
        assert row.product_code.startswith("PC-")
        assert row.variant == "clear"
        assert isinstance(row.source_images, list) and len(row.source_images) == 2

        # 受付後の BackgroundTasks で manufacturing_data(pending) が作成・紐付けされている
        assert row.manufacturing_data_id is not None
        md = (
            await db_session.execute(
                text("SELECT status FROM manufacturing_data WHERE id = :id"),
                {"id": row.manufacturing_data_id},
            )
        ).fetchone()
        assert md is not None
        # ILLUSTRATOR_VM_URL 未設定なので生成は走らず pending のまま
        assert md.status == "pending"

    @pytest.mark.asyncio
    async def test_v2_order_missing_variant_rejected(self, client, v2_setup: dict):
        payload = {
            "order_number": _digits7(),
            "customer": {
                "name": "山田太郎",
                "postal_code": "100-0001",
                "address_prefecture": "東京都",
                "address_city": "千代田区1-1",
                "phone": "090-0000-0000",
            },
            "items": [
                {
                    "uid": _digits7(),
                    "product_type": "acrylic_keychain",
                    "product_name": "キーホルダー",
                    "price": 1200,
                    "quantity": 1,
                    "size": "50x50mm",
                    # variant 未指定 → keychain は必須 → 400
                    "product_code": f"PC-{uuid4().hex[:8]}",
                    "source_images": [
                        {"layer_type": "color", "url": "http://example.com/c.png"},
                        {"layer_type": "cutline", "url": "http://example.com/l.png"},
                    ],
                }
            ],
        }
        resp = await client.post(
            "/api/v2/orders", json=payload, headers={"X-API-Key": v2_setup["api_key"]}
        )
        assert resp.status_code == 400, resp.text
