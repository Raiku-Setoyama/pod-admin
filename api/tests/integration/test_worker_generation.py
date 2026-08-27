"""Integration tests for the manufacturing generation worker (実DB).

REQ-0052 の受入基準のうち、実際の PostgreSQL が要るものを検証する。

- 生成待ちの行を古い順に取り出し、対象が無くなるまで処理する
- ワーカーを 2 つ同時に起動しても、同じ製造データが二重に処理されない
- 中断されて generating のまま残った行が、ワーカーの起動時に再駆動される

アドバイザリロックも行の確保も PostgreSQL の挙動そのものなので、モックでは検証できない。
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import worker
from app.models.manufacturing_data import MfgDataStatus


async def _insert_row(session: AsyncSession, status: str, *, seq: int) -> str:
    """製造データ行を1件作る.

    created_at を1時間前に置くのは、同じ DB を共有する他のテストが残した行より必ず先に
    並ばせるため（ワーカーは古い順に取り出すので、取り出し順が決定的になる）。
    seq でその中の順序を決める。
    """
    md_id = str(uuid4())
    await session.execute(
        text(
            """
            INSERT INTO manufacturing_data
                (id, product_code, product_type, status, attempts, created_at, updated_at)
            VALUES
                (:id, :code, 'sticker', :status, 0,
                 NOW() - INTERVAL '1 hour' + (:seq * INTERVAL '1 second'), NOW())
            """
        ),
        {"id": md_id, "code": f"WORKER-{md_id[:8]}", "status": status, "seq": seq},
    )
    await session.commit()
    return md_id


async def _status_of(session: AsyncSession, md_id: str) -> str:
    result = await session.execute(
        text("SELECT status FROM manufacturing_data WHERE id = :id"), {"id": md_id}
    )
    return str(result.scalar_one())


async def _cleanup(session: AsyncSession, md_ids: list[str]) -> None:
    await session.execute(
        text("DELETE FROM manufacturing_data WHERE id = ANY(:ids)"), {"ids": md_ids}
    )
    await session.commit()


class TestWorkerAgainstRealDatabase:
    @pytest.mark.asyncio
    async def test_drains_pending_rows_in_created_order(
        self, db_session: AsyncSession
    ) -> None:
        """生成待ちの行を古い順に処理し、対象が無くなったら終了する.

        DB は他のテストと共有しているため、件数ではなく「自分の行がどう扱われたか」で
        検証する。他所の行には触らない（触ると他のテストを壊す）。
        """
        ids = [
            await _insert_row(db_session, MfgDataStatus.PENDING.value, seq=i)
            for i in range(3)
        ]
        mine = set(ids)
        processed: list[str] = []

        async def fake_run(md_id: str) -> None:
            processed.append(md_id)
            if md_id not in mine:
                return  # 他のテストが残した行は状態を変えない
            # 実際の generate() と同じく、処理後は pending から外れる
            await db_session.execute(
                text("UPDATE manufacturing_data SET status = 'ready' WHERE id = :id"),
                {"id": md_id},
            )
            await db_session.commit()

        try:
            with patch.object(worker, "run_generation", fake_run):
                await worker.process_pending(max_runtime_seconds=60, max_items=0)

            # 自分の行はすべて、created_at の昇順で拾われている
            assert [md_id for md_id in processed if md_id in mine] == ids
            for md_id in ids:
                assert await _status_of(db_session, md_id) == MfgDataStatus.READY.value
        finally:
            await _cleanup(db_session, ids)

    @pytest.mark.asyncio
    async def test_second_worker_exits_without_doing_anything(
        self, db_session: AsyncSession
    ) -> None:
        """多重起動: 先にロックを取った 1 本だけが処理し、2 本目は即終了する."""
        ids = [await _insert_row(db_session, MfgDataStatus.PENDING.value, seq=0)]
        entered = asyncio.Event()
        release = asyncio.Event()
        runs = 0

        async def slow_process(**_: Any) -> int:
            nonlocal runs
            runs += 1
            entered.set()
            await release.wait()
            return 1

        try:
            with (
                patch.object(worker, "reclaim_stranded_generations", AsyncMock(return_value=0)),
                patch.object(worker, "process_pending", slow_process),
            ):
                first = asyncio.create_task(worker.run_once())
                await asyncio.wait_for(entered.wait(), timeout=10)

                # 1 本目がロックを保持している間に 2 本目を走らせる。
                # ロックが効いていれば即座に戻る。効いていなければ 2 本目も slow_process に
                # 入って解放待ちで詰まるため、待ち時間を切ってその場で失敗させる
                # （ハングさせない）。
                try:
                    second = await asyncio.wait_for(worker.run_once(), timeout=5)
                finally:
                    release.set()

                assert await asyncio.wait_for(first, timeout=10) == 1

            assert second == 0
            assert runs == 1  # 2 本目は処理に入っていない
        finally:
            await _cleanup(db_session, ids)

    @pytest.mark.asyncio
    async def test_reclaims_rows_left_generating_by_a_crashed_worker(
        self, db_session: AsyncSession
    ) -> None:
        """中断されて generating のまま残った行を pending へ戻し、そのまま処理する."""
        stranded = await _insert_row(db_session, MfgDataStatus.GENERATING.value, seq=0)
        seen_status: list[str] = []

        async def fake_run(md_id: str) -> None:
            if md_id != stranded:
                return  # 他のテストが残した行は状態を変えない
            seen_status.append(await _status_of(db_session, md_id))
            await db_session.execute(
                text("UPDATE manufacturing_data SET status = 'ready' WHERE id = :id"),
                {"id": md_id},
            )
            await db_session.commit()

        try:
            with patch.object(worker, "run_generation", fake_run):
                await worker.run_once()

            # 復旧で pending へ戻ったうえで拾われている
            assert seen_status == [MfgDataStatus.PENDING.value]
            assert await _status_of(db_session, stranded) == MfgDataStatus.READY.value
        finally:
            await _cleanup(db_session, [stranded])
