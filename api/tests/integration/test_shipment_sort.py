"""REQ-0049: 配送一覧を作成日・配送予定日・ステータス・注文番号・宛先で並び替える.

並び替えは実配送（shipment）にのみ効かせ、準備中注文（pending_order）は
従来どおり受注日の降順で並ぶ（ADR-0025 の決定）。

対象データだけを見るため、各テストは一意のトークンで検索して結果を絞り込む
（検索は注文番号・宛先名に部分一致する。BUG-0001 / REQ-0048）。
"""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.shipment_search_helpers import (
    insert_order,
    insert_shipment,
    list_shipments,
    ordered_pending_order_ids,
    ordered_shipment_ids,
)


@pytest.fixture
async def sort_data(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """並び替えの向きが列ごとに変わるよう、値をわざとばらした実配送 3 件を作る.

    | | 作成日 | 配送予定日 | ステータス | 注文番号 | 宛先 |
    |---|---|---|---|---|---|
    | A | 最古 | 09-05 | ready | R49A | AAA |
    | B | 中間 | 09-01 | shipped | R49B | CCC |
    | C | 最新 | 未設定 | pending | R49C | BBB |

    準備中注文は受注日の降順（P2 → P1）になることの確認用に 2 件。
    """
    token = uuid4().hex[:8].upper()
    source_id = test_order_source["id"]

    order_a = await insert_order(
        db_session, source_id, f"R49A-{token}", f"{token}-AAA", "delivered", date(2026, 9, 5)
    )
    order_b = await insert_order(
        db_session, source_id, f"R49B-{token}", f"{token}-CCC", "delivered", date(2026, 9, 1)
    )
    order_c = await insert_order(
        db_session, source_id, f"R49C-{token}", f"{token}-BBB", "delivered", None
    )

    shipment_a = await insert_shipment(
        db_session, [order_a], status="ready", created_at=datetime(2026, 8, 1, tzinfo=UTC)
    )
    shipment_b = await insert_shipment(
        db_session, [order_b], status="shipped", created_at=datetime(2026, 8, 2, tzinfo=UTC)
    )
    shipment_c = await insert_shipment(
        db_session, [order_c], status="pending", created_at=datetime(2026, 8, 3, tzinfo=UTC)
    )

    pending_1 = await insert_order(
        db_session,
        source_id,
        f"R49P1-{token}",
        f"{token}-PENDING1",
        "manufacturing",
        ordered_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    pending_2 = await insert_order(
        db_session,
        source_id,
        f"R49P2-{token}",
        f"{token}-PENDING2",
        "manufacturing",
        ordered_at=datetime(2026, 8, 5, tzinfo=UTC),
    )

    await db_session.commit()

    yield {
        "token": token,
        "a": shipment_a,
        "b": shipment_b,
        "c": shipment_c,
        "pending_1": pending_1,
        "pending_2": pending_2,
    }


@pytest.fixture
async def multi_order_sort_data(
    db_session: AsyncSession, test_order_source: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """複数の注文をまとめた実配送が、最小値を代表として並ぶかを見るためのデータ.

    `multi` は最小 (M1 / 09-02) と最大 (M9 / 09-30) の幅を持ち、
    `single` (M5 / 09-15) がその間に入る。最大値で並べると順序が入れ替わる。
    """
    token = uuid4().hex[:8].upper()
    source_id = test_order_source["id"]

    order_min = await insert_order(
        db_session, source_id, f"R49M1-{token}", f"{token}-MULTI-MIN", "delivered", date(2026, 9, 2)
    )
    order_max = await insert_order(
        db_session, source_id, f"R49M9-{token}", f"{token}-MULTI-MAX", "delivered", date(2026, 9, 30)
    )
    order_single = await insert_order(
        db_session, source_id, f"R49M5-{token}", f"{token}-SINGLE", "delivered", date(2026, 9, 15)
    )

    multi = await insert_shipment(db_session, [order_min, order_max])
    single = await insert_shipment(db_session, [order_single])

    await db_session.commit()

    yield {"token": token, "multi": multi, "single": single}


class TestShipmentSortColumns:
    """作成日・配送予定日・ステータス・注文番号・宛先で昇順／降順に並び替えられる."""

    @pytest.mark.parametrize(
        ("sort_by", "expected_asc"),
        [
            ("created_at", ("a", "b", "c")),
            ("order_number", ("a", "b", "c")),
            ("customer_name", ("a", "c", "b")),
            ("estimated_shipping_date", ("b", "a", "c")),
        ],
    )
    async def test_sort_asc_and_desc(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        sort_data: dict[str, Any],
        sort_by: str,
        expected_asc: tuple[str, ...],
    ) -> None:
        """昇順で期待どおりに並び、降順はその逆順になる.

        配送予定日が未設定の C は、昇順・降順のいずれでも末尾に置く。
        """
        expected_ids = [sort_data[key] for key in expected_asc]

        asc = await list_shipments(
            client,
            auth_headers,
            search=sort_data["token"],
            sort_by=sort_by,
            sort_order="asc",
        )
        desc = await list_shipments(
            client,
            auth_headers,
            search=sort_data["token"],
            sort_by=sort_by,
            sort_order="desc",
        )

        assert ordered_shipment_ids(asc) == expected_ids
        if sort_by == "estimated_shipping_date":
            # 未設定は降順でも末尾（A → B の逆順のあとに C）
            assert ordered_shipment_ids(desc) == [sort_data[k] for k in ("a", "b", "c")]
        else:
            assert ordered_shipment_ids(desc) == list(reversed(expected_ids))

    async def test_sort_by_status_follows_business_order(
        self, client: AsyncClient, auth_headers: dict[str, Any], sort_data: dict[str, Any]
    ) -> None:
        """ステータスの並びは業務上の進行順（pending → ready → shipped）になる.

        値の文字列は辞書順でも同じ並びになるため、ここでは観測できる並びだけを固定する。
        「辞書順ではなく CASE で並べている」ことは
        `tests/unit/test_shipment_sort_columns.py` が見る。
        """
        asc = await list_shipments(
            client,
            auth_headers,
            search=sort_data["token"],
            sort_by="status",
            sort_order="asc",
        )
        desc = await list_shipments(
            client,
            auth_headers,
            search=sort_data["token"],
            sort_by="status",
            sort_order="desc",
        )

        # C=pending（配送準備待ち） → A=ready（配送準備完了） → B=shipped（発送完了）
        assert ordered_shipment_ids(asc) == [sort_data[k] for k in ("c", "a", "b")]
        assert ordered_shipment_ids(desc) == [sort_data[k] for k in ("b", "a", "c")]

    async def test_default_sort_is_created_at_desc(
        self, client: AsyncClient, auth_headers: dict[str, Any], sort_data: dict[str, Any]
    ) -> None:
        """並び替えを指定しないとき、作成日の降順で並ぶ."""
        data = await list_shipments(client, auth_headers, search=sort_data["token"])

        assert ordered_shipment_ids(data) == [sort_data[k] for k in ("c", "b", "a")]


class TestShipmentSortScope:
    """並び替えの適用範囲（ADR-0025 の決定）."""

    async def test_pending_orders_keep_ordered_at_desc(
        self, client: AsyncClient, auth_headers: dict[str, Any], sort_data: dict[str, Any]
    ) -> None:
        """実配送を昇順に並べても、準備中注文は受注日の降順のままである."""
        data = await list_shipments(
            client,
            auth_headers,
            search=sort_data["token"],
            sort_by="order_number",
            sort_order="asc",
        )

        assert ordered_pending_order_ids(data) == [
            sort_data["pending_2"],
            sort_data["pending_1"],
        ]

    async def test_shipments_come_before_pending_orders(
        self, client: AsyncClient, auth_headers: dict[str, Any], sort_data: dict[str, Any]
    ) -> None:
        """1 ページの中では「並び替えた実配送」→「受注日降順の準備中注文」の順に並ぶ."""
        data = await list_shipments(client, auth_headers, search=sort_data["token"])

        types = [item["type"] for item in data["items"]]
        assert types == ["shipment"] * 3 + ["pending_order"] * 2


class TestShipmentSortPagination:
    """ページを送っても選択した並び順が維持される."""

    async def test_sort_is_kept_across_pages(
        self, client: AsyncClient, auth_headers: dict[str, Any], sort_data: dict[str, Any]
    ) -> None:
        """1 件ずつページを送ると、通しで並び替えた順に 1 件ずつ返る."""
        expected = [sort_data[k] for k in ("a", "b", "c")]

        collected = []
        for page in (1, 2, 3):
            data = await list_shipments(
                client,
                auth_headers,
                search=sort_data["token"],
                sort_by="order_number",
                sort_order="asc",
                page=page,
                limit=1,
            )
            collected.extend(ordered_shipment_ids(data))

        assert collected == expected


class TestShipmentSortMultiOrderShipment:
    """複数の注文を含む実配送は、注文番号・配送予定日とも最小値を代表として並ぶ."""

    @pytest.mark.parametrize("sort_by", ["order_number", "estimated_shipping_date"])
    async def test_multi_order_shipment_sorts_by_minimum(
        self,
        client: AsyncClient,
        auth_headers: dict[str, Any],
        multi_order_sort_data: dict[str, Any],
        sort_by: str,
    ) -> None:
        """最小値（M1 / 09-02）で並ぶので、単一注文（M5 / 09-15）より前に来る."""
        data = await list_shipments(
            client,
            auth_headers,
            search=multi_order_sort_data["token"],
            sort_by=sort_by,
            sort_order="asc",
        )

        assert ordered_shipment_ids(data) == [
            multi_order_sort_data["multi"],
            multi_order_sort_data["single"],
        ]
