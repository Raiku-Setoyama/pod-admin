"""Unit tests for ManufacturingDataService and the manufacturing readiness gate."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import settings
from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import OrderItem, OrderItemStatus
from app.services import manufacturing_data_service as mds
from app.services.illustrator_vm_client import (
    IllustratorVmError,
    IllustratorVmUnavailableError,
)
from app.services.manufacturing_data_service import ManufacturingDataService
from app.utils.exceptions import ConflictError, NotFoundError


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
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md

        vm_client = MagicMock()
        vm_client.submit = AsyncMock(side_effect=IllustratorVmError("VM 503"))

        svc = _service(md_repo, file_storage=MagicMock(), vm_client=vm_client)
        svc._download_source_images = AsyncMock(return_value={"color": b"c", "cutline": b"k"})

        await svc.generate("md-1", _LEASE)

        assert md.status == MfgDataStatus.FAILED.value
        assert "VM 503" in md.error_message
        assert md.lease_expires_at is None  # 失敗でも所有権は返す

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

        svc = _service(md_repo, order_repo)
        resp = await svc.regenerate("md-1")

        assert md.status == MfgDataStatus.PENDING.value
        assert md.error_message is None
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


class TestUnreachableVmIsRetried:
    """**VM に届かなかった失敗は終端にしない。**

    到達不能（接続不能・タイムアウト・5xx）は、同じ入力でも VM が戻れば成功する。
    入力の誤りと同じ `failed` に落とすと、VM が数分止まっただけで待ち行列が失敗の山に
    変わり、戻すのに 1 件ずつの手作業が要る。
    """

    def _claimed_md(self, attempts: int = 1) -> Any:
        md = ManufacturingData(product_code="RKSYO-1", product_type="sticker", size="50x50mm")
        md.id = "md-1"
        md.status = MfgDataStatus.GENERATING.value
        md.source_images = [
            {"layer_type": "color", "url": "https://x/color.png"},
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
        ]
        md.attempts = attempts
        md.lease_expires_at = _LEASE
        return md

    def _service_with_vm_error(self, md: Any, error: Exception) -> Any:
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        vm_client = MagicMock()
        vm_client.submit = AsyncMock(side_effect=error)
        svc = _service(md_repo, file_storage=MagicMock(), vm_client=vm_client)
        svc._download_source_images = AsyncMock(
            return_value={"color": b"c", "cutline": b"k"}
        )
        return svc

    @pytest.mark.asyncio
    async def test_unreachable_vm_goes_back_to_the_queue(self) -> None:
        md = self._claimed_md()
        svc = self._service_with_vm_error(
            md, IllustratorVmUnavailableError("connection refused")
        )

        outcome = await svc.generate("md-1", _LEASE)

        assert outcome is mds.GenerationOutcome.RESCHEDULED
        assert md.status == MfgDataStatus.PENDING.value
        # 次にいつ試してよいかを持たせる。持たせないと同じ周回が即座に取り直す。
        assert md.next_attempt_at is not None
        assert md.next_attempt_at > datetime.now(UTC)
        # 何が起きたかは残す（画面と通知が読む）。
        assert "connection refused" in md.error_message
        assert md.lease_expires_at is None  # 所有権は返す

    @pytest.mark.asyncio
    async def test_bad_input_still_fails_at_once(self) -> None:
        """入力の誤りは再試行しても直らない。**回数を使わずその場で終える。**"""
        md = self._claimed_md()
        svc = self._service_with_vm_error(md, IllustratorVmError("422 unsupported size"))

        outcome = await svc.generate("md-1", _LEASE)

        assert outcome is mds.GenerationOutcome.FAILED
        assert md.status == MfgDataStatus.FAILED.value
        assert md.next_attempt_at is None

    @pytest.mark.asyncio
    async def test_a_dropped_connection_while_fetching_layers_is_retried(self) -> None:
        """元データの取得先が落ちた場合も、入力の誤りではない."""
        md = self._claimed_md()
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        svc = _service(md_repo, file_storage=MagicMock(), vm_client=MagicMock())
        svc._download_source_images = AsyncMock(
            side_effect=httpx.ConnectError("asset host is down")
        )

        outcome = await svc.generate("md-1", _LEASE)

        assert outcome is mds.GenerationOutcome.RESCHEDULED
        assert md.status == MfgDataStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_it_gives_up_once_the_attempt_cap_is_reached(self) -> None:
        """**無限には粘らない。** 上限まで来たら failed にして人の目に入れる."""
        md = self._claimed_md(attempts=settings.MFG_MAX_GENERATION_ATTEMPTS)
        svc = self._service_with_vm_error(
            md, IllustratorVmUnavailableError("connection refused")
        )

        outcome = await svc.generate("md-1", _LEASE)

        assert outcome is mds.GenerationOutcome.FAILED
        assert md.status == MfgDataStatus.FAILED.value
        # 上限で諦めたことが読み取れる文言にする（入力エラーと区別が付かないと困る）。
        assert str(settings.MFG_MAX_GENERATION_ATTEMPTS) in md.error_message
        assert "connection refused" in md.error_message

    @pytest.mark.asyncio
    async def test_a_lost_lease_does_not_stop_the_run(self) -> None:
        """リースを失っていたら、その行は別のワーカーのものである。周回は続けてよい."""
        md = self._claimed_md()
        md_repo = AsyncMock()
        md_repo.find_by_id.return_value = md
        md_repo.finish_generation.return_value = False  # 書き戻せなかった
        vm_client = MagicMock()
        vm_client.submit = AsyncMock(
            side_effect=IllustratorVmUnavailableError("connection refused")
        )
        svc = _service(md_repo, file_storage=MagicMock(), vm_client=vm_client)
        svc._download_source_images = AsyncMock(
            return_value={"color": b"c", "cutline": b"k"}
        )

        assert await svc.generate("md-1", _LEASE) is mds.GenerationOutcome.FAILED

    def test_the_wait_grows_with_each_attempt_and_then_stops(self) -> None:
        """待ち時間は倍々に伸び、上限で止まる（落ちている VM を叩き続けない）."""
        delays = [
            ManufacturingDataService._retry_delay(attempt) for attempt in range(1, 12)
        ]

        assert delays[0] == settings.MFG_RETRY_BASE_SECONDS
        assert delays[1] == settings.MFG_RETRY_BASE_SECONDS * 2
        # 単調非減少で、上限を超えない
        assert delays == sorted(delays)
        assert max(delays) == settings.MFG_RETRY_MAX_SECONDS

    @pytest.mark.parametrize(
        ("error", "retryable"),
        [
            pytest.param(IllustratorVmUnavailableError("5xx"), True, id="VMが5xxを返す"),
            pytest.param(httpx.ConnectError("refused"), True, id="接続できない"),
            pytest.param(httpx.ReadTimeout("slow"), True, id="応答が返らない"),
            pytest.param(IllustratorVmError("422"), False, id="入力が悪い"),
            pytest.param(ValueError("bug"), False, id="想定外の不具合"),
        ],
    )
    def test_only_reachability_failures_are_retried(
        self, error: Exception, retryable: bool
    ) -> None:
        """**判定は型で行う**（文言で見ると VM 側の変更で静かに壊れる）."""
        assert ManufacturingDataService._is_retryable(error) is retryable


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
