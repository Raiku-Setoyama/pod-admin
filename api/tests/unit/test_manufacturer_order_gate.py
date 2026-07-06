"""Unit tests for the manufacturer order gate (manufacturing-data readiness)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.manufacturing_data import MfgDataStatus
from app.schemas.manufacturer import ManufacturerOrderStatusUpdate
from app.services.manufacturer_order_service import ManufacturerOrderService
from app.utils.exceptions import ManufacturingDataNotReadyError


def _md(status=MfgDataStatus.READY.value, file_path="path", md_id="md-1"):
    return SimpleNamespace(id=md_id, status=status, file_path=file_path)


def _oi(oi_id="oi-1", product_code="PC", manufacturing_data_id="md-1"):
    return SimpleNamespace(
        id=oi_id, product_code=product_code, manufacturing_data_id=manufacturing_data_id
    )


def _row(order_item, item_status="ordered"):
    # (order_item, order_number, ordered_at, customer_name, cost, item_status, order_status, lead)
    return (order_item, "0000001", None, "cust", 100, item_status, "ordered", 3)


def _service(mfg_repo=None, file_storage=None, order_repo=None, manufacturer_repo=None):
    return ManufacturerOrderService(
        order_repo or AsyncMock(),
        manufacturer_repo or AsyncMock(),
        AsyncMock(),
        mfg_repo,
        file_storage,
    )


class TestPartitionByReadiness:
    @pytest.mark.asyncio
    async def test_gate_inactive_includes_all(self):
        svc = _service()  # mfg_repo / file_storage 未設定 → ゲート無効
        includable, held, content = await svc._partition_by_readiness([_row(_oi())])
        assert len(includable) == 1
        assert held == 0
        assert content == {}

    @pytest.mark.asyncio
    async def test_legacy_item_always_included(self):
        mfg_repo = AsyncMock()
        mfg_repo.find_by_ids.return_value = []
        svc = _service(mfg_repo, AsyncMock())
        legacy = _oi(oi_id="leg", product_code=None, manufacturing_data_id=None)
        includable, held, _ = await svc._partition_by_readiness([_row(legacy)])
        assert len(includable) == 1
        assert held == 0

    @pytest.mark.asyncio
    async def test_ready_v2_included_with_stored_content(self):
        mfg_repo = AsyncMock()
        mfg_repo.find_by_ids.return_value = [_md()]
        fs = AsyncMock()
        fs.get.return_value = b"AIDATA"
        svc = _service(mfg_repo, fs)
        includable, held, content = await svc._partition_by_readiness([_row(_oi())])
        assert len(includable) == 1
        assert held == 0
        assert content["oi-1"] == b"AIDATA"

    @pytest.mark.asyncio
    async def test_not_ready_v2_is_held(self):
        mfg_repo = AsyncMock()
        mfg_repo.find_by_ids.return_value = [_md(status=MfgDataStatus.PENDING.value)]
        svc = _service(mfg_repo, AsyncMock())
        includable, held, _ = await svc._partition_by_readiness([_row(_oi())])
        assert includable == []
        assert held == 1

    @pytest.mark.asyncio
    async def test_ready_but_file_missing_is_held(self):
        mfg_repo = AsyncMock()
        mfg_repo.find_by_ids.return_value = [_md()]
        fs = AsyncMock()
        fs.get.return_value = None  # GCS 180日ライフサイクル等でファイル消失
        svc = _service(mfg_repo, fs)
        includable, held, _ = await svc._partition_by_readiness([_row(_oi())])
        assert includable == []
        assert held == 1


class TestAssertManufacturingReady:
    @pytest.mark.asyncio
    async def test_raises_when_not_ready(self):
        order_repo = AsyncMock()
        order_repo.find_manufacturer_items.return_value = [_oi()]
        mfg_repo = AsyncMock()
        mfg_repo.find_by_ids.return_value = [_md(status=MfgDataStatus.FAILED.value)]
        svc = _service(mfg_repo, AsyncMock(), order_repo)
        with pytest.raises(ManufacturingDataNotReadyError):
            await svc._assert_manufacturing_ready("mfr-1", None)

    @pytest.mark.asyncio
    async def test_passes_when_ready(self):
        order_repo = AsyncMock()
        order_repo.find_manufacturer_items.return_value = [_oi()]
        mfg_repo = AsyncMock()
        mfg_repo.find_by_ids.return_value = [_md()]
        fs = AsyncMock()
        fs.exists.return_value = True
        svc = _service(mfg_repo, fs, order_repo)
        await svc._assert_manufacturing_ready("mfr-1", None)  # 例外が出なければOK

    @pytest.mark.asyncio
    async def test_update_order_status_rejects_not_ready(self):
        order_repo = AsyncMock()
        order_repo.find_manufacturer_items.return_value = [_oi()]
        mfg_repo = AsyncMock()
        mfg_repo.find_by_ids.return_value = [_md(status=MfgDataStatus.PENDING.value)]
        manufacturer_repo = AsyncMock()
        manufacturer_repo.find_by_id.return_value = SimpleNamespace(id="mfr-1", name="M")
        svc = ManufacturerOrderService(
            order_repo, manufacturer_repo, AsyncMock(), mfg_repo, AsyncMock()
        )
        data = ManufacturerOrderStatusUpdate(status="manufacturing", order_item_ids=None, note=None)
        with pytest.raises(ManufacturingDataNotReadyError):
            await svc.update_order_status("mfr-1", data)
        order_repo.update_item_status_by_manufacturer.assert_not_awaited()
