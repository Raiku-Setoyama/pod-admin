"""Integration tests for manufacturing-data status/retry endpoints (admin)."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus


async def _make_md(db_session: AsyncSession, source_id: str, status: str) -> ManufacturingData:
    md = ManufacturingData(
        order_source_id=source_id,
        product_code=f"PC-{uuid4().hex[:8]}",
        product_type="acrylic_keychain",
        size="50x50mm",
        variant="clear",
        status=status,
        error_message="prev error" if status == MfgDataStatus.FAILED.value else None,
    )
    db_session.add(md)
    await db_session.commit()
    return md


class TestManufacturingDataEndpoints:
    @pytest.mark.asyncio
    async def test_list_requires_admin(self, client):
        resp = await client.get("/api/v1/manufacturing-data")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_rows(self, client, db_session, auth_headers, test_order_source):
        await _make_md(db_session, test_order_source["id"], MfgDataStatus.PENDING.value)
        resp = await client.get("/api/v1/manufacturing-data?limit=10", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert body["total"] >= 1

    @pytest.mark.asyncio
    async def test_retry_resets_failed_to_pending(
        self, client, db_session, auth_headers, test_order_source
    ):
        md = await _make_md(db_session, test_order_source["id"], MfgDataStatus.FAILED.value)
        resp = await client.post(f"/api/v1/manufacturing-data/{md.id}/retry", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "pending"

    @pytest.mark.asyncio
    async def test_retry_404_for_unknown(self, client, auth_headers):
        resp = await client.post(
            f"/api/v1/manufacturing-data/{uuid4()}/retry", headers=auth_headers
        )
        assert resp.status_code == 404
