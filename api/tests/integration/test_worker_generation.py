"""Integration tests for the manufacturing generation worker (実DB).

REQ-0052 の受入基準のうち、実際の PostgreSQL が要るものを検証する。

キューからの取り出し（``claim_next_generation``）とリースの失効は、どちらも
PostgreSQL の挙動そのもの（``FOR UPDATE SKIP LOCKED`` / サーバ時刻での期限比較）に
乗っているため、モックでは検証できない。

とくに次の 2 点を、**アドバイザリロックを外した状態で**確かめる。
ロックはスループットの都合であって正しさの条件ではない、という設計が本当か確認するためである。

- 同時に取り出しても、同じ行を 2 つのワーカーが掴まない
- 期限内のリースを持つ行は、復旧処理が触らない
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import worker
from app.config import settings
from app.models.manufacturing_data import MfgDataStatus
from app.repositories.manufacturing_data_repository import ManufacturingDataRepository
from app.services.manufacturing_data_service import (
    GenerationOutcome,
    claim_next_generation,
    reclaim_expired_generation_leases,
)


async def _insert_row(
    session: AsyncSession,
    status: str,
    *,
    seq: int = 0,
    lease_offset_seconds: int | None = None,
    next_attempt_offset_seconds: int | None = None,
) -> str:
    """製造データ行を1件作る.

    created_at を1時間前に置くのは、同じ DB を共有する他のテストが残した行より必ず先に
    並ばせるため（取り出しは古い順なので、取り出し順が決定的になる）。seq でその中の順序を決める。

    ``lease_offset_seconds`` は現在時刻からの相対でリース期限を打つ。負なら期限切れ。
    ``next_attempt_offset_seconds`` は同じく再試行の予定時刻。負なら「もう取り出してよい」。
    """
    md_id = str(uuid4())
    lease = (
        "NULL"
        if lease_offset_seconds is None
        else f"NOW() + ({lease_offset_seconds} * INTERVAL '1 second')"
    )
    next_attempt = (
        "NULL"
        if next_attempt_offset_seconds is None
        else f"NOW() + ({next_attempt_offset_seconds} * INTERVAL '1 second')"
    )
    await session.execute(
        text(
            f"""
            INSERT INTO manufacturing_data
                (id, product_code, product_type, status, attempts,
                 lease_expires_at, next_attempt_at, created_at, updated_at)
            VALUES
                (:id, :code, 'sticker', :status, 0, {lease}, {next_attempt},
                 NOW() - INTERVAL '1 hour' + (:seq * INTERVAL '1 second'), NOW())
            """  # noqa: S608 - lease/next_attempt は上のリテラル 2 択のみ。外部入力は入らない
        ),
        {"id": md_id, "code": f"WORKER-{md_id[:8]}", "status": status, "seq": seq},
    )
    await session.commit()
    return md_id


async def _row(session: AsyncSession, md_id: str) -> Any:
    result = await session.execute(
        text(
            "SELECT status, attempts, lease_expires_at FROM manufacturing_data "
            "WHERE id = :id"
        ),
        {"id": md_id},
    )
    return result.fetchone()


async def _retry_row(session: AsyncSession, md_id: str) -> Any:
    """再試行まわりの列だけを読む（``_row`` を広げると既存の分解代入が全部壊れる）."""
    result = await session.execute(
        text(
            "SELECT status, attempts, next_attempt_at, error_message "
            "FROM manufacturing_data WHERE id = :id"
        ),
        {"id": md_id},
    )
    return result.fetchone()


async def _cleanup(session: AsyncSession, md_ids: list[str]) -> None:
    await session.execute(
        text("DELETE FROM manufacturing_data WHERE id = ANY(:ids)"), {"ids": md_ids}
    )
    await session.commit()


async def _finish(
    session: AsyncSession, md_id: str, lease_token: Any, status: str
) -> bool:
    """リポジトリの条件付き書き戻しを、テスト用のセッションで呼ぶ."""
    applied = await ManufacturingDataRepository(session).finish_generation(
        md_id, lease_token=lease_token, values={"status": status}
    )
    await session.commit()
    return applied


@pytest.fixture
async def quiet_queue(db_session: AsyncSession) -> AsyncIterator[None]:
    """このテストが作る行だけがキューに並ぶようにする.

    DB は他のテストと共有しており、前の実行が残した pending 行が混ざる。取り出しは
    古い順なので、それらが先に返ってきて「自分が入れた行が返る」という前提が崩れる。

    よそのキューを消さずに退避させたいので、リースだけ打って一時的に取り出し対象から
    外し、テストが終わったら元に戻す。
    """
    parked = await db_session.execute(
        text(
            "UPDATE manufacturing_data SET status = 'generating', "
            "lease_expires_at = NOW() + INTERVAL '1 day' "
            "WHERE status = 'pending' RETURNING id"
        )
    )
    parked_ids = list(parked.scalars().all())
    await db_session.commit()
    try:
        yield
    finally:
        if parked_ids:
            await db_session.execute(
                text(
                    "UPDATE manufacturing_data SET status = 'pending', "
                    "lease_expires_at = NULL WHERE id = ANY(:ids)"
                ),
                {"ids": parked_ids},
            )
            await db_session.commit()


class TestClaimNextGeneration:
    """キューからの取り出しが、1 文で「選ぶ・確保する・リースを打つ」を済ませること."""

    @pytest.mark.asyncio
    async def test_claim_marks_the_row_generating_with_a_lease(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        md_id = await _insert_row(db_session, MfgDataStatus.PENDING.value)
        try:
            claimed = await claim_next_generation(1800)

            assert claimed is not None
            assert claimed[0] == md_id
            status, attempts, lease = await _row(db_session, md_id)
            assert status == MfgDataStatus.GENERATING.value
            assert attempts == 1  # 取り出しが試行回数も進める
            assert lease is not None  # 所有権を持っている
            assert claimed[1] == lease  # 返した期限が、行に書かれた期限と一致する
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_lease_expires_after_the_requested_number_of_seconds(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """**単位と時計の取り違えを検知する。**設計全体がこの値の正しさに乗っている."""
        md_id = await _insert_row(db_session, MfgDataStatus.PENDING.value)
        try:
            claimed = await claim_next_generation(300)

            assert claimed is not None
            assert claimed[0] == md_id
            remaining = await db_session.execute(
                text(
                    "SELECT EXTRACT(EPOCH FROM (lease_expires_at - NOW())) "
                    "FROM manufacturing_data WHERE id = :id"
                ),
                {"id": md_id},
            )
            # DB のサーバ時刻基準で 300 秒後（テストの実行時間ぶんだけ手前にずれる）
            assert 295 <= float(remaining.scalar_one()) <= 300
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_a_lease_written_by_claim_is_reclaimed_once_it_expires(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """claim が書いたリースを reclaim が正しく解釈すること（経路をつなぐ）."""
        md_id = await _insert_row(db_session, MfgDataStatus.PENDING.value)
        try:
            claimed = await claim_next_generation(1)
            assert claimed is not None

            # 期限内はまだ戻さない
            await reclaim_expired_generation_leases()
            status, _, _ = await _row(db_session, md_id)
            assert status == MfgDataStatus.GENERATING.value

            await asyncio.sleep(1.2)
            await reclaim_expired_generation_leases()

            status, _, lease = await _row(db_session, md_id)
            assert status == MfgDataStatus.PENDING.value
            assert lease is None
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_returns_none_when_the_queue_is_empty(
        self, quiet_queue: None
    ) -> None:
        assert await claim_next_generation(1800) is None

    @pytest.mark.asyncio
    async def test_concurrent_claims_never_return_the_same_row(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """**アドバイザリロック無しでも**、同時に取り出して同じ行が重ならないこと."""
        ids = [
            await _insert_row(db_session, MfgDataStatus.PENDING.value, seq=i)
            for i in range(5)
        ]
        mine = set(ids)
        try:
            claimed = await asyncio.gather(*(claim_next_generation(1800) for _ in range(5)))

            got = [c[0] for c in claimed if c is not None]
            assert len(got) == len(set(got))  # 同じ行が 2 度返っていない
            assert set(got) == mine  # 5 行とも、ちょうど 1 度ずつ掴まれている
        finally:
            await _cleanup(db_session, ids)


class TestReclaimExpiredLeases:
    """復旧処理が、ワーカーの本数に依存せず単独で正しいこと."""

    @pytest.mark.asyncio
    async def test_reclaims_a_row_whose_lease_expired(
        self, db_session: AsyncSession
    ) -> None:
        md_id = await _insert_row(
            db_session, MfgDataStatus.GENERATING.value, lease_offset_seconds=-60
        )
        try:
            await reclaim_expired_generation_leases()

            status, _, lease = await _row(db_session, md_id)
            assert status == MfgDataStatus.PENDING.value
            assert lease is None
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_reclaims_a_generating_row_without_a_lease(
        self, db_session: AsyncSession
    ) -> None:
        """リース導入前に確保された行も、取り残しとして戻す."""
        md_id = await _insert_row(
            db_session, MfgDataStatus.GENERATING.value, lease_offset_seconds=None
        )
        try:
            await reclaim_expired_generation_leases()

            status, _, _ = await _row(db_session, md_id)
            assert status == MfgDataStatus.PENDING.value
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_leaves_a_row_whose_lease_is_still_valid(
        self, db_session: AsyncSession
    ) -> None:
        """**ここが設計の要。**処理中の行を奪わないので、復旧はロック無しでも安全である."""
        md_id = await _insert_row(
            db_session, MfgDataStatus.GENERATING.value, lease_offset_seconds=3600
        )
        try:
            await reclaim_expired_generation_leases()

            status, _, lease = await _row(db_session, md_id)
            assert status == MfgDataStatus.GENERATING.value  # 触られていない
            assert lease is not None
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_does_not_touch_pending_rows(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """pending は戻す必要が無い。触ると updated_at が動き、件数も読めなくなる."""
        md_id = await _insert_row(db_session, MfgDataStatus.PENDING.value)
        try:
            before = await db_session.execute(
                text("SELECT updated_at FROM manufacturing_data WHERE id = :id"),
                {"id": md_id},
            )
            updated_at = before.scalar_one()

            await reclaim_expired_generation_leases()

            after = await db_session.execute(
                text("SELECT status, updated_at FROM manufacturing_data WHERE id = :id"),
                {"id": md_id},
            )
            status, touched_at = after.one()
            assert status == MfgDataStatus.PENDING.value
            # 同じ値で UPDATE していれば updated_at が動く（onupdate=now）。動いていない
            # ことが「触っていない」の証拠になる。
            assert touched_at == updated_at
        finally:
            await _cleanup(db_session, [md_id])


class TestLeaseFencing:
    """リースを失った結果が書き戻されないこと（所有権の検証）."""

    @pytest.mark.asyncio
    async def test_finish_applies_while_the_lease_is_held(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        md_id = await _insert_row(db_session, MfgDataStatus.PENDING.value)
        try:
            claimed = await claim_next_generation(1800)
            assert claimed is not None
            _, lease_token = claimed

            applied = await _finish(db_session, md_id, lease_token, "ready")

            assert applied is True
            status, _, lease = await _row(db_session, md_id)
            assert status == MfgDataStatus.READY.value
            assert lease is None  # 所有権を返している
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_finish_is_discarded_after_the_lease_was_taken_over(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """**ここが要。**リースが失効して再確保された行を、古い結果で上書きしない."""
        md_id = await _insert_row(db_session, MfgDataStatus.PENDING.value)
        try:
            first = await claim_next_generation(1)
            assert first is not None
            _, stale_token = first

            # 1 本目が生成に手間取っている間に、リースが切れて 2 本目が再確保する。
            # 巻き戻しは再試行の間隔を空けるので、ここではそれを 0 にして即座に取り直す
            # （検証したいのはフェンシングであって、間隔ではない）。
            await asyncio.sleep(1.2)
            with patch.object(settings, "MFG_RETRY_BASE_SECONDS", 0):
                await reclaim_expired_generation_leases()
            second = await claim_next_generation(1800)
            assert second is not None
            assert second[0] == md_id
            assert second[1] != stale_token

            # 遅れて戻ってきた 1 本目の結果は捨てられる
            applied = await _finish(db_session, md_id, stale_token, "ready")

            assert applied is False
            status, _, lease = await _row(db_session, md_id)
            assert status == MfgDataStatus.GENERATING.value  # 2 本目が処理中のまま
            assert lease is not None  # 2 本目の所有権が生きている
        finally:
            await _cleanup(db_session, [md_id])


class TestWorkerRun:
    @pytest.mark.asyncio
    async def test_drains_the_queue_in_created_order(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """生成待ちを古い順に処理し、対象が無くなったら終了する."""
        ids = [
            await _insert_row(db_session, MfgDataStatus.PENDING.value, seq=i)
            for i in range(3)
        ]
        processed: list[str] = []

        async def fake_run(md_id: str, lease_token: Any) -> None:
            processed.append(md_id)
            await db_session.execute(
                text(
                    "UPDATE manufacturing_data SET status = 'ready', "
                    "lease_expires_at = NULL WHERE id = :id"
                ),
                {"id": md_id},
            )
            await db_session.commit()

        try:
            with patch.object(worker, "run_generation", fake_run):
                await worker.process_pending(max_runtime_seconds=60, max_items=0)

            assert processed == ids  # created_at の昇順で拾う
            for md_id in ids:
                status, _, _ = await _row(db_session, md_id)
                assert status == MfgDataStatus.READY.value
        finally:
            await _cleanup(db_session, ids)

    @pytest.mark.asyncio
    async def test_second_worker_exits_without_doing_anything(self) -> None:
        """多重起動の抑止。正しさではなく、直列な VM を奪い合わないための降り方."""
        entered = asyncio.Event()
        release = asyncio.Event()
        runs = 0

        async def slow_process(**_: Any) -> int:
            nonlocal runs
            runs += 1
            entered.set()
            await release.wait()
            return 1

        with (
            patch.object(worker, "reclaim_expired_generation_leases", AsyncMock(return_value=0)),
            patch.object(worker, "process_pending", slow_process),
        ):
            first = asyncio.create_task(worker.run_once())
            await asyncio.wait_for(entered.wait(), timeout=10)

            # 1 本目がロックを保持している間に 2 本目を走らせる。ロックが効いていれば
            # 即座に戻る。効いていなければ 2 本目も slow_process に入って解放待ちで
            # 詰まるため、待ち時間を切ってその場で失敗させる（ハングさせない）。
            try:
                second = await asyncio.wait_for(worker.run_once(), timeout=5)
            finally:
                release.set()

            assert await asyncio.wait_for(first, timeout=10) == 1

        assert second == 0
        assert runs == 1


class TestRetryScheduling:
    """到達不能で戻された行が、いつ取り出せるようになるか（実DB）.

    予定時刻の比較は PostgreSQL のサーバ時刻で行われるため、モックでは検証できない。
    """

    @pytest.mark.asyncio
    async def test_a_row_scheduled_for_later_is_not_claimed(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """再試行の予定時刻が未来なら取り出さない（落ちている VM を叩き続けない）."""
        md_id = await _insert_row(
            db_session, MfgDataStatus.PENDING.value, next_attempt_offset_seconds=3600
        )
        try:
            assert await claim_next_generation(60) is None
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_a_row_whose_schedule_has_passed_is_claimed(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """予定時刻を過ぎたら取り出す（VM が戻れば自力で再開する）."""
        md_id = await _insert_row(
            db_session, MfgDataStatus.PENDING.value, next_attempt_offset_seconds=-1
        )
        try:
            claimed = await claim_next_generation(60)
            assert claimed is not None
            assert claimed[0] == md_id

            # 確保したら予定は消化済みになる。残すとリース失効で戻ったときに引きずる。
            status, _, next_attempt, _ = await _retry_row(db_session, md_id)
            assert status == MfgDataStatus.GENERATING.value
            assert next_attempt is None
        finally:
            await _cleanup(db_session, [md_id])

    @pytest.mark.asyncio
    async def test_a_scheduled_row_does_not_block_the_ones_behind_it(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """**先頭詰まりが起きないこと。** 予定待ちの行は飛ばして後続を処理する.

        これが無いと、特定の入力でだけ VM が 5xx を返す 1 行が待ち行列の先頭に居座り、
        その後ろの受注がすべて止まる。
        """
        blocked = await _insert_row(
            db_session,
            MfgDataStatus.PENDING.value,
            seq=0,
            next_attempt_offset_seconds=3600,
        )
        behind = await _insert_row(db_session, MfgDataStatus.PENDING.value, seq=1)
        try:
            claimed = await claim_next_generation(60)
            assert claimed is not None
            # 古い順なら blocked が先に返るはずのところを、予定待ちなので飛ばす。
            assert claimed[0] == behind
        finally:
            await _cleanup(db_session, [blocked, behind])

    @pytest.mark.asyncio
    async def test_a_crashed_row_is_put_back_behind_a_wait(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """**クラッシュで戻した行も間隔を空ける。**

        空けないと、ワーカーを落とす行（巨大な画像で OOM になる等）が即座に取り直され、
        取り出しは古い順なので待ち行列の先頭に居座り続ける。**後続がその 1 行で止まる。**
        生成の途中で落ちた行は失敗ハンドラを通らないので、ここが唯一の歯止めである。
        """
        crashed = await _insert_row(
            db_session, MfgDataStatus.GENERATING.value, seq=0, lease_offset_seconds=-1
        )
        behind = await _insert_row(db_session, MfgDataStatus.PENDING.value, seq=1)
        try:
            assert await reclaim_expired_generation_leases() >= 1

            status, _, next_attempt, _ = await _retry_row(db_session, crashed)
            assert status == MfgDataStatus.PENDING.value
            assert next_attempt is not None

            # 先頭に居座らず、後続が先に進む
            claimed = await claim_next_generation(60)
            assert claimed is not None
            assert claimed[0] == behind
        finally:
            await _cleanup(db_session, [crashed, behind])

    @pytest.mark.asyncio
    async def test_a_crashed_row_comes_back_once_the_wait_has_passed(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """待ったうえで、ちゃんと戻ってくる（取りこぼしにはしない）."""
        md_id = await _insert_row(
            db_session, MfgDataStatus.GENERATING.value, lease_offset_seconds=-1
        )
        try:
            with patch.object(settings, "MFG_RETRY_BASE_SECONDS", 0):
                assert await reclaim_expired_generation_leases() >= 1
            claimed = await claim_next_generation(60)
            assert claimed is not None
            assert claimed[0] == md_id
        finally:
            await _cleanup(db_session, [md_id])


class TestRetryFailed:
    """失敗した行の一括リトライ（VM 停止明けの復旧操作）."""

    @pytest.mark.asyncio
    async def test_all_failed_rows_go_back_to_the_queue(
        self, db_session: AsyncSession
    ) -> None:
        failed = [
            await _insert_row(db_session, MfgDataStatus.FAILED.value, seq=i)
            for i in range(3)
        ]
        try:
            repo = ManufacturingDataRepository(db_session)
            restored = await repo.retry_failed()
            await db_session.commit()

            assert restored >= 3
            for md_id in failed:
                status, attempts, next_attempt, error = await _retry_row(
                    db_session, md_id
                )
                assert status == MfgDataStatus.PENDING.value
                # 人の判断による仕切り直しなので、数え直しも待ち時間も手放す。
                assert attempts == 0
                assert next_attempt is None
                assert error is None
        finally:
            await _cleanup(db_session, failed)

    @pytest.mark.asyncio
    async def test_only_the_named_rows_are_restored(
        self, db_session: AsyncSession
    ) -> None:
        target = await _insert_row(db_session, MfgDataStatus.FAILED.value, seq=0)
        other = await _insert_row(db_session, MfgDataStatus.FAILED.value, seq=1)
        try:
            repo = ManufacturingDataRepository(db_session)
            assert await repo.retry_failed([target]) == 1
            await db_session.commit()

            assert (await _retry_row(db_session, target))[0] == MfgDataStatus.PENDING.value
            assert (await _retry_row(db_session, other))[0] == MfgDataStatus.FAILED.value
        finally:
            await _cleanup(db_session, [target, other])

    @pytest.mark.asyncio
    async def test_rows_that_are_not_failed_are_left_alone(
        self, db_session: AsyncSession
    ) -> None:
        """**ready を巻き戻さない。** 行は複数の注文で共有されるため、巻き戻すと
        その行を参照する他の注文の発注可否まで落ちる。
        """
        ready = await _insert_row(db_session, MfgDataStatus.READY.value)
        generating = await _insert_row(
            db_session, MfgDataStatus.GENERATING.value, lease_offset_seconds=600
        )
        try:
            repo = ManufacturingDataRepository(db_session)
            assert await repo.retry_failed([ready, generating]) == 0
            await db_session.commit()

            assert (await _retry_row(db_session, ready))[0] == MfgDataStatus.READY.value
            assert (await _retry_row(db_session, generating))[
                0
            ] == MfgDataStatus.GENERATING.value
        finally:
            await _cleanup(db_session, [ready, generating])


class TestWorkerStopsWhenTheVmIsDown:
    """VM に届かないと分かった時点で周回を降りる（実DB）."""

    @pytest.mark.asyncio
    async def test_the_run_stops_at_the_first_unreachable_row(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """**同じ答えのために 1 件 15 分を積み増さない。**

        残りは pending のまま次回の起動が拾うので、取りこぼしにはならない。
        """
        ids = [
            await _insert_row(db_session, MfgDataStatus.PENDING.value, seq=i)
            for i in range(3)
        ]
        attempted: list[str] = []

        async def vm_is_down(md_id: str, lease_token: Any) -> Any:
            attempted.append(md_id)
            await db_session.execute(
                text(
                    "UPDATE manufacturing_data SET status = 'pending', "
                    "lease_expires_at = NULL, "
                    "next_attempt_at = NOW() + INTERVAL '1 hour' WHERE id = :id"
                ),
                {"id": md_id},
            )
            await db_session.commit()
            return GenerationOutcome.VM_UNREACHABLE

        try:
            with patch.object(worker, "run_generation", vm_is_down):
                processed = await worker.process_pending(
                    max_runtime_seconds=60, max_items=0
                )

            assert processed == 1
            assert attempted == ids[:1]  # 2 件目以降には手を付けない
            # 手つかずの行はそのまま待っている
            for md_id in ids[1:]:
                status, attempts, next_attempt, _ = await _retry_row(db_session, md_id)
                assert status == MfgDataStatus.PENDING.value
                assert attempts == 0
                assert next_attempt is None
        finally:
            await _cleanup(db_session, ids)

    @pytest.mark.asyncio
    async def test_a_single_bad_row_does_not_stop_the_others(
        self, db_session: AsyncSession, quiet_queue: None
    ) -> None:
        """入力が悪い 1 行では降りない（VM は生きているため）."""
        ids = [
            await _insert_row(db_session, MfgDataStatus.PENDING.value, seq=i)
            for i in range(3)
        ]
        attempted: list[str] = []

        async def bad_input(md_id: str, lease_token: Any) -> Any:
            attempted.append(md_id)
            await db_session.execute(
                text(
                    "UPDATE manufacturing_data SET status = 'failed', "
                    "lease_expires_at = NULL WHERE id = :id"
                ),
                {"id": md_id},
            )
            await db_session.commit()
            return GenerationOutcome.FAILED

        try:
            with patch.object(worker, "run_generation", bad_input):
                processed = await worker.process_pending(
                    max_runtime_seconds=60, max_items=0
                )

            assert processed == 3
            assert attempted == ids
        finally:
            await _cleanup(db_session, ids)
