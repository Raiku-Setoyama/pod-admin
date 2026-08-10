"""配送一覧のテスト（検索・並び替え）で共有するヘルパー.

`GET /shipments` は実配送（shipment）と準備中注文（pending_order）の両方を返すため、
どのテストも「注文を入れる」「実配送を組む」「一覧を引いて種別ごとに ID を取り出す」の
3 つを必要とする。

日時・日付は `date` / `datetime` をそのまま渡す（`None` なら NOW() / NULL になる）。
"""

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT_ORDER = text("""
    INSERT INTO orders (
        id, order_number, order_source_id,
        customer_name, customer_email, customer_phone,
        customer_postal_code, customer_address_prefecture, customer_address_city,
        status, estimated_shipping_date, ordered_at, created_at, updated_at
    )
    VALUES (
        :id, :order_number, :order_source_id,
        :customer_name, :customer_email, :customer_phone,
        :customer_postal_code, :customer_address_prefecture, :customer_address_city,
        :status, CAST(:estimated_shipping_date AS date),
        COALESCE(CAST(:ordered_at AS timestamptz), NOW()), NOW(), NOW()
    )
""")

_INSERT_SHIPMENT = text("""
    INSERT INTO shipments (id, status, tracking_number, created_at, updated_at)
    VALUES (
        :id, :status, :tracking_number,
        COALESCE(CAST(:created_at AS timestamptz), NOW()), NOW()
    )
""")

_INSERT_SHIPMENT_ITEM = text("""
    INSERT INTO shipment_items (id, shipment_id, order_id, created_at, updated_at)
    VALUES (:id, :shipment_id, :order_id, NOW(), NOW())
""")


async def insert_order(
    db_session: AsyncSession,
    order_source_id: str,
    order_number: str,
    customer_name: str,
    status: str,
    estimated_shipping_date: date | None = None,
    ordered_at: datetime | None = None,
) -> str:
    """注文を 1 件作り、その ID を返す（コミットは呼び出し側）."""
    order_id = str(uuid4())
    await db_session.execute(
        _INSERT_ORDER,
        {
            "id": order_id,
            "order_number": order_number,
            "order_source_id": order_source_id,
            "customer_name": customer_name,
            "customer_email": "shipment-search@example.com",
            "customer_phone": "090-0000-0000",
            "customer_postal_code": "100-0001",
            "customer_address_prefecture": "東京都",
            "customer_address_city": "千代田区1-1-1",
            "status": status,
            "estimated_shipping_date": estimated_shipping_date,
            "ordered_at": ordered_at,
        },
    )
    return order_id


async def insert_shipment(
    db_session: AsyncSession,
    order_ids: list[str],
    tracking_number: str | None = None,
    status: str = "pending",
    created_at: datetime | None = None,
) -> str:
    """指定した注文をまとめた実配送を 1 件作り、その ID を返す."""
    shipment_id = str(uuid4())
    await db_session.execute(
        _INSERT_SHIPMENT,
        {
            "id": shipment_id,
            "status": status,
            "tracking_number": tracking_number,
            "created_at": created_at,
        },
    )
    for order_id in order_ids:
        await db_session.execute(
            _INSERT_SHIPMENT_ITEM,
            {"id": str(uuid4()), "shipment_id": shipment_id, "order_id": order_id},
        )
    return shipment_id


async def list_shipments(
    client: AsyncClient, auth_headers: dict[str, Any], **params: Any
) -> dict[str, Any]:
    """配送一覧を引く。200 以外はその場で失敗させる."""
    response = await client.get(
        "/api/v1/shipments",
        params={"limit": 100, **params},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def search_shipments(
    client: AsyncClient, auth_headers: dict[str, Any], keyword: str
) -> dict[str, Any]:
    """配送一覧をキーワード検索する."""
    return await list_shipments(client, auth_headers, search=keyword)


def shipment_ids(data: dict[str, Any]) -> set[str]:
    """検索結果のうち実配送の ID を集める."""
    return {i["id"] for i in data["items"] if i["type"] == "shipment"}


def ordered_shipment_ids(data: dict[str, Any]) -> list[str]:
    """検索結果のうち実配送の ID を、返ってきた順のまま並べる."""
    return [i["id"] for i in data["items"] if i["type"] == "shipment"]


def pending_order_ids(data: dict[str, Any]) -> set[str]:
    """検索結果のうち準備中注文の注文 ID を集める."""
    return {i["order_id"] for i in data["items"] if i["type"] == "pending_order"}


def ordered_pending_order_ids(data: dict[str, Any]) -> list[str]:
    """検索結果のうち準備中注文の注文 ID を、返ってきた順のまま並べる."""
    return [i["order_id"] for i in data["items"] if i["type"] == "pending_order"]
