"""Unit tests for ManufacturingDataService (repos / VM / storage / session mocked)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.services.illustrator_vm_client import IllustratorVmError, VmJobStatus
from app.services.manufacturing_data_service import (
    ManufacturingDataService,
    is_generatable_item,
)

_HTTPX = "app.services.manufacturing_data_service.httpx.AsyncClient"

_LAYERS = [
    {"layer_type": "color", "url": "http://x/c.png"},
    {"layer_type": "cutline", "url": "http://x/l.png"},
]


def _md(**overrides):
    md = ManufacturingData(
        order_source_id="src",
        product_code="PC",
        product_type="acrylic_keychain",
        size="50x50mm",
        variant="clear",
        status=MfgDataStatus.PENDING.value,
        source_images=_LAYERS,
    )
    md.id = "md-1"
    md.attempts = 0
    md.file_path = None
    for key, value in overrides.items():
        setattr(md, key, value)
    return md


def _item(**overrides):
    data = {
        "product_code": "PC",
        "source_images": _LAYERS,
        "product_type": "acrylic_keychain",
        "size": "50x50mm",
        "variant": "clear",
        "order_id": "ORDER1",
        "manufacturing_data_id": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _httpx_mock():
    resp = MagicMock()
    resp.content = b"png"
    resp.raise_for_status = MagicMock()
    inst = AsyncMock()
    inst.get.return_value = resp
    inst.__aenter__ = AsyncMock(return_value=inst)
    inst.__aexit__ = AsyncMock(return_value=False)
    return inst


def _service(*, mfg_repo, order_repo=None, file_storage=None, vm_client=None):
    session = AsyncMock()
    service = ManufacturingDataService(
        session,
        mfg_repo,
        order_repo or AsyncMock(),
        file_storage or AsyncMock(),
        vm_client,
    )
    return service, session


class TestIsGeneratableItem:
    def test_true_when_product_code_and_layers(self):
        assert is_generatable_item(_item()) is True

    def test_false_without_product_code_or_layers(self):
        assert is_generatable_item(_item(product_code=None)) is False
        assert is_generatable_item(_item(source_images=None)) is False


class TestEnsureForOrder:
    @pytest.mark.asyncio
    async def test_generates_on_cache_miss(self):
        md = _md()
        mfg_repo = AsyncMock()
        mfg_repo.find_by_cache_key.return_value = None
        mfg_repo.create.return_value = md
        mfg_repo.claim_for_generation.return_value = True
        order = SimpleNamespace(order_source_id="src", items=[_item()])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order
        file_storage = AsyncMock()
        file_storage.save.return_value = "manufacturing/out.ai"
        vm = AsyncMock()
        vm.submit.return_value = "job1"
        vm.wait_for_completion.return_value = VmJobStatus("job1", "completed", 100, None, "OUT.ai")
        vm.download.return_value = b"AIDATA"

        service, _ = _service(
            mfg_repo=mfg_repo, order_repo=order_repo, file_storage=file_storage, vm_client=vm
        )
        with patch(_HTTPX, return_value=_httpx_mock()):
            await service.ensure_for_order("order-1")

        assert md.status == MfgDataStatus.READY.value
        assert md.file_path == "manufacturing/out.ai"
        assert md.output_filename == "OUT.ai"
        assert md.file_size == len(b"AIDATA")
        vm.submit.assert_awaited_once()
        file_storage.save.assert_awaited_once()
        assert order.items[0].manufacturing_data_id == "md-1"

    @pytest.mark.asyncio
    async def test_reuses_ready_cache_without_calling_vm(self):
        md = _md(status=MfgDataStatus.READY.value, file_path="manufacturing/exist.ai")
        mfg_repo = AsyncMock()
        mfg_repo.find_by_cache_key.return_value = md
        order = SimpleNamespace(order_source_id="src", items=[_item()])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order
        file_storage = AsyncMock()
        file_storage.exists.return_value = True
        vm = AsyncMock()

        service, _ = _service(
            mfg_repo=mfg_repo, order_repo=order_repo, file_storage=file_storage, vm_client=vm
        )
        await service.ensure_for_order("order-1")

        vm.submit.assert_not_awaited()
        mfg_repo.create.assert_not_awaited()
        file_storage.exists.assert_awaited_once_with("manufacturing/exist.ai")

    @pytest.mark.asyncio
    async def test_regenerates_ready_when_file_missing(self):
        md = _md(status=MfgDataStatus.READY.value, file_path="manufacturing/gone.ai")
        mfg_repo = AsyncMock()
        mfg_repo.find_by_cache_key.return_value = md
        mfg_repo.claim_for_generation.return_value = True
        order = SimpleNamespace(order_source_id="src", items=[_item()])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order
        file_storage = AsyncMock()
        file_storage.exists.return_value = False  # ファイル消失
        file_storage.save.return_value = "manufacturing/new.ai"
        vm = AsyncMock()
        vm.submit.return_value = "job2"
        vm.wait_for_completion.return_value = VmJobStatus("job2", "completed", 100, None, "NEW.ai")
        vm.download.return_value = b"NEW"

        service, _ = _service(
            mfg_repo=mfg_repo, order_repo=order_repo, file_storage=file_storage, vm_client=vm
        )
        with patch(_HTTPX, return_value=_httpx_mock()):
            await service.ensure_for_order("order-1")

        mfg_repo.claim_for_generation.assert_awaited_once_with("md-1", allow_ready=True)
        vm.submit.assert_awaited_once()
        assert md.file_path == "manufacturing/new.ai"

    @pytest.mark.asyncio
    async def test_generation_failure_marks_failed(self):
        md = _md()
        mfg_repo = AsyncMock()
        mfg_repo.find_by_cache_key.return_value = None
        mfg_repo.create.return_value = md
        mfg_repo.claim_for_generation.return_value = True
        mfg_repo.get_by_id.return_value = md
        order = SimpleNamespace(order_source_id="src", items=[_item()])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order
        vm = AsyncMock()
        vm.submit.side_effect = IllustratorVmError("boom")

        service, _ = _service(mfg_repo=mfg_repo, order_repo=order_repo, vm_client=vm)
        with patch(_HTTPX, return_value=_httpx_mock()):
            await service.ensure_for_order("order-1")

        assert md.status == MfgDataStatus.FAILED.value
        assert "boom" in (md.error_message or "")

    @pytest.mark.asyncio
    async def test_vm_unconfigured_leaves_pending(self):
        md = _md()
        mfg_repo = AsyncMock()
        mfg_repo.find_by_cache_key.return_value = None
        mfg_repo.create.return_value = md
        order = SimpleNamespace(order_source_id="src", items=[_item()])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order

        service, _ = _service(mfg_repo=mfg_repo, order_repo=order_repo, vm_client=None)
        await service.ensure_for_order("order-1")

        assert md.status == MfgDataStatus.PENDING.value
        mfg_repo.claim_for_generation.assert_not_awaited()


class TestGenerateById:
    @pytest.mark.asyncio
    async def test_missing_row_is_noop(self):
        mfg_repo = AsyncMock()
        mfg_repo.get_by_id.return_value = None
        service, _ = _service(mfg_repo=mfg_repo, vm_client=AsyncMock())
        await service.generate_by_id("nope")  # should not raise
