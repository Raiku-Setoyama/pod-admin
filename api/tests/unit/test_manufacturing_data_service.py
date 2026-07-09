"""Unit tests for ManufacturingDataService and the manufacturing readiness gate."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import OrderItem
from app.services import manufacturing_data_service as mds
from app.services.illustrator_vm_client import IllustratorVmError
from app.services.manufacturing_data_service import ManufacturingDataService
from app.utils.exceptions import ConflictError, NotFoundError


def _v2_item(
    *,
    product_code="RKSYO-1",
    product_type="acrylic_keychain",
    size="50x50mm",
    layers=("color", "cutline"),
):
    """v2 明細（product_code + source_images あり）の簡易モック."""
    return SimpleNamespace(
        id="item-1",
        product_code=product_code,
        product_type=product_type,
        size=size,
        source_images=[{"layer_type": ly, "url": f"https://x/{ly}.png"} for ly in layers],
        manufacturing_data_id=None,
        manufacturing_data=None,
    )


def _service(md_repo, order_repo=None, **kwargs):
    return ManufacturingDataService(
        md_repo=md_repo,
        order_repo=order_repo or AsyncMock(),
        session=None,  # unit test: _commit は no-op、_insert_row は md_repo.create を使用
        **kwargs,
    )


def _assign_id(md: ManufacturingData, new_id: str = "md-new") -> ManufacturingData:
    md.id = new_id
    return md


class TestCacheResolution:
    @pytest.mark.asyncio
    async def test_creates_new_row_and_requests_generation(self):
        item = _v2_item()
        order = SimpleNamespace(order_source_id="src-1", items=[item])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order

        md_repo = AsyncMock()
        md_repo.find_by_cache_key.return_value = None
        md_repo.create.side_effect = lambda m: _assign_id(m, "md-new")

        svc = _service(md_repo, order_repo)
        to_generate = await svc.prepare_for_order("order-1")

        assert to_generate == ["md-new"]
        assert item.manufacturing_data_id == "md-new"
        # keychain(color+cutline, white なし) は variant clear で照会される
        # find_by_cache_key(order_source_id, product_code, size, variant)
        called = md_repo.find_by_cache_key.call_args
        assert called.args == ("src-1", "RKSYO-1", "50x50mm", "clear")

    @pytest.mark.asyncio
    async def test_reuses_ready_cache_without_generation(self):
        item = _v2_item()
        order = SimpleNamespace(order_source_id="src-1", items=[item])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order

        existing = ManufacturingData(product_code="RKSYO-1", product_type="acrylic_keychain")
        existing.id = "md-existing"
        existing.status = MfgDataStatus.READY.value

        md_repo = AsyncMock()
        md_repo.find_by_cache_key.return_value = existing

        svc = _service(md_repo, order_repo)
        to_generate = await svc.prepare_for_order("order-1")

        # キャッシュ再利用 → VM生成は起動しない
        assert to_generate == []
        assert item.manufacturing_data_id == "md-existing"
        md_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_cache_is_reset_and_regenerated(self):
        item = _v2_item()
        order = SimpleNamespace(order_source_id="src-1", items=[item])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order

        existing = ManufacturingData(product_code="RKSYO-1", product_type="acrylic_keychain")
        existing.id = "md-failed"
        existing.status = MfgDataStatus.FAILED.value

        md_repo = AsyncMock()
        md_repo.find_by_cache_key.return_value = existing

        svc = _service(md_repo, order_repo)
        to_generate = await svc.prepare_for_order("order-1")

        assert to_generate == ["md-failed"]
        assert existing.status == MfgDataStatus.PENDING.value
        assert item.manufacturing_data_id == "md-failed"

    @pytest.mark.asyncio
    async def test_unmappable_product_creates_failed_row_no_generation(self):
        # mug_cup は pod-admin ProductType 外 → マッピング不能 → failed 行（発注ゲートで保留）
        item = _v2_item(product_type="mug_cup", size="normal", layers=("design",))
        order = SimpleNamespace(order_source_id="src-1", items=[item])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order

        md_repo = AsyncMock()
        md_repo.create.side_effect = lambda m: _assign_id(m, "md-bad")

        svc = _service(md_repo, order_repo)
        to_generate = await svc.prepare_for_order("order-1")

        assert to_generate == []
        assert item.manufacturing_data_id == "md-bad"
        created = md_repo.create.call_args.args[0]
        assert created.status == MfgDataStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_v1_items_are_ignored(self):
        v1 = SimpleNamespace(
            id="i", product_code=None, source_images=None, manufacturing_data_id=None
        )
        order = SimpleNamespace(order_source_id="src-1", items=[v1])
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = order
        md_repo = AsyncMock()

        svc = _service(md_repo, order_repo)
        assert await svc.prepare_for_order("order-1") == []
        md_repo.find_by_cache_key.assert_not_called()

    @pytest.mark.asyncio
    async def test_insert_row_recovers_existing_on_conflict_marks_not_created(self):
        # 同時受注でキャッシュキーが競合したら、既存行を回収し created=False を返す
        # （作成した側だけが生成を起動し、二重生成しないようにする）。
        from sqlalchemy.exc import IntegrityError

        item = _v2_item()
        existing = ManufacturingData(
            product_code="RKSYO-1", product_type="acrylic_keychain"
        )
        existing.id = "md-existing"
        existing.status = MfgDataStatus.PENDING.value

        md_repo = AsyncMock()
        md_repo.find_by_cache_key.return_value = existing

        class _Nested:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        session = MagicMock()
        session.begin_nested = MagicMock(return_value=_Nested())
        session.add = MagicMock()
        session.flush = AsyncMock(
            side_effect=IntegrityError("stmt", {}, Exception("dup key"))
        )

        svc = ManufacturingDataService(
            md_repo=md_repo, order_repo=AsyncMock(), session=session
        )
        md, created = await svc._insert_row(
            "src-1",
            item,
            variant="clear",
            status=MfgDataStatus.PENDING,
            source_images=item.source_images,
        )
        assert md is existing
        assert created is False


class TestGenerateDriver:
    def _pending_md(self):
        md = ManufacturingData(product_code="RKSYO-1", product_type="sticker", size="50x50mm")
        md.id = "md-1"
        md.status = MfgDataStatus.PENDING.value
        md.source_images = [
            {"layer_type": "color", "url": "https://x/color.png"},
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
        ]
        md.attempts = 0
        return md

    @pytest.mark.asyncio
    async def test_successful_generation_marks_ready(self):
        md = self._pending_md()
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md

        vm_client = MagicMock()
        vm_client.submit = AsyncMock(return_value="job-9")
        vm_client.wait_until_complete = AsyncMock(
            return_value=SimpleNamespace(output_filename="sticker_out.ai")
        )
        vm_client.download = AsyncMock(return_value=b"AI-BYTES")

        file_storage = MagicMock()
        file_storage.save = AsyncMock(return_value="manufacturing_data/sticker_out.ai")

        svc = _service(md_repo, file_storage=file_storage, vm_client=vm_client)
        svc._download_source_images = AsyncMock(
            return_value={"color": b"c", "cutline": b"k"}
        )

        await svc.generate("md-1")

        assert md.status == MfgDataStatus.READY.value
        assert md.output_filename == "sticker_out.ai"
        assert md.file_path == "manufacturing_data/sticker_out.ai"
        assert md.file_size == len(b"AI-BYTES")
        assert md.attempts == 1
        assert md.vm_job_id == "job-9"

    @pytest.mark.asyncio
    async def test_vm_failure_marks_failed_with_message(self):
        md = self._pending_md()
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md

        vm_client = MagicMock()
        vm_client.submit = AsyncMock(side_effect=IllustratorVmError("VM 503"))

        svc = _service(md_repo, file_storage=MagicMock(), vm_client=vm_client)
        svc._download_source_images = AsyncMock(return_value={"color": b"c", "cutline": b"k"})

        await svc.generate("md-1")

        assert md.status == MfgDataStatus.FAILED.value
        assert "VM 503" in md.error_message

    @pytest.mark.asyncio
    async def test_not_configured_vm_marks_failed(self):
        md = self._pending_md()
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md

        svc = _service(md_repo, file_storage=MagicMock(), vm_client=None)

        await svc.generate("md-1")
        assert md.status == MfgDataStatus.FAILED.value
        assert "not configured" in md.error_message

    @pytest.mark.asyncio
    async def test_ready_row_is_skipped(self):
        md = self._pending_md()
        md.status = MfgDataStatus.READY.value
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        vm_client = MagicMock()
        vm_client.submit = AsyncMock()

        svc = _service(md_repo, file_storage=MagicMock(), vm_client=vm_client)
        await svc.generate("md-1")

        vm_client.submit.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_skips_when_claim_not_acquired(self):
        # 別ワーカーが既に生成中（claim 失敗）なら VM を叩かず抜ける（二重生成防止）。
        md = self._pending_md()
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        md_repo.claim_for_generation.return_value = False
        vm_client = MagicMock()
        vm_client.submit = AsyncMock()

        svc = _service(md_repo, file_storage=MagicMock(), vm_client=vm_client)
        await svc.generate("md-1")

        vm_client.submit.assert_not_called()
        assert md.attempts == 0  # claim できていないので attempts も加算されない

    @pytest.mark.asyncio
    async def test_download_skips_failed_optional_layer(self):
        # optional(white) の取得が失敗しても例外を投げず、成功したレイヤーのみ返す。
        source_images = [
            {"layer_type": "color", "url": "https://x/color.png"},
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
            {"layer_type": "white", "url": "https://x/white.png"},
        ]

        class _Resp:
            def __init__(self, content: bytes):
                self.content = content

            def raise_for_status(self) -> None:
                return None

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url):
                if "white" in url:
                    raise httpx.ConnectError("refused")
                return _Resp(b"OK")

        svc = _service(AsyncMock())
        with patch.object(mds.httpx, "AsyncClient", _FakeClient):
            images = await svc._download_source_images(
                source_images, {"color", "cutline", "white"}
            )

        assert set(images.keys()) == {"color", "cutline"}


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_resets_to_pending_and_enqueues(self):
        from datetime import UTC, datetime

        md = ManufacturingData(product_code="p", product_type="sticker")
        md.id = "md-1"
        md.status = MfgDataStatus.FAILED.value
        md.error_message = "boom"
        # 通常は DB が埋める列（レスポンス変換に必要）
        md.attempts = 1
        md.created_at = datetime.now(UTC)
        md.updated_at = datetime.now(UTC)
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md

        bg = MagicMock()
        svc = _service(md_repo)
        resp = await svc.retry("md-1", bg)

        assert md.status == MfgDataStatus.PENDING.value
        assert md.error_message is None
        assert resp.status == MfgDataStatus.PENDING.value
        bg.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_missing_raises(self):
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await _service(md_repo).retry("missing", MagicMock())

    @pytest.mark.asyncio
    async def test_retry_rejects_non_failed_row(self):
        # ready 行を retry で巻き戻さない（共有キャッシュ行なので他注文を劣化させる）。
        md = ManufacturingData(product_code="p", product_type="sticker")
        md.id = "md-1"
        md.status = MfgDataStatus.READY.value
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        bg = MagicMock()

        with pytest.raises(ConflictError):
            await _service(md_repo).retry("md-1", bg)

        assert md.status == MfgDataStatus.READY.value  # 状態は変えない
        bg.add_task.assert_not_called()  # 再生成も起動しない


class TestRecovery:
    @pytest.mark.asyncio
    async def test_recover_resets_generating_and_reenqueues(self):
        # 起動時復旧: generating(中断) を pending に戻し、pending/generating を再駆動する。
        generating = ManufacturingData(product_code="p", product_type="sticker")
        generating.id = "md-gen"
        generating.status = MfgDataStatus.GENERATING.value
        pending = ManufacturingData(product_code="q", product_type="sticker")
        pending.id = "md-pend"
        pending.status = MfgDataStatus.PENDING.value

        session = AsyncMock()
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        session_maker = MagicMock(return_value=session_cm)

        repo = AsyncMock()
        repo.find_stranded.return_value = [generating, pending]

        started: list[str] = []

        async def fake_run(md_id: str) -> None:
            started.append(md_id)

        with (
            patch.object(mds, "get_session_maker", return_value=session_maker),
            patch.object(mds, "ManufacturingDataRepository", return_value=repo),
            patch.object(mds, "run_generation", fake_run),
        ):
            await mds.recover_stranded_generations()
            await asyncio.sleep(0.05)  # spawn したタスクを走らせる

        # 中断された generating は claim 可能な pending に戻る
        assert generating.status == MfgDataStatus.PENDING.value
        assert pending.status == MfgDataStatus.PENDING.value
        session.commit.assert_awaited()
        assert set(started) == {"md-gen", "md-pend"}


class TestManufacturingReadinessGate:
    def test_v1_item_is_always_ready(self):
        item = OrderItem(manufacturing_data_id=None)
        assert item.is_manufacturing_ready is True

    def test_required_but_missing_data_not_ready(self):
        item = OrderItem(manufacturing_data_id="md-1")
        item.manufacturing_data = None
        assert item.is_manufacturing_ready is False

    def test_required_and_ready(self):
        item = OrderItem(manufacturing_data_id="md-1")
        md = ManufacturingData(product_code="p", product_type="sticker")
        md.status = MfgDataStatus.READY.value
        item.manufacturing_data = md
        assert item.is_manufacturing_ready is True

    def test_required_but_pending_not_ready(self):
        item = OrderItem(manufacturing_data_id="md-1")
        md = ManufacturingData(product_code="p", product_type="sticker")
        md.status = MfgDataStatus.PENDING.value
        item.manufacturing_data = md
        assert item.is_manufacturing_ready is False
