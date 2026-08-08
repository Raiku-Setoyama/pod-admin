"""BUG-0001: 配送一覧のキーワード検索が、どんな入力でも 0 件になる.

再現手順（BUG-0001 の `## 再現手順`）をテストにしたもの。

- 実配送は 伝票番号 / 配送ID（先頭 8 桁）/ 宛先の氏名 のいずれでも引けること
- 準備中注文（pending_order）も同じ検索語で絞り込まれること
- 一致するものが無いときだけ 0 件になること（API が 500 を返さないこと）
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
async def search_data(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """検索対象の実配送 1 件と、準備中注文 2 件（一致する／しない）を作る.

    他テストのデータと混ざらないよう、すべての値に一意のトークンを埋め込む。
    """
    token = uuid4().hex[:8].upper()
    source_id = test_order_source["id"]

    shipped_order_id = await insert_order(
        db_session, source_id, f"SRCHS-{token}", f"SRCH{token} 山田太郎", "delivered"
    )
    tracking_number = f"TRK{token}0001"
    shipment_id = await insert_shipment(db_session, [shipped_order_id], tracking_number)

    matching_pending_id = await insert_order(
        db_session, source_id, f"SRCHP-{token}", f"SRCH{token} 鈴木花子", "manufacturing"
    )
    other_pending_id = await insert_order(
        db_session, source_id, f"OTHRP-{token}", f"OTHER{token} 佐藤次郎", "manufacturing"
    )

    await db_session.commit()

    yield {
        "token": token,
        "shipment_id": shipment_id,
        "tracking_number": tracking_number,
        "shipped_order_id": shipped_order_id,
        "shipped_customer_name": f"SRCH{token} 山田太郎",
        "matching_pending_id": matching_pending_id,
        "other_pending_id": other_pending_id,
    }


class TestShipmentSearch:
    """BUG-0001 の受入基準に対応する回帰テスト."""

    async def test_search_by_tracking_number_returns_shipment(
        self, client: AsyncClient, auth_headers: dict[str, Any], search_data: dict[str, Any]
    ) -> None:
        """伝票番号をそのまま入力すると、その実配送が結果に出る."""
        data = await search_shipments(client, auth_headers, search_data["tracking_number"])

        assert search_data["shipment_id"] in shipment_ids(data)

    async def test_search_by_shipment_id_prefix_returns_shipment(
        self, client: AsyncClient, auth_headers: dict[str, Any], search_data: dict[str, Any]
    ) -> None:
        """一覧に表示される配送 ID の先頭 8 桁で、その実配送が結果に出る.

        `Shipment.id` は PostgreSQL の uuid 型なので、文字列として ILIKE を
        掛けると `operator does not exist: uuid ~~* unknown` で落ちる。
        """
        prefix = search_data["shipment_id"][:8]

        data = await search_shipments(client, auth_headers, prefix)

        assert search_data["shipment_id"] in shipment_ids(data)

    async def test_search_by_customer_name_returns_shipment(
        self, client: AsyncClient, auth_headers: dict[str, Any], search_data: dict[str, Any]
    ) -> None:
        """宛先の氏名で、その実配送が結果に出る."""
        data = await search_shipments(client, auth_headers, search_data["shipped_customer_name"])

        assert search_data["shipment_id"] in shipment_ids(data)

    async def test_search_filters_pending_orders_by_customer_name(
        self, client: AsyncClient, auth_headers: dict[str, Any], search_data: dict[str, Any]
    ) -> None:
        """準備中注文も同じ検索語で絞り込まれる."""
        token = search_data["token"]

        data = await search_shipments(client, auth_headers, f"SRCH{token} 鈴木")

        pending_ids = pending_order_ids(data)
        assert search_data["matching_pending_id"] in pending_ids
        assert search_data["other_pending_id"] not in pending_ids

    async def test_search_by_tracking_number_excludes_unrelated_pending_orders(
        self, client: AsyncClient, auth_headers: dict[str, Any], search_data: dict[str, Any]
    ) -> None:
        """伝票番号で検索したとき、一致しない準備中注文が混ざらない."""
        data = await search_shipments(client, auth_headers, search_data["tracking_number"])

        pending_ids = pending_order_ids(data)
        assert search_data["matching_pending_id"] not in pending_ids
        assert search_data["other_pending_id"] not in pending_ids

    async def test_search_without_match_returns_empty(
        self, client: AsyncClient, auth_headers: dict[str, Any], search_data: dict[str, Any]
    ) -> None:
        """一致するものが無いときだけ 0 件になる（500 を返さない）."""
        data = await search_shipments(client, auth_headers, f"NOMATCH-{uuid4().hex}")

        assert data["items"] == []
        assert data["total"] == 0

    async def test_search_single_character_does_not_error(
        self, client: AsyncClient, auth_headers: dict[str, Any], search_data: dict[str, Any]
    ) -> None:
        """1 文字だけ入力しても API がエラーにならない（必ず 0 件にならない）."""
        data = await search_shipments(client, auth_headers, search_data["token"][0])

        assert isinstance(data["items"], list)
