"""Unit tests for the manufacturing generation worker (app/worker.py).

実 DB が要る部分（取り出しの原子性・リースの失効）は
tests/integration/test_worker_generation.py が受け持つ。ここでは打ち切りの条件と、
多重起動時の降り方だけを見る。
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import worker
from app.config import settings
from app.services.illustrator_vm_client import IllustratorVmClient, VmHealth
from app.services.manufacturing_data_service import GenerationOutcome


@pytest.fixture(autouse=True)
def _no_db_side_effects() -> Iterator[None]:
    """VM の死活確認と滞留の報告は、個別のテストが差し替えない限り何もしない."""
    with (
        patch.object(worker, "check_vm_health", AsyncMock(return_value=True)),
        patch.object(worker, "report_pending", AsyncMock()),
    ):
        yield


def _conn(*, acquired: bool) -> MagicMock:
    """pg_try_advisory_lock の戻り値を差し替えた接続の代役."""
    result = MagicMock()
    result.scalar.return_value = acquired
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=result)
    conn.commit = AsyncMock()
    return conn


def _engine(conn: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.connect = MagicMock(return_value=cm)
    return engine


# リースの中身はワーカーが解釈しない（そのまま run_generation へ渡すだけ）
_LEASE = datetime(2099, 1, 1, tzinfo=UTC)


def _queue(*md_ids: str) -> AsyncMock:
    """取り出すたびに (id, リース) を 1 件ずつ返し、尽きたら None を返すキューの代役."""
    remaining = [(md_id, _LEASE) for md_id in md_ids]
    return AsyncMock(side_effect=lambda _: remaining.pop(0) if remaining else None)


class TestProcessPending:
    @pytest.mark.asyncio
    async def test_drains_until_the_queue_is_empty(self) -> None:
        processed: list[str] = []

        with (
            patch.object(worker, "claim_next_generation", _queue("md-1", "md-2", "md-3")),
            patch.object(
                worker,
                "run_generation",
                AsyncMock(side_effect=lambda md_id, _lease: processed.append(md_id)),
            ),
        ):
            count = await worker.process_pending(max_runtime_seconds=60, max_items=0)

        assert count == 3
        assert processed == ["md-1", "md-2", "md-3"]

    @pytest.mark.asyncio
    async def test_returns_zero_when_nothing_is_queued(self) -> None:
        with (
            patch.object(worker, "claim_next_generation", _queue()),
            patch.object(worker, "run_generation", AsyncMock()) as run,
        ):
            count = await worker.process_pending(max_runtime_seconds=60, max_items=0)

        assert count == 0
        run.assert_not_called()

    @pytest.mark.asyncio
    async def test_stops_at_the_item_limit(self) -> None:
        """上限で打ち切っても取りこぼしにはならない（残りは次回の起動が拾う）."""
        queue = _queue(*[f"md-{i}" for i in range(10)])

        with (
            patch.object(worker, "claim_next_generation", queue),
            patch.object(worker, "run_generation", AsyncMock()),
        ):
            count = await worker.process_pending(max_runtime_seconds=60, max_items=4)

        assert count == 4
        assert queue.await_count == 4  # 上限を超えて取り出しに行かない

    @pytest.mark.asyncio
    async def test_stops_at_the_runtime_limit(self) -> None:
        """実行時間の上限を超えたら、まだ生成待ちが残っていても抜ける."""
        # 開始時刻 → 1周目（上限内なので md-1 を処理）→ 2周目（上限超過で抜ける）
        clock = iter([0.0, 0.0, 999.0])

        with (
            patch("app.worker.time.monotonic", lambda: next(clock)),
            patch.object(worker, "claim_next_generation", _queue("md-1", "md-2")),
            patch.object(worker, "run_generation", AsyncMock()),
        ):
            count = await worker.process_pending(max_runtime_seconds=10, max_items=0)

        assert count == 1

    @pytest.mark.asyncio
    async def test_uses_the_configured_lease(self) -> None:
        """取り出しには設定のリース期限を渡す（短すぎると二重生成になる値）."""
        queue = _queue("md-1")

        with (
            patch.object(worker, "claim_next_generation", queue),
            patch.object(worker, "run_generation", AsyncMock()),
        ):
            await worker.process_pending(max_runtime_seconds=60, max_items=0)

        assert queue.await_args_list[0].args[0] == settings.WORKER_LEASE_SECONDS


    @pytest.mark.asyncio
    async def test_stops_when_the_vm_becomes_unreachable(self) -> None:
        """生成待ちへ戻した（VM に届かなかった）ら、同じ起動では次の行へ進まない."""
        queue = _queue("md-1", "md-2", "md-3")

        with (
            patch.object(worker, "claim_next_generation", queue),
            patch.object(
                worker, "run_generation", AsyncMock(return_value=GenerationOutcome.DEFERRED)
            ) as run,
        ):
            count = await worker.process_pending(max_runtime_seconds=60, max_items=0)

        assert count == 1
        assert run.await_count == 1
        assert queue.await_count == 1  # 残りは取り出さない（試行回数を無駄に消費しない）


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_does_nothing_when_another_worker_holds_the_lock(self) -> None:
        """2 本目は降りる。直列な VM を複数のワーカーで奪い合わないため."""
        conn = _conn(acquired=False)

        with (
            patch.object(worker, "get_engine", return_value=_engine(conn)),
            patch.object(worker, "reclaim_expired_generation_leases", AsyncMock()) as reclaim,
            patch.object(worker, "process_pending", AsyncMock()) as process,
        ):
            count = await worker.run_once()

        assert count == 0
        reclaim.assert_not_called()
        process.assert_not_called()

    @pytest.mark.asyncio
    async def test_reclaims_expired_leases_before_processing(self) -> None:
        calls: list[str] = []
        conn = _conn(acquired=True)

        async def fake_reclaim() -> int:
            calls.append("reclaim")
            return 2

        async def fake_process(**_: Any) -> int:
            calls.append("process")
            return 5

        with (
            patch.object(worker, "get_engine", return_value=_engine(conn)),
            patch.object(worker, "reclaim_expired_generation_leases", fake_reclaim),
            patch.object(worker, "process_pending", fake_process),
        ):
            count = await worker.run_once()

        assert count == 5
        assert calls == ["reclaim", "process"]

    @pytest.mark.asyncio
    async def test_leaves_pending_rows_untouched_when_the_vm_is_unhealthy(self) -> None:
        """VM が NG なら取り出さない。生成待ちは pending のまま復旧を待つ."""
        conn = _conn(acquired=True)

        with (
            patch.object(worker, "check_vm_health", AsyncMock(return_value=False)),
            patch.object(worker, "get_engine", return_value=_engine(conn)),
            patch.object(
                worker, "reclaim_expired_generation_leases", AsyncMock(return_value=0)
            ),
            patch.object(worker, "process_pending", AsyncMock()) as process,
            patch.object(worker, "report_pending", AsyncMock()) as report,
        ):
            count = await worker.run_once()

        assert count == 0
        process.assert_not_called()
        report.assert_awaited_once()  # 滞留の報告は NG のときこそ要る

    @pytest.mark.asyncio
    async def test_checks_the_vm_even_when_another_worker_holds_the_lock(self) -> None:
        """死活確認のログが途絶えたら「ワーカーが止まった」と判断するので、毎回出す."""
        conn = _conn(acquired=False)

        with (
            patch.object(worker, "check_vm_health", AsyncMock(return_value=True)) as check,
            patch.object(worker, "get_engine", return_value=_engine(conn)),
        ):
            await worker.run_once()

        check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_releases_the_lock_even_when_processing_raises(self) -> None:
        conn = _conn(acquired=True)

        with (
            patch.object(worker, "get_engine", return_value=_engine(conn)),
            patch.object(
                worker, "reclaim_expired_generation_leases", AsyncMock(return_value=0)
            ),
            patch.object(worker, "process_pending", AsyncMock(side_effect=RuntimeError("boom"))),
            pytest.raises(RuntimeError),
        ):
            await worker.run_once()

        # 1回目が pg_try_advisory_lock、最後が pg_advisory_unlock
        statements = [str(call.args[0]) for call in conn.execute.await_args_list]
        assert "pg_try_advisory_lock" in statements[0]
        assert "pg_advisory_unlock" in statements[-1]


class TestCheckVmHealth:
    @pytest.fixture(autouse=True)
    def _real_check(self) -> Iterator[None]:
        # モジュール共通の差し替えを外し、本物の check_vm_health を呼ぶ
        with patch.object(worker, "check_vm_health", _REAL_CHECK_VM_HEALTH):
            yield

    @pytest.mark.asyncio
    async def test_logs_ng_with_the_marker(self, caplog: pytest.LogCaptureFixture) -> None:
        client = MagicMock()
        client.health = AsyncMock(return_value=VmHealth(ok=False, detail="ConnectTimeout"))

        with patch.object(IllustratorVmClient, "from_settings", return_value=client):
            ok = await worker.check_vm_health()

        assert ok is False
        assert "illustrator_vm_health status=ng detail=ConnectTimeout" in caplog.text

    @pytest.mark.asyncio
    async def test_logs_ok_with_the_marker(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("INFO")
        client = MagicMock()
        client.health = AsyncMock(return_value=VmHealth(ok=True, detail="healthy"))

        with patch.object(IllustratorVmClient, "from_settings", return_value=client):
            ok = await worker.check_vm_health()

        assert ok is True
        assert "illustrator_vm_health status=ok" in caplog.text

    @pytest.mark.asyncio
    async def test_unconfigured_vm_is_not_a_failure(self) -> None:
        with patch.object(IllustratorVmClient, "from_settings", return_value=None):
            assert await worker.check_vm_health() is True


class TestReportPending:
    @pytest.fixture(autouse=True)
    def _real_report(self) -> Iterator[None]:
        with patch.object(worker, "report_pending", _REAL_REPORT_PENDING):
            yield

    @pytest.mark.asyncio
    async def test_warns_when_the_oldest_pending_row_is_idle_too_long(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        idle = datetime.now(UTC) - timedelta(minutes=settings.WORKER_STALL_ALERT_MINUTES + 5)
        with patch.object(
            worker, "pending_generation_summary", AsyncMock(return_value=(3, idle))
        ):
            await worker.report_pending(processed=0)

        assert "manufacturing_data_stalled pending=3" in caplog.text

    @pytest.mark.asyncio
    async def test_quiet_while_draining_a_backlog(self, caplog: pytest.LogCaptureFixture) -> None:
        """この起動で処理が進んでいるなら、古い行が待っていても止まってはいない."""
        idle = datetime.now(UTC) - timedelta(minutes=settings.WORKER_STALL_ALERT_MINUTES + 5)
        with patch.object(
            worker, "pending_generation_summary", AsyncMock(return_value=(30, idle))
        ):
            await worker.report_pending(processed=4)

        assert "manufacturing_data_stalled" not in caplog.text

    @pytest.mark.asyncio
    async def test_quiet_when_recent(self, caplog: pytest.LogCaptureFixture) -> None:
        recent = datetime.now(UTC) - timedelta(minutes=1)
        with patch.object(
            worker, "pending_generation_summary", AsyncMock(return_value=(1, recent))
        ):
            await worker.report_pending(processed=0)

        assert "manufacturing_data_stalled" not in caplog.text


# autouse の差し替え前に本物を控えておく（TestCheckVmHealth / TestReportPending が使う）
_REAL_CHECK_VM_HEALTH = worker.check_vm_health
_REAL_REPORT_PENDING = worker.report_pending
