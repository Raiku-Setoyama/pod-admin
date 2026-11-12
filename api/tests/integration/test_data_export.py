"""データ出力 API（GET /data-export/columns, POST /data-export/csv）の統合テスト.

REQ-0047 / Issue #172。実際の DB に受注・明細・配送・商品マスタ・メーカーを作り、
API → サービス → リポジトリ → DB を通して出力される CSV を確かめる。

テスト間で DB を掃除しないため、データはテストごとに一意なトークンを注文番号と顧客名に
含め、キーワード絞り込みでそのテストのデータだけを対象にする。
"""

import csv
import io
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturer import Manufacturer
from app.models.order import Order, OrderItem
from app.models.order_source import OrderSource
from app.models.product import Product
from app.models.shipment import Shipment, ShipmentItem

CSV_URL = "/api/v1/data-export/csv"
PREVIEW_URL = "/api/v1/data-export/preview"


def _parse(csv_bytes: bytes) -> list[list[str]]:
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    return list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))


@pytest.fixture
async def dataset(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
    """受注 2 件（明細 3 件）。1 件目は配送あり・明細 2 件（Tシャツとステッカー）."""
    token = uuid4().hex[:10]
    source = OrderSource(
        code=f"DX{token}",
        name="配送元テスト",
        api_key=f"dx-key-{token}",
        phone="03-0000-0000",
        postal_code="100-0001",
        address_prefecture="東京都",
        address_city="千代田区1-1",
    )
    manufacturer = Manufacturer(
        name=f"データ出力メーカー {token}",
        email="dx-mfg@example.com",
        phone="03-1111-1111",
        supported_products=["tshirt", "sticker"],
        unit_prices={},
        lead_time_days=5,
        daily_order_limit=100,
    )
    db_session.add_all([source, manufacturer])
    await db_session.flush()

    tshirt = Product(
        product_type="tshirt", size="M", position=f"DX{token}", color="白",
        manufacturer_id=manufacturer.id, cost=1200, lead_time_days=5,
    )
    sticker = Product(
        product_type="sticker", size="50x50mm", position=f"DX{token}", color=None,
        manufacturer_id=manufacturer.id, cost=100, lead_time_days=3,
    )
    db_session.add_all([tshirt, sticker])
    await db_session.flush()

    def customer(name: str) -> dict[str, Any]:
        return {
            "customer_name": name,
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "150-0001",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "渋谷区1-2-3",
            "customer_address_building": "テストビル101",
        }

    order1 = Order(
        order_number=f"DX1-{token}",
        status="delivered",
        order_source_id=source.id,
        total_price=3500,
        estimated_shipping_date=date(2026, 11, 20),
        ordered_at=datetime(2026, 11, 1, 3, 0, tzinfo=UTC),
        **customer(f"山田 {token}"),
    )
    order2 = Order(
        order_number=f"DX2-{token}",
        status="ordered",
        order_source_id=source.id,
        total_price=1000,
        estimated_shipping_date=date(2026, 12, 5),
        ordered_at=datetime(2026, 11, 10, 3, 0, tzinfo=UTC),
        **customer(f"佐藤 {token}"),
    )
    db_session.add_all([order1, order2])
    await db_session.flush()

    db_session.add_all(
        [
            OrderItem(
                order_id=order1.id, uid="1000001", product_id=tshirt.id,
                product_name="Tシャツ A", product_type="tshirt", status="delivered",
                price=2500, quantity=1, size="M",
            ),
            OrderItem(
                order_id=order1.id, uid="1000002", product_id=sticker.id,
                product_name="ステッカー B", product_type="sticker", status="delivered",
                price=500, quantity=2, size="50x50mm",
            ),
            OrderItem(
                order_id=order2.id, uid="1000003", product_id=sticker.id,
                product_name="ステッカー C", product_type="sticker", status="ordered",
                price=500, quantity=5, size="50x50mm",
            ),
        ]
    )
    shipment = Shipment(status="ready", carrier="yamato", tracking_number=f"TN{token}")
    db_session.add(shipment)
    await db_session.flush()
    db_session.add(ShipmentItem(shipment_id=shipment.id, order_id=order1.id))
    await db_session.commit()

    yield {"token": token, "order1": order1.order_number, "order2": order2.order_number}


async def _export(
    client: AsyncClient, headers: dict[str, Any], body: dict[str, Any]
) -> list[list[str]]:
    response = await client.post(CSV_URL, json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    return _parse(response.content)


async def test_columns_endpoint(client: AsyncClient, auth_headers: dict[str, Any]) -> None:
    response = await client.get("/api/v1/data-export/columns", headers=auth_headers)
    assert response.status_code == 200
    columns = response.json()["columns"]
    assert {"key": "order_number", "label": "注文番号", "group": "受注"} in columns


async def test_one_row_per_item_with_joined_fields(
    client: AsyncClient, auth_headers: dict[str, Any], dataset: dict[str, Any]
) -> None:
    rows = await _export(
        client,
        auth_headers,
        {
            "columns": [
                "order_number",
                "item_uid",
                "item_product_type",
                "order_source_name",
                "manufacturer_name",
                "product_cost",
                "shipment_status",
                "shipment_tracking_number",
                "item_processing_name",
            ],
            "filters": {"search": dataset["token"]},
            "sort": {"column": "item_uid", "direction": "asc"},
        },
    )

    token = dataset["token"]
    assert rows == [
        [
            "注文番号", "商品番号", "商品種類", "配送元氏名", "メーカー名", "原価",
            "配送ステータス", "追跡番号", "商品名（処理用）",
        ],
        [
            dataset["order1"], "1000001", "Tシャツ", "配送元テスト",
            f"データ出力メーカー {token}", "1200", "配送準備完了", f"TN{token}",
            f"{dataset['order1']}_1000001",
        ],
        [
            dataset["order1"], "1000002", "ステッカー", "配送元テスト",
            f"データ出力メーカー {token}", "100", "配送準備完了", f"TN{token}",
            f"{dataset['order1']}_1000002",
        ],
        # 配送のない受注は配送の列が空欄
        [
            dataset["order2"], "1000003", "ステッカー", "配送元テスト",
            f"データ出力メーカー {token}", "100", "", "",
            f"{dataset['order2']}_1000003",
        ],
    ]


async def test_unselected_personal_info_is_not_output(
    client: AsyncClient, auth_headers: dict[str, Any], dataset: dict[str, Any]
) -> None:
    rows = await _export(
        client,
        auth_headers,
        {"columns": ["order_number", "item_quantity"], "filters": {"search": dataset["token"]}},
    )
    assert len(rows) == 4
    body = "\n".join(",".join(r) for r in rows)
    for value in ["山田", "佐藤", "090-0000-0000", "150-0001", "渋谷区", "テストビル"]:
        assert value not in body


@pytest.mark.parametrize(
    ("filters", "expected_uids"),
    [
        ({"status": "ordered"}, ["1000003"]),
        # 商品種別は明細の種別で絞る（同じ受注の Tシャツ明細は出ない）
        ({"product_type": "sticker"}, ["1000002", "1000003"]),
        ({"ordered_from": "2026-11-05"}, ["1000003"]),
        ({"ordered_to": "2026-11-05"}, ["1000001", "1000002"]),
        ({"shipping_from": "2026-12-01", "shipping_to": "2026-12-31"}, ["1000003"]),
        ({"shipping_to": "2026-11-01"}, []),
    ],
)
async def test_filters(
    client: AsyncClient,
    auth_headers: dict[str, Any],
    dataset: dict[str, Any],
    filters: dict[str, Any],
    expected_uids: list[str],
) -> None:
    rows = await _export(
        client,
        auth_headers,
        {
            "columns": ["item_uid"],
            "filters": {"search": dataset["token"], **filters},
            "sort": {"column": "item_uid"},
        },
    )
    assert rows[0] == ["商品番号"]
    assert [r[0] for r in rows[1:]] == expected_uids


async def test_search_by_order_number(
    client: AsyncClient, auth_headers: dict[str, Any], dataset: dict[str, Any]
) -> None:
    rows = await _export(
        client,
        auth_headers,
        {"columns": ["item_uid"], "filters": {"search": dataset["order2"]}},
    )
    assert [r[0] for r in rows[1:]] == ["1000003"]


async def test_sort_descending(
    client: AsyncClient, auth_headers: dict[str, Any], dataset: dict[str, Any]
) -> None:
    rows = await _export(
        client,
        auth_headers,
        {
            "columns": ["item_quantity", "item_uid"],
            "filters": {"search": dataset["token"]},
            "sort": {"column": "item_quantity", "direction": "desc"},
        },
    )
    assert rows[1:] == [["5", "1000003"], ["2", "1000002"], ["1", "1000001"]]


async def test_default_sort_is_newest_order_first(
    client: AsyncClient, auth_headers: dict[str, Any], dataset: dict[str, Any]
) -> None:
    rows = await _export(
        client,
        auth_headers,
        {"columns": ["item_uid"], "filters": {"search": dataset["token"]}},
    )
    # 新しい受注（order2）の明細が先。同じ受注の明細どうしは同一トランザクションで作られ
    # created_at が並ぶため、その中の順は問わない
    uids = [r[0] for r in rows[1:]]
    assert uids[0] == "1000003"
    assert sorted(uids[1:]) == ["1000001", "1000002"]


async def test_zero_rows_returns_header_only(
    client: AsyncClient, auth_headers: dict[str, Any]
) -> None:
    rows = await _export(
        client,
        auth_headers,
        {"columns": ["order_number", "customer_name"], "filters": {"search": uuid4().hex}},
    )
    assert rows == [["注文番号", "お客様氏名"]]


async def test_preview_matches_csv_and_counts_all_rows(
    client: AsyncClient, auth_headers: dict[str, Any], dataset: dict[str, Any]
) -> None:
    body = {
        "columns": ["item_uid", "item_product_type", "shipment_status"],
        "filters": {"search": dataset["token"]},
        "sort": {"column": "item_uid", "direction": "asc"},
    }
    response = await client.post(PREVIEW_URL, json=body, headers=auth_headers)
    assert response.status_code == 200, response.text
    preview = response.json()

    rows = await _export(client, auth_headers, body)
    assert preview["headers"] == rows[0]
    assert preview["rows"] == rows[1:]
    assert preview["total_count"] == 3


async def test_preview_counts_with_item_product_type(
    client: AsyncClient, auth_headers: dict[str, Any], dataset: dict[str, Any]
) -> None:
    response = await client.post(
        PREVIEW_URL,
        json={
            "columns": ["item_uid"],
            "filters": {"search": dataset["token"], "product_type": "sticker"},
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_count"] == 2
    # 絞り込み前の件数は DB 全体の明細数（他のテストのデータも含む）なので、下限だけ見る
    assert response.json()["unfiltered_count"] >= 3


async def test_preview_pages_through_all_rows(
    client: AsyncClient,
    auth_headers: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    token = uuid4().hex[:10]
    manufacturer = Manufacturer(
        name=f"プレビューメーカー {token}",
        email="dxp-mfg@example.com",
        supported_products=["sticker"],
        unit_prices={},
        lead_time_days=3,
        daily_order_limit=100,
    )
    db_session.add(manufacturer)
    await db_session.flush()
    product = Product(
        product_type="sticker", size="50x50mm", position=f"DXP{token}", color=None,
        manufacturer_id=manufacturer.id, cost=100, lead_time_days=3,
    )
    db_session.add(product)
    order = Order(
        order_number=f"DXP-{token}",
        status="ordered",
        total_price=0,
        ordered_at=datetime(2026, 11, 1, tzinfo=UTC),
        customer_name=f"プレビュー {token}",
        customer_phone="090-0000-0000",
        customer_postal_code="150-0001",
        customer_address_prefecture="東京都",
        customer_address_city="渋谷区1-2-3",
    )
    db_session.add(order)
    await db_session.flush()
    db_session.add_all(
        [
            OrderItem(
                order_id=order.id, uid=f"{n:07d}", product_id=product.id,
                product_name="ステッカー",
                product_type="sticker", status="ordered", price=100, quantity=1,
            )
            for n in range(12)
        ]
    )
    await db_session.commit()

    async def page(page: int, limit: int) -> dict[str, Any]:
        response = await client.post(
            PREVIEW_URL,
            json={
                "columns": ["item_uid"],
                "filters": {"search": token},
                "sort": {"column": "item_uid"},
                "page": page,
                "limit": limit,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        result: dict[str, Any] = response.json()
        return result

    # 5 件ずつ 3 ページで、12 件すべてを重複なく見られる
    pages = [await page(n, 5) for n in (1, 2, 3)]
    assert [len(p["rows"]) for p in pages] == [5, 5, 2]
    assert all(p["total_count"] == 12 for p in pages)
    uids = [row[0] for p in pages for row in p["rows"]]
    assert uids == [f"{n:07d}" for n in range(12)]

    # 総件数を超えたページは空（エラーにしない）
    assert (await page(4, 5))["rows"] == []


async def test_preview_rejects_too_large_limit(
    client: AsyncClient, auth_headers: dict[str, Any]
) -> None:
    response = await client.post(
        PREVIEW_URL, json={"columns": ["item_uid"], "limit": 101}, headers=auth_headers
    )
    assert response.status_code == 422


async def test_no_columns_is_rejected(client: AsyncClient, auth_headers: dict[str, Any]) -> None:
    response = await client.post(CSV_URL, json={"columns": []}, headers=auth_headers)
    assert response.status_code == 422


async def test_unknown_column_is_rejected(
    client: AsyncClient, auth_headers: dict[str, Any]
) -> None:
    response = await client.post(CSV_URL, json={"columns": ["nope"]}, headers=auth_headers)
    assert response.status_code == 400


async def test_requires_admin(client: AsyncClient) -> None:
    response = await client.post(CSV_URL, json={"columns": ["order_number"]})
    assert response.status_code in (401, 403)
    response = await client.get("/api/v1/data-export/columns")
    assert response.status_code in (401, 403)
    response = await client.post(PREVIEW_URL, json={"columns": ["order_number"]})
    assert response.status_code in (401, 403)
