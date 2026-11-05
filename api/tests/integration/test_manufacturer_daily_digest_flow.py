"""Integration test for the manufacturer daily digest end-to-end flow (requires DB).

実際の DB に対して集計クエリ・原子的な日次 claim・明細の通知済み記録を検証する。
メール送信は依存性オーバーライドでモックする。
"""

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.dependencies import get_email_service
from app.main import app


@pytest.fixture
def internal_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "test-internal-secret")
    return {"X-Internal-Secret": "test-internal-secret"}


@pytest.fixture
def mock_email() -> Iterator[Any]:
    email = MagicMock()
    email.send_manufacturer_daily_digest = AsyncMock(return_value=True)
    app.dependency_overrides[get_email_service] = lambda: email
    yield email
    app.dependency_overrides.pop(get_email_service, None)


@pytest.fixture
async def seeded_manufacturer(db_session: AsyncSession) -> AsyncIterator[dict[str, Any]]:
    mid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    oid = str(uuid.uuid4())
    iid = str(uuid.uuid4())

    await db_session.execute(
        text(
            "INSERT INTO manufacturers (id, name, email, supported_products, unit_prices, "
            "lead_time_days, daily_order_limit, sharing_method, is_active, created_at, updated_at) "
            "VALUES (:id, :name, :email, '{tshirt}', '{}', 7, 100, 'portal', true, NOW(), NOW())"
        ),
        {"id": mid, "name": f"Digest社{mid[:8]}", "email": "mfr@example.com"},
    )
    await db_session.execute(
        text(
            "INSERT INTO products (id, product_type, size, color, position, manufacturer_id, "
            "cost, lead_time_days, is_active, created_at, updated_at) "
            "VALUES (:id, 'tshirt', 'M', NULL, NULL, :mid, 500, 7, true, NOW(), NOW())"
        ),
        {"id": pid, "mid": mid},
    )
    await db_session.execute(
        text(
            "INSERT INTO orders (id, order_number, product_name, quantity, customer_name, "
            "customer_email, customer_phone, customer_postal_code, customer_address_prefecture, "
            "customer_address_city, status, ordered_at, total_price, created_at, updated_at) "
            "VALUES (:id, :num, 'T', 1, 'Cust', 'c@example.com', '090', '100-0001', '東京都', "
            "'千代田区', 'ordered', NOW(), 0, NOW(), NOW())"
        ),
        {"id": oid, "num": f"D-{oid[:8]}"},
    )
    await db_session.execute(
        text(
            "INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, "
            "price, quantity, status, created_at, updated_at) "
            "VALUES (:id, :oid, :uid, :pid, 'T', 'tshirt', 500, 3, 'ordered', NOW(), NOW())"
        ),
        {"id": iid, "oid": oid, "uid": iid[:8], "pid": pid},
    )
    await db_session.execute(
        text(
            "INSERT INTO manufacturer_notification_settings (id, manufacturer_id, "
            "daily_digest_enabled, to_emails, cc_emails, created_at, updated_at) "
            "VALUES (:id, :mid, true, ARRAY['to@example.com']::varchar[], "
            "ARRAY['cc@example.com']::varchar[], NOW(), NOW())"
        ),
        {"id": str(uuid.uuid4()), "mid": mid},
    )
    await db_session.commit()

    yield {"manufacturer_id": mid, "item_quantity": 3, "order_id": oid, "product_id": pid}

    for table, key in (
        ("manufacturer_notification_settings", ("manufacturer_id", mid)),
        ("order_items", ("order_id", oid)),
        ("orders", ("id", oid)),
        ("products", ("id", pid)),
        ("manufacturers", ("id", mid)),
    ):
        await db_session.execute(
            text(f"DELETE FROM {table} WHERE {key[0]} = :v"), {"v": key[1]}
        )
    await db_session.commit()


@pytest.mark.asyncio
async def test_force_run_sends_then_idempotent(
    client: Any, internal_headers: dict[str, Any], mock_email: Any, seeded_manufacturer: dict[str, Any]
) -> None:
    mid = seeded_manufacturer["manufacturer_id"]

    # 1回目（force）: 新規発注済み 3件 → 送信される
    resp = await client.post(
        "/api/v1/internal/manufacturer-daily-digest?force=true", headers=internal_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ran"] is True
    assert mid in body["sent_manufacturer_ids"]

    kwargs = mock_email.send_manufacturer_daily_digest.await_args.kwargs
    # 明細 1 件・数量 3 → 発注中明細数=1, 合計数量=3
    assert kwargs["item_count"] == 1
    assert kwargs["total_quantity"] == 3
    assert kwargs["to_emails"] == ["to@example.com"]
    assert kwargs["cc_emails"] == ["cc@example.com"]

    # 2回目（force）: 1回目の明細は通知済み → 0件スキップ（送信されない）
    mock_email.send_manufacturer_daily_digest.reset_mock()
    resp2 = await client.post(
        "/api/v1/internal/manufacturer-daily-digest?force=true", headers=internal_headers
    )
    body2 = resp2.json()
    assert mid in body2["skipped_zero_manufacturer_ids"]
    assert mid not in body2["sent_manufacturer_ids"]
    mock_email.send_manufacturer_daily_digest.assert_not_called()


async def _add_item(
    db_session: AsyncSession, seeded: dict[str, Any], *, status: str, quantity: int
) -> str:
    iid = str(uuid.uuid4())
    await db_session.execute(
        text(
            "INSERT INTO order_items (id, order_id, uid, product_id, product_name, product_type, "
            "price, quantity, status, created_at, updated_at) "
            "VALUES (:id, :oid, :uid, :pid, 'T', 'tshirt', 500, :qty, :status, NOW(), NOW())"
        ),
        {
            "id": iid,
            "oid": seeded["order_id"],
            "uid": iid[:8],
            "pid": seeded["product_id"],
            "qty": quantity,
            "status": status,
        },
    )
    await db_session.commit()
    return iid


async def _set_status(db_session: AsyncSession, iid: str, status: str) -> None:
    await db_session.execute(
        text("UPDATE order_items SET status = :status WHERE id = :id"),
        {"status": status, "id": iid},
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_notifies_items_already_advanced_past_ordered(
    client: Any,
    internal_headers: dict[str, Any],
    mock_email: Any,
    seeded_manufacturer: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """送信処理より先に製造中・納入済みへ進んだ明細も、未通知なら数える（2026-11-04 の取りこぼし）."""
    mid = seeded_manufacturer["manufacturer_id"]
    await _add_item(db_session, seeded_manufacturer, status="manufacturing", quantity=5)
    await _add_item(db_session, seeded_manufacturer, status="delivered", quantity=2)
    # 製造に回らない明細は数えない
    await _add_item(db_session, seeded_manufacturer, status="cancelled", quantity=100)

    resp = await client.post(
        "/api/v1/internal/manufacturer-daily-digest?force=true", headers=internal_headers
    )

    assert mid in resp.json()["sent_manufacturer_ids"]
    kwargs = mock_email.send_manufacturer_daily_digest.await_args.kwargs
    # 発注済み 3 + 製造中 5 + 納入済み 2
    assert kwargs["item_count"] == 3
    assert kwargs["total_quantity"] == 10


@pytest.mark.asyncio
async def test_notifies_item_that_was_preparing_at_previous_run(
    client: Any,
    internal_headers: dict[str, Any],
    mock_email: Any,
    seeded_manufacturer: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """送信処理の時点で発注準備中だった明細は、発注済みになった後の回で数える."""
    mid = seeded_manufacturer["manufacturer_id"]
    preparing = await _add_item(
        db_session, seeded_manufacturer, status="preparing_order", quantity=4
    )

    # 1 回目: 発注準備中の明細は数えない
    resp = await client.post(
        "/api/v1/internal/manufacturer-daily-digest?force=true", headers=internal_headers
    )
    assert mid in resp.json()["sent_manufacturer_ids"]
    assert mock_email.send_manufacturer_daily_digest.await_args.kwargs["total_quantity"] == 3

    # 製造データの生成が終わって発注済みになる（作成は 1 回目の送信より前）
    await _set_status(db_session, preparing, "ordered")
    mock_email.send_manufacturer_daily_digest.reset_mock()

    # 2 回目: その明細だけを数える
    resp = await client.post(
        "/api/v1/internal/manufacturer-daily-digest?force=true", headers=internal_headers
    )
    assert mid in resp.json()["sent_manufacturer_ids"]
    kwargs = mock_email.send_manufacturer_daily_digest.await_args.kwargs
    assert kwargs["item_count"] == 1
    assert kwargs["total_quantity"] == 4


@pytest.mark.asyncio
async def test_failed_send_is_retried_next_run(
    client: Any,
    internal_headers: dict[str, Any],
    mock_email: Any,
    seeded_manufacturer: dict[str, Any],
) -> None:
    """送れなかった回の明細は通知済みにせず、次の回で送る."""
    mid = seeded_manufacturer["manufacturer_id"]
    mock_email.send_manufacturer_daily_digest.return_value = False

    resp = await client.post(
        "/api/v1/internal/manufacturer-daily-digest?force=true", headers=internal_headers
    )
    assert mid in resp.json()["failed_manufacturer_ids"]

    mock_email.send_manufacturer_daily_digest.return_value = True
    resp = await client.post(
        "/api/v1/internal/manufacturer-daily-digest?force=true", headers=internal_headers
    )
    assert mid in resp.json()["sent_manufacturer_ids"]
    assert mock_email.send_manufacturer_daily_digest.await_args.kwargs["total_quantity"] == 3


@pytest.mark.asyncio
async def test_requires_internal_secret(client: Any, mock_email: Any) -> None:
    # INTERNAL_API_SECRET 未設定（既定 ""）→ 403
    resp = await client.post(
        "/api/v1/internal/manufacturer-daily-digest",
        headers={"X-Internal-Secret": "whatever"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_notification_settings_crud_roundtrip(
    client: Any, auth_headers: dict[str, Any], seeded_manufacturer: dict[str, Any]
) -> None:
    mid = seeded_manufacturer["manufacturer_id"]

    # GET: seed 済みの設定が返る
    resp = await client.get(
        f"/api/v1/manufacturers/{mid}/notification-settings", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["daily_digest_enabled"] is True
    assert body["to_emails"] == ["to@example.com"]

    # PUT: 更新（無効化・宛先変更）。空白/重複は正規化される
    resp = await client.put(
        f"/api/v1/manufacturers/{mid}/notification-settings",
        headers=auth_headers,
        json={
            "daily_digest_enabled": False,
            "to_emails": [" new@example.com ", "new@example.com"],
            "cc_emails": [],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["to_emails"] == ["new@example.com"]

    # GET: 更新が反映されている
    resp = await client.get(
        f"/api/v1/manufacturers/{mid}/notification-settings", headers=auth_headers
    )
    assert resp.json()["daily_digest_enabled"] is False
    assert resp.json()["to_emails"] == ["new@example.com"]

    # PUT: 不正なメール → 422（日本語メッセージ）
    resp = await client.put(
        f"/api/v1/manufacturers/{mid}/notification-settings",
        headers=auth_headers,
        json={"daily_digest_enabled": True, "to_emails": ["not-an-email"], "cc_emails": []},
    )
    assert resp.status_code == 422
    assert "error" in resp.json()
