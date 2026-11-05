"""Integration tests for shipment info in the external order status API.

Issue #165: GET /api/v1/external/orders/{order_number}/status に配送情報を返す。
Tests the full flow through API -> Service -> Repository -> Database.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.shipment_search_helpers import insert_order

_INSERT_SHIPMENT = text("""
    INSERT INTO shipments (
        id, status, tracking_number, carrier, shipped_at, created_at, updated_at
    )
    VALUES (
        :id, :status, :tracking_number, :carrier, :shipped_at,
        COALESCE(CAST(:created_at AS timestamptz), NOW()), NOW()
    )
""")

_INSERT_SHIPMENT_ITEM = text("""
    INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
    VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
""")


async def _insert_shipment(
    db_session: AsyncSession,
    order_ids: list[str],
    tracking_number: str | None,
    carrier: str | None = None,
    shipped_at: datetime | None = None,
    created_at: datetime | None = None,
) -> None:
    shipment_id = str(uuid4())
    await db_session.execute(
        _INSERT_SHIPMENT,
        {
            "id": shipment_id,
            "status": "shipped" if shipped_at else "pending",
            "tracking_number": tracking_number,
            "carrier": carrier,
            "shipped_at": shipped_at,
            "created_at": created_at,
        },
    )
    for order_id in order_ids:
        await db_session.execute(
            _INSERT_SHIPMENT_ITEM,
            {"id": str(uuid4()), "shipment_id": shipment_id, "order_id": order_id},
        )


async def _new_order(
    db_session: AsyncSession, test_order_source: dict[str, Any], status: str
) -> tuple[str, str]:
    order_number = f"EXT-STATUS-{uuid4().hex[:8]}"
    order_id = await insert_order(
        db_session, test_order_source["id"], order_number, "外部ステータス確認", status
    )
    return order_id, order_number


async def _get_status(
    client: AsyncClient, test_order_source: dict[str, Any], order_number: str
) -> dict[str, Any]:
    response = await client.get(
        f"/api/v1/external/orders/{order_number}/status",
        headers={"X-API-Key": test_order_source["api_key"]},
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


class TestExternalOrderStatusShipment:
    """外部向け注文ステータス取得 API の shipment 項目."""

    async def test_shipped_order_returns_shipment(
        self, client: AsyncClient, db_session: AsyncSession, test_order_source: dict[str, Any]
    ) -> None:
        order_id, order_number = await _new_order(db_session, test_order_source, "shipped")
        shipped_at = datetime(2026, 3, 5, 6, 0, tzinfo=UTC)
        await _insert_shipment(
            db_session, [order_id], "1234-5678-9012", carrier="ヤマト運輸", shipped_at=shipped_at
        )
        await db_session.commit()

        data = await _get_status(client, test_order_source, order_number)

        assert data["order_number"] == order_number
        assert data["status"] == "shipped"
        assert data["shipment"]["carrier"] == "ヤマト運輸"
        assert data["shipment"]["tracking_number"] == "1234-5678-9012"
        assert datetime.fromisoformat(data["shipment"]["shipped_at"]) == shipped_at

    async def test_shipment_is_null_without_shipment_record(
        self, client: AsyncClient, db_session: AsyncSession, test_order_source: dict[str, Any]
    ) -> None:
        _, order_number = await _new_order(db_session, test_order_source, "manufacturing")
        await db_session.commit()

        data = await _get_status(client, test_order_source, order_number)

        assert data["status"] == "manufacturing"
        assert "shipment" in data
        assert data["shipment"] is None

    async def test_shipment_is_null_without_tracking_number(
        self, client: AsyncClient, db_session: AsyncSession, test_order_source: dict[str, Any]
    ) -> None:
        order_id, order_number = await _new_order(db_session, test_order_source, "delivered")
        await _insert_shipment(db_session, [order_id], None)
        await db_session.commit()

        data = await _get_status(client, test_order_source, order_number)

        assert data["status"] == "delivered"
        assert data["shipment"] is None

    @pytest.mark.parametrize("tracking_number", ["", "  "])
    async def test_shipment_is_null_with_blank_tracking_number(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_order_source: dict[str, Any],
        tracking_number: str,
    ) -> None:
        order_id, order_number = await _new_order(db_session, test_order_source, "delivered")
        await _insert_shipment(db_session, [order_id], tracking_number)
        await db_session.commit()

        data = await _get_status(client, test_order_source, order_number)

        assert data["shipment"] is None

    async def test_tracking_number_before_shipping(
        self, client: AsyncClient, db_session: AsyncSession, test_order_source: dict[str, Any]
    ) -> None:
        """伝票番号だけ先に登録された（未発送の）配送は shipped_at が null で返る."""
        order_id, order_number = await _new_order(db_session, test_order_source, "delivered")
        await _insert_shipment(db_session, [order_id], "9999-0000-1111")
        await db_session.commit()

        data = await _get_status(client, test_order_source, order_number)

        assert data["status"] == "delivered"
        assert data["shipment"] == {
            "carrier": None,
            "tracking_number": "9999-0000-1111",
            "shipped_at": None,
        }

    async def test_bundled_orders_share_shipment(
        self, client: AsyncClient, db_session: AsyncSession, test_order_source: dict[str, Any]
    ) -> None:
        """同梱（1 配送に複数注文）では、どの注文から引いても同じ配送情報が返る."""
        order_a, number_a = await _new_order(db_session, test_order_source, "shipped")
        order_b, number_b = await _new_order(db_session, test_order_source, "shipped")
        await _insert_shipment(
            db_session,
            [order_a, order_b],
            "5555-6666-7777",
            carrier="佐川急便",
            shipped_at=datetime(2026, 3, 5, 6, 0, tzinfo=UTC),
        )
        await db_session.commit()

        data_a = await _get_status(client, test_order_source, number_a)
        data_b = await _get_status(client, test_order_source, number_b)

        assert data_a["shipment"] == data_b["shipment"]
        assert data_a["shipment"]["tracking_number"] == "5555-6666-7777"

    async def test_multiple_shipments_pick_latest_shipped_tracked_one(
        self, client: AsyncClient, db_session: AsyncSession, test_order_source: dict[str, Any]
    ) -> None:
        """1 注文に配送が複数あるときは、伝票番号ありのうち発送日時が新しいものを返す."""
        order_id, order_number = await _new_order(db_session, test_order_source, "shipped")
        await _insert_shipment(
            db_session,
            [order_id],
            "OLD-0001",
            shipped_at=datetime(2026, 3, 1, 6, 0, tzinfo=UTC),
        )
        await _insert_shipment(
            db_session,
            [order_id],
            "NEW-0002",
            shipped_at=datetime(2026, 3, 5, 6, 0, tzinfo=UTC),
            created_at=datetime(2026, 2, 1, 0, 0, tzinfo=UTC),
        )
        # 未発送のものは発送済みより後ろ、伝票番号なしは対象外
        await _insert_shipment(db_session, [order_id], "UNSHIPPED-0003")
        await _insert_shipment(db_session, [order_id], None)
        await db_session.commit()

        data = await _get_status(client, test_order_source, order_number)

        assert data["shipment"]["tracking_number"] == "NEW-0002"
