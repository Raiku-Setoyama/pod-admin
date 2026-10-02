"""Unit tests for ManufacturingDataService and the manufacturing readiness gate."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import settings
from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import OrderItem, OrderItemStatus
from app.services import manufacturing_data_service as mds
from app.services.illustrator_vm_client import IllustratorVmError, IllustratorVmUnavailableError
from app.services.manufacturing_data_service import ManufacturingDataService
from app.utils.exceptions import (
    ConflictError,
    NotFoundError,
    TransientDependencyError,
)


def _v2_item(
    *,
    product_code: str="RKSYO-1",
    product_type: str="acrylic_keychain",
    size: str="50x50mm",
    layers: Any=("color", "cutline"),
) -> Any:
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


def _service(md_repo: Any, order_repo: Any=None, **kwargs: Any) -> Any:
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
    async def test_creates_new_row_and_requests_generation(self) -> None:
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
        # 未 ready のため統合ステータスは発注準備中
        assert item.status == OrderItemStatus.PREPARING_ORDER.value
        # keychain(color+cutline, white なし) は variant clear で照会される
        # find_by_cache_key(order_source_id, product_code, size, variant)
        called = md_repo.find_by_cache_key.call_args
        assert called.args == ("src-1", "RKSYO-1", "50x50mm", "clear")

    @pytest.mark.asyncio
    async def test_reuses_ready_cache_without_generation(self) -> None:
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
        # キャッシュが ready のため統合ステータスは発注済みへ昇格
        assert item.status == OrderItemStatus.ORDERED.value
        md_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_cache_is_reset_and_regenerated(self) -> None:
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
    async def test_unmappable_product_creates_failed_row_no_generation(self) -> None:
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
    async def test_v1_items_are_ignored(self) -> None:
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
    async def test_insert_row_recovers_existing_on_conflict_marks_not_created(self) -> None:
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
            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: Any) -> bool:
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


# 取り出しが返すリースの代役（generate はこの値を書き戻しの条件に使うだけ）
_LEASE = datetime(2099, 1, 1, tzinfo=UTC)


class TestGenerateDriver:
    def _claimed_md(self) -> Any:
        """ワーカーが取り出した直後の行（generating・試行回数は加算済み・リース保持）."""
        md = ManufacturingData(product_code="RKSYO-1", product_type="sticker", size="50x50mm")
        md.id = "md-1"
        md.status = MfgDataStatus.GENERATING.value
        md.source_images = [
            {"layer_type": "color", "url": "https://x/color.png"},
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
        ]
        md.attempts = 1
        md.lease_expires_at = _LEASE
        return md

    async def _generate_with_submit_error(
        self, md: Any, exc: Exception, *, finish_ok: bool = True
    ) -> tuple[Any, Any]:
        """VM への投入が exc で失敗する状況で generate を 1 回走らせ、(svc, 結果) を返す."""
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        if not finish_ok:
            md_repo.finish_generation.return_value = False  # リースを失っている

        vm_client = MagicMock()
        vm_client.submit = AsyncMock(side_effect=exc)

        svc = _service(md_repo, file_storage=MagicMock(), vm_client=vm_client)
        svc._download_source_images = AsyncMock(return_value={"color": b"c", "cutline": b"k"})
        return svc, await svc.generate("md-1", _LEASE)

    @pytest.mark.asyncio
    async def test_successful_generation_marks_ready(self) -> None:
        md = self._claimed_md()
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

        await svc.generate("md-1", _LEASE)

        assert md.status == MfgDataStatus.READY.value
        assert md.output_filename == "sticker_out.ai"
        assert md.file_path == "manufacturing_data/sticker_out.ai"
        assert md.file_size == len(b"AI-BYTES")
        assert md.vm_job_id == "job-9"
        assert md.lease_expires_at is None  # 処理が終わったので所有権を返す
        # VM 必須の order_id に製造データ行の id を渡す（トレーサビリティ）
        assert vm_client.submit.call_args.kwargs["order_id"] == md.id
        # 生成完了を参照明細へ波及（発注準備中→発注済み）
        svc._order_repo.sync_item_status_for_manufacturing_data.assert_awaited_once_with(
            "md-1", ready=True
        )

    @pytest.mark.asyncio
    async def test_vm_failure_marks_failed_with_message(self) -> None:
        md = self._claimed_md()
        await self._generate_with_submit_error(md, IllustratorVmError("VM 503"))

        assert md.status == MfgDataStatus.FAILED.value
        assert "VM 503" in md.error_message
        assert md.lease_expires_at is None  # 失敗でも所有権は返す

    @pytest.mark.asyncio
    async def test_unreachable_vm_defers_to_pending_instead_of_failing(self) -> None:
        """VM に届かないのは入力の誤りではない。failed にせず生成待ちへ戻す.

        2026-09-27〜10-02 の障害では failed に確定させたため、VM の復旧後も
        人が 1 件ずつ再生成を押すまで発注が止まったままになった。
        """
        md = self._claimed_md()
        md.vm_job_id = "stale-job"
        svc, outcome = await self._generate_with_submit_error(
            md, IllustratorVmUnavailableError("VM POST /api/process failed: ConnectTimeout")
        )

        assert outcome is mds.GenerationOutcome.DEFERRED
        assert md.status == MfgDataStatus.PENDING.value
        assert md.vm_job_id is None
        assert "ConnectTimeout" in md.error_message
        assert md.lease_expires_at is None
        # 発注可否は変えない（生成待ちのまま）
        svc._order_repo.sync_item_status_for_manufacturing_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_unreachable_vm_fails_after_the_attempt_limit(self) -> None:
        md = self._claimed_md()
        md.attempts = settings.WORKER_MAX_GENERATION_ATTEMPTS
        _, outcome = await self._generate_with_submit_error(
            md, IllustratorVmUnavailableError("down")
        )

        assert outcome is mds.GenerationOutcome.FAILED
        assert md.status == MfgDataStatus.FAILED.value
        assert "接続できませんでした" in md.error_message

    @pytest.mark.asyncio
    async def test_deferred_row_is_given_a_retry_time(self) -> None:
        """戻す行には次に試す時刻を入れる（先頭詰まりを防ぐ）.

        取り出しは created_at の昇順なので、時刻を入れずに戻すと同じ行が毎回いちばん先に
        選ばれ、その 1 行が上限を使い切るまで後ろの行が 1 件も処理されない。
        """
        md = self._claimed_md()
        before = datetime.now(UTC)
        _, outcome = await self._generate_with_submit_error(
            md, IllustratorVmUnavailableError("down")
        )

        assert outcome is mds.GenerationOutcome.DEFERRED
        assert md.next_attempt_at is not None
        # 1 回目（attempts=1）は base そのぶんだけ先。
        assert md.next_attempt_at >= before + timedelta(seconds=settings.MFG_RETRY_BASE_SECONDS)

    @pytest.mark.asyncio
    async def test_retry_delay_doubles_and_stops_at_the_cap(self) -> None:
        delay = ManufacturingDataService._retry_delay
        assert delay(1) == settings.MFG_RETRY_BASE_SECONDS
        assert delay(2) == settings.MFG_RETRY_BASE_SECONDS * 2
        assert delay(3) == settings.MFG_RETRY_BASE_SECONDS * 4
        # 試行回数がいくら増えても上限を超えない（SQL 側と違い overflow はしないが、
        # 落ちている相手を何日も待たせない意味で上限を効かせる）。
        assert delay(99) == settings.MFG_RETRY_MAX_SECONDS

    @pytest.mark.asyncio
    async def test_unavailable_storage_defers_but_keeps_the_run_going(self) -> None:
        """保存先が一時的に落ちた行も生成待ちへ戻す。**ただし周回は続ける.**

        VM と違い、落ちているのはその行が参照している先だけかもしれない。VM と同じ扱いに
        すると 1 行の都合で起動まるごとを捨てることになる。
        """
        md = self._claimed_md()
        _, outcome = await self._generate_with_submit_error(
            md, TransientDependencyError("GCS is unavailable (upload): 503")
        )

        assert outcome is mds.GenerationOutcome.RESCHEDULED
        assert md.status == MfgDataStatus.PENDING.value
        assert md.next_attempt_at is not None
        assert "依存先に接続できず再試行待ち" in md.error_message

    @pytest.mark.asyncio
    async def test_unreachable_asset_host_defers(self) -> None:
        """元データの配信元に届かない場合も恒久的な失敗にしない.

        この層は元データの取得だけ自分で httpx を呼ぶので、翻訳する境界が無い
        （is_transient_failure がここで境界を兼ねる）。
        """
        md = self._claimed_md()
        _, outcome = await self._generate_with_submit_error(
            md, httpx.ConnectError("asset host is down")
        )

        assert outcome is mds.GenerationOutcome.RESCHEDULED
        assert md.status == MfgDataStatus.PENDING.value

    @pytest.mark.parametrize(
        ("error", "transient"),
        [
            pytest.param(TransientDependencyError("GCS 503"), True, id="保存先が落ちている"),
            pytest.param(httpx.ConnectError("refused"), True, id="配信元に繋がらない"),
            pytest.param(httpx.ReadTimeout("slow"), True, id="配信元が応答しない"),
            pytest.param(
                httpx.HTTPStatusError(
                    "boom", request=httpx.Request("GET", "https://x"),
                    response=httpx.Response(503),
                ),
                True,
                id="配信元が5xx",
            ),
            pytest.param(
                httpx.HTTPStatusError(
                    "nope", request=httpx.Request("GET", "https://x"),
                    response=httpx.Response(404),
                ),
                False,
                id="URLが誤っている（4xx）",
            ),
            pytest.param(ValueError("bad png"), False, id="入力が壊れている"),
        ],
    )
    def test_is_transient_failure_classification(
        self, error: Exception, transient: bool
    ) -> None:
        assert mds.is_transient_failure(error) is transient

    @pytest.mark.asyncio
    async def test_lost_lease_while_deferring_is_skipped(self) -> None:
        md = self._claimed_md()
        _, outcome = await self._generate_with_submit_error(
            md, IllustratorVmUnavailableError("down"), finish_ok=False
        )

        assert outcome is mds.GenerationOutcome.SKIPPED
        assert md.status == MfgDataStatus.GENERATING.value  # 他のワーカーの行を書き換えない

    @pytest.mark.asyncio
    async def test_not_configured_vm_marks_failed(self) -> None:
        md = self._claimed_md()
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md

        svc = _service(md_repo, file_storage=MagicMock(), vm_client=None)

        await svc.generate("md-1", _LEASE)
        assert md.status == MfgDataStatus.FAILED.value
        assert "not configured" in md.error_message

    @pytest.mark.parametrize(
        "status",
        [
            pytest.param(MfgDataStatus.READY.value, id="既に完成している"),
            pytest.param(MfgDataStatus.PENDING.value, id="まだ確保されていない"),
            pytest.param(MfgDataStatus.FAILED.value, id="確保されずに失敗で残っている"),
        ],
    )
    @pytest.mark.asyncio
    async def test_skips_a_row_that_is_not_claimed(self, status: str) -> None:
        """確保済み（generating）の行以外は触らない.

        generate は自分では確保しない。確保はキューからの取り出しが 1 文で済ませており、
        ここで再度確保しようとすると自分の取り出しと衝突する。
        """
        md = self._claimed_md()
        md.status = status
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        vm_client = MagicMock()
        vm_client.submit = AsyncMock()

        svc = _service(md_repo, file_storage=MagicMock(), vm_client=vm_client)
        await svc.generate("md-1", _LEASE)

        vm_client.submit.assert_not_called()
        assert md.status == status  # 状態も変えない

    @pytest.mark.asyncio
    async def test_download_skips_failed_optional_layer(self) -> None:
        # optional(white) の取得が失敗しても例外を投げず、成功したレイヤーのみ返す。
        source_images = [
            {"layer_type": "color", "url": "https://x/color.png"},
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
            {"layer_type": "white", "url": "https://x/white.png"},
        ]

        class _StreamResp:
            def __init__(self, chunks: Any) -> None:
                self._chunks = chunks

            def raise_for_status(self) -> None:
                return None

            async def aiter_bytes(self) -> AsyncIterator[Any]:
                for c in self._chunks:
                    yield c

        class _StreamCtx:
            def __init__(self, resp: Any) -> None:
                self._resp = resp

            async def __aenter__(self) -> Any:
                return self._resp

            async def __aexit__(self, *exc: Any) -> bool:
                return False

        class _FakeClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: Any) -> bool:
                return False

            def stream(self, method: Any, url: Any) -> Any:
                if "white" in url:
                    raise httpx.ConnectError("refused")
                return _StreamCtx(_StreamResp([b"OK"]))

        # host "x" は許可リストで素通し（このテストの主眼はレイヤー欠落の耐性）。
        svc = _service(AsyncMock(), allowed_source_hosts=frozenset({"x"}))
        with patch("app.services.manufacturing_data_service.httpx.AsyncClient", _FakeClient):
            images = await svc._download_source_images(
                source_images, {"color", "cutline", "white"}
            )

        assert set(images.keys()) == {"color", "cutline"}


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_clears_the_pending_retry_schedule(self) -> None:
        """**人が押した再生成は待たせない。**

        生成待ちへ戻した行は next_attempt_at を持ち、取り出しはその時刻まで飛ばす。
        人の操作でここを消し忘れると、画面上は「生成待ち」なのに最長 1 時間動かない
        （押しても何も起きないように見える）。
        """
        md = ManufacturingData(product_code="p", product_type="sticker")
        md.id = "md-1"
        md.status = MfgDataStatus.FAILED.value
        md.error_message = "依存先に接続できず再試行待ち: boom"
        md.attempts = 3
        md.next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
        md.lease_expires_at = None
        md.created_at = datetime.now(UTC)
        md.updated_at = datetime.now(UTC)
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md

        svc = _service(md_repo)
        await svc.retry("md-1")

        assert md.status == MfgDataStatus.PENDING.value
        assert md.next_attempt_at is None  # 次の取り出しで拾われる
        assert md.attempts == 0
        assert md.error_message is None

    @pytest.mark.asyncio
    async def test_retry_resets_to_pending_without_generating_inline(self) -> None:
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

        svc = _service(md_repo)
        resp = await svc.retry("md-1")

        # 行を pending へ戻すだけ。生成はワーカーが別プロセスで拾う（ADR-0026）。
        assert md.status == MfgDataStatus.PENDING.value
        assert md.error_message is None
        assert resp.status == MfgDataStatus.PENDING.value
        # 人が再駆動したので、VM 不達の試行回数は数え直す
        assert md.attempts == 0

    @pytest.mark.asyncio
    async def test_retry_missing_raises(self) -> None:
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await _service(md_repo).retry("missing")

    @pytest.mark.asyncio
    async def test_retry_rejects_non_failed_row(self) -> None:
        # ready 行を retry で巻き戻さない（共有キャッシュ行なので他注文を劣化させる）。
        md = ManufacturingData(product_code="p", product_type="sticker")
        md.id = "md-1"
        md.status = MfgDataStatus.READY.value
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md

        with pytest.raises(ConflictError):
            await _service(md_repo).retry("md-1")

        assert md.status == MfgDataStatus.READY.value  # 状態は変えない


class TestRegenerate:
    """製造データ GUI 再作成（regenerate）の前提条件・波及のテスト."""

    def _md(self, status: Any=MfgDataStatus.READY.value) -> Any:
        from datetime import UTC, datetime

        md = ManufacturingData(product_code="p", product_type="sticker")
        md.id = "md-1"
        md.status = status
        md.attempts = 1
        md.created_at = datetime.now(UTC)
        md.updated_at = datetime.now(UTC)
        return md

    @pytest.mark.asyncio
    async def test_regenerate_demotes_and_enqueues_when_pre_manufacturing(self) -> None:
        # 参照明細が全て発注準備中/発注済みなら再作成可。ready 行を pending に戻し、
        # 発注済み明細を発注準備中へ戻す（demote）。生成そのものはワーカーが拾う。
        md = self._md(MfgDataStatus.READY.value)
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        order_repo = AsyncMock()
        order_repo.has_manufacturing_or_delivered_items.return_value = False

        md.attempts = 3
        svc = _service(md_repo, order_repo)
        resp = await svc.regenerate("md-1")

        assert md.status == MfgDataStatus.PENDING.value
        assert md.error_message is None
        assert md.attempts == 0  # 作り直しなので VM 不達の試行回数も数え直す
        # 降格は 1 回だけ（生成の起動もこの 1 回に対応する）
        order_repo.sync_item_status_for_manufacturing_data.assert_awaited_once_with(
            "md-1", ready=False
        )
        assert resp.status == MfgDataStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_regenerate_allows_failed_row(self) -> None:
        md = self._md(MfgDataStatus.FAILED.value)
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        order_repo = AsyncMock()
        order_repo.has_manufacturing_or_delivered_items.return_value = False

        resp = await _service(md_repo, order_repo).regenerate("md-1")

        assert md.status == MfgDataStatus.PENDING.value
        assert resp.status == MfgDataStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_regenerate_blocked_when_shared_with_manufacturing(self) -> None:
        # 共有明細に製造中があれば、その注文の完成データ保護のため再作成不可。
        md = self._md(MfgDataStatus.READY.value)
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        order_repo = AsyncMock()
        order_repo.has_manufacturing_or_delivered_items.return_value = True

        svc = _service(md_repo, order_repo)
        with pytest.raises(ConflictError):
            await svc.regenerate("md-1")

        assert md.status == MfgDataStatus.READY.value  # 状態は変えない
        order_repo.sync_item_status_for_manufacturing_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_regenerate_blocked_when_shared_with_delivered(self) -> None:
        md = self._md(MfgDataStatus.READY.value)
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        order_repo = AsyncMock()
        order_repo.has_manufacturing_or_delivered_items.return_value = True

        with pytest.raises(ConflictError):
            await _service(md_repo, order_repo).regenerate("md-1")

    @pytest.mark.asyncio
    async def test_regenerate_rejects_generating(self) -> None:
        # 生成中は進行中ジョブと競合させないため、ゲート判定前に即拒否する。
        md = self._md(MfgDataStatus.GENERATING.value)
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        order_repo = AsyncMock()

        svc = _service(md_repo, order_repo)
        with pytest.raises(ConflictError):
            await svc.regenerate("md-1")

        order_repo.has_manufacturing_or_delivered_items.assert_not_called()

    @pytest.mark.asyncio
    async def test_regenerate_missing_raises(self) -> None:
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await _service(md_repo).regenerate("missing")


class TestRecovery:
    @pytest.mark.asyncio
    async def test_reclaim_returns_the_number_of_expired_leases(self) -> None:
        # リースが切れた generating を pending へ戻し、戻した件数を返す。
        # 再駆動そのものは行わない（ワーカーが通常の取り出しで拾う）。
        session = AsyncMock()
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        session_maker = MagicMock(return_value=session_cm)

        repo = AsyncMock()
        repo.reclaim_expired_leases.return_value = 2

        with (
            patch.object(mds, "get_session_maker", return_value=session_maker),
            patch.object(mds, "ManufacturingDataRepository", return_value=repo),
        ):
            reclaimed = await mds.reclaim_expired_generation_leases()

        # pending へ戻すだけ。再駆動は通常の取り出しが拾う。
        assert reclaimed == 2
        session.commit.assert_awaited()


class TestManufacturingReadinessGate:
    def test_v1_item_is_always_ready(self) -> None:
        item = OrderItem(manufacturing_data_id=None)
        assert item.is_manufacturing_ready is True

    def test_required_but_missing_data_not_ready(self) -> None:
        item = OrderItem(manufacturing_data_id="md-1")
        item.manufacturing_data = None
        assert item.is_manufacturing_ready is False

    def test_required_and_ready(self) -> None:
        item = OrderItem(manufacturing_data_id="md-1")
        md = ManufacturingData(product_code="p", product_type="sticker")
        md.status = MfgDataStatus.READY.value
        item.manufacturing_data = md
        assert item.is_manufacturing_ready is True

    def test_required_but_pending_not_ready(self) -> None:
        item = OrderItem(manufacturing_data_id="md-1")
        md = ManufacturingData(product_code="p", product_type="sticker")
        md.status = MfgDataStatus.PENDING.value
        item.manufacturing_data = md
        assert item.is_manufacturing_ready is False
