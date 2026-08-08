"""REQ-0048: 配送一覧の検索で注文番号も検索できる.

配送の問い合わせは注文番号を起点に来るため、`GET /shipments` の `search` は
注文番号（`orders.order_number`）も対象にする。

- 実配送（shipment）は `ShipmentItem` 経由で紐づく注文の注文番号で引ける
- 準備中注文（pending_order）は自身の注文番号で引ける
- 複数の注文をまとめた実配送は、含まれるどの注文番号でも引ける
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.shipment_search_helpers import (
    insert_order,
    insert_shipment,
    pending_order_ids,
    search_shipments,
    shipment_ids,
)


@pytest.fixture
async def order_number_data(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """2 つの注文をまとめた実配送 1 件と、準備中注文 1 件を作る."""
    token = uuid4().hex[:8].upper()
    source_id = test_order_source["id"]

    first_order_number = f"R48A-{token}"
    second_order_number = f"R48B-{token}"
    first_order_id = await insert_order(
        db_session, source_id, first_order_number, f"R48{token} 宛先1", "delivered"
    )
    second_order_id = await insert_order(
        db_session, source_id, second_order_number, f"R48{token} 宛先2", "delivered"
    )
    shipment_id = await insert_shipment(db_session, [first_order_id, second_order_id])

    pending_order_number = f"R48P-{token}"
    pending_order_id = await insert_order(
        db_session, source_id, pending_order_number, f"R48{token} 準備中", "manufacturing"
    )

    await db_session.commit()

    yield {
        "token": token,
        "shipment_id": shipment_id,
        "first_order_number": first_order_number,
        "second_order_number": second_order_number,
        "pending_order_id": pending_order_id,
        "pending_order_number": pending_order_number,
    }


class TestShipmentSearchByOrderNumber:
    """REQ-0048 の受入基準に対応するテスト."""

    async def test_search_by_order_number_returns_shipment(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        order_number_data: dict[str, Any],
    ) -> None:
        """注文番号を入力すると、その注文を含む実配送が結果に出る."""
        data = await search_shipments(
            client, auth_headers, order_number_data["first_order_number"]
        )

        assert order_number_data["shipment_id"] in shipment_ids(data)

    async def test_search_by_order_number_returns_pending_order(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        order_number_data: dict[str, Any],
    ) -> None:
        """注文番号で、準備中注文も結果に出る."""
        data = await search_shipments(
            client, auth_headers, order_number_data["pending_order_number"]
        )

        assert order_number_data["pending_order_id"] in pending_order_ids(data)

    async def test_multi_order_shipment_is_found_by_each_order_number(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        order_number_data: dict[str, Any],
    ) -> None:
        """複数の注文をまとめた実配送を、含まれるどの注文番号でも検索できる."""
        for key in ("first_order_number", "second_order_number"):
            data = await search_shipments(client, auth_headers, order_number_data[key])

            assert order_number_data["shipment_id"] in shipment_ids(data), key
