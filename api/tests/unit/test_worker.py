"""Unit tests for the manufacturing generation worker (app/worker.py).

REQ-0052 の受入基準のうち、次を検証する。

- 生成待ちの行を処理し、対象が無くなると終了すること
- 件数・実行時間の上限で打ち切り、残りを次回に委ねること
- アドバイザリロックを取れなければ何もせずに終わること（多重起動の単一化）
- ロックを取れた場合は、中断された生成を pending へ戻してから処理を始めること
- 処理しても pending から外れない行で無限ループしないこと
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import worker


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


class TestProcessPending:
    @pytest.mark.asyncio
    async def test_drains_until_no_pending_rows_remain(self) -> None:
        """処理するたびに行が pending から外れ、空になったら終了する."""
        remaining = ["md-1", "md-2", "md-3"]
        processed_ids: list[str] = []

        async def fake_run(md_id: str) -> None:
            processed_ids.append(md_id)
            remaining.remove(md_id)

        with (
            patch.object(
                worker,
                "next_pending_generation_id",
                AsyncMock(side_effect=lambda exclude: next(
                    (i for i in remaining if i not in exclude), None
                )),
            ),
            patch.object(worker, "run_generation", fake_run),
        ):
            processed = await worker.process_pending(max_runtime_seconds=60, max_items=0)

        assert processed == 3
        assert processed_ids == ["md-1", "md-2", "md-3"]  # 古い順に処理する

    @pytest.mark.asyncio
    async def test_returns_zero_when_nothing_is_pending(self) -> None:
        with (
            patch.object(worker, "next_pending_generation_id", AsyncMock(return_value=None)),
            patch.object(worker, "run_generation", AsyncMock()) as run,
        ):
            processed = await worker.process_pending(max_runtime_seconds=60, max_items=0)

        assert processed == 0
        run.assert_not_called()

    @pytest.mark.asyncio
    async def test_stops_at_the_item_limit(self) -> None:
        """上限で打ち切っても取りこぼしにはならない（残りは pending のまま）."""
        remaining = [f"md-{i}" for i in range(10)]

        async def fake_run(md_id: str) -> None:
            remaining.remove(md_id)

        with (
            patch.object(
                worker,
                "next_pending_generation_id",
                AsyncMock(side_effect=lambda exclude: next(
                    (i for i in remaining if i not in exclude), None
                )),
            ),
            patch.object(worker, "run_generation", fake_run),
        ):
            processed = await worker.process_pending(max_runtime_seconds=60, max_items=4)

        assert processed == 4
        assert len(remaining) == 6  # 残りは次回の起動が拾う

    @pytest.mark.asyncio
    async def test_stops_at_the_runtime_limit(self) -> None:
        """実行時間の上限を超えたら、まだ pending が残っていても抜ける."""
        # 開始時刻 → 1周目（上限内なので md-1 を処理）→ 2周目（上限超過で抜ける）
        clock = iter([0.0, 0.0, 999.0])

        async def fake_run(md_id: str) -> None:
            return None

        with (
            patch("app.worker.time.monotonic", lambda: next(clock)),
            patch.object(worker, "next_pending_generation_id", AsyncMock(return_value="md-1")),
            patch.object(worker, "run_generation", fake_run),
        ):
            processed = await worker.process_pending(max_runtime_seconds=10, max_items=0)

        assert processed == 1

    @pytest.mark.asyncio
    async def test_does_not_loop_forever_on_a_row_that_stays_pending(self) -> None:
        """確定に失敗して pending のままになった行を、延々と掴み続けない."""
        with (
            patch.object(
                worker,
                "next_pending_generation_id",
                AsyncMock(side_effect=lambda exclude: None if "md-stuck" in exclude else "md-stuck"),
            ),
            patch.object(worker, "run_generation", AsyncMock()) as run,
        ):
            processed = await worker.process_pending(max_runtime_seconds=60, max_items=0)

        assert processed == 1
        run.assert_awaited_once_with("md-stuck")


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_does_nothing_when_the_lock_is_held_by_another_worker(self) -> None:
        """2 本目はロックを取れず、復旧も処理もせずに戻る."""
        conn = _conn(acquired=False)

        with (
            patch.object(worker, "get_engine", return_value=_engine(conn)),
            patch.object(worker, "reclaim_stranded_generations", AsyncMock()) as reclaim,
            patch.object(worker, "process_pending", AsyncMock()) as process,
        ):
            processed = await worker.run_once()

        assert processed == 0
        reclaim.assert_not_called()
        process.assert_not_called()

    @pytest.mark.asyncio
    async def test_reclaims_stranded_rows_before_processing(self) -> None:
        """中断された生成を pending へ戻してから取り出しを始める."""
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
            patch.object(worker, "reclaim_stranded_generations", fake_reclaim),
            patch.object(worker, "process_pending", fake_process),
        ):
            processed = await worker.run_once()

        assert processed == 5
        assert calls == ["reclaim", "process"]

    @pytest.mark.asyncio
    async def test_releases_the_lock_even_when_processing_raises(self) -> None:
        conn = _conn(acquired=True)

        with (
            patch.object(worker, "get_engine", return_value=_engine(conn)),
            patch.object(worker, "reclaim_stranded_generations", AsyncMock(return_value=0)),
            patch.object(worker, "process_pending", AsyncMock(side_effect=RuntimeError("boom"))),
            pytest.raises(RuntimeError),
        ):
            await worker.run_once()

        # 1回目が pg_try_advisory_lock、最後が pg_advisory_unlock
        statements = [str(call.args[0]) for call in conn.execute.await_args_list]
        assert "pg_try_advisory_lock" in statements[0]
        assert "pg_advisory_unlock" in statements[-1]
