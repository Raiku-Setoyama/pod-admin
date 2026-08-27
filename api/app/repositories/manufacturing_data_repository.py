"""Manufacturing data repository for database operations."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus


class ManufacturingDataRepository:
    """Repository for ManufacturingData model."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, mfg_data_id: str) -> ManufacturingData | None:
        """Find a manufacturing data row by ID."""
        result = await self._db.execute(
            select(ManufacturingData).where(ManufacturingData.id == mfg_data_id)
        )
        return result.scalar_one_or_none()

    async def claim_for_generation(self, mfg_data_id: str) -> bool:
        """生成のためにこの行を原子的に確保（claim）し、generating へ遷移させる.

        status が pending/failed のときのみ、status=generating・attempts+1・error クリアを
        1つの条件付き UPDATE で確定する（生成開始の遷移をこの1文が単独で所有する）。既に
        generating（他ワーカーが処理中）または ready の場合は 0 行更新となり False を返す。
        これにより、同一行に対して複数の run_generation が走っても VM ジョブは一度しか投入
        されない（PostgreSQL は競合 UPDATE をロックし、解放後に WHERE を再評価する）。
        """
        result = await self._db.execute(
            update(ManufacturingData)
            .where(
                ManufacturingData.id == mfg_data_id,
                ManufacturingData.status.notin_(
                    [MfgDataStatus.GENERATING.value, MfgDataStatus.READY.value]
                ),
            )
            .values(
                status=MfgDataStatus.GENERATING.value,
                attempts=ManufacturingData.attempts + 1,
                error_message=None,
            )
            .returning(ManufacturingData.id)
            .execution_options(synchronize_session=False)
        )
        return result.scalar_one_or_none() is not None

    async def reclaim_stranded(self) -> int:
        """中断されて generating のまま残った行を pending へ戻し、戻した件数を返す.

        ワーカーが生成中に落ちると、その行は generating のまま取り残される。
        ワーカーは同時に 1 本しか走らないので、この呼び出しの時点で generating に
        残っているものは全て中断済みであり、pending へ戻して差し支えない。

        **pending の行は対象にしない。** 戻す必要が無いうえ、同じ値で UPDATE すると
        バックログ全件の updated_at が動き、戻した件数も読めなくなる。
        対象を generating に絞ったことで、通常運用ではほぼ 0 件しか触らない。
        """
        result = await self._db.execute(
            update(ManufacturingData)
            .where(ManufacturingData.status == MfgDataStatus.GENERATING.value)
            .values(status=MfgDataStatus.PENDING.value)
            .returning(ManufacturingData.id)
            .execution_options(synchronize_session=False)
        )
        return len(result.scalars().all())

    async def find_next_pending_id(self, exclude: Collection[str]) -> str | None:
        """生成待ち（pending）の行のうち、最も古い 1 件の id を返す（無ければ None）.

        ワーカーが処理対象を 1 件ずつ取り出すために使う。1 件だけ引くのは、処理のたびに
        「その時点で最も古い生成待ち」を見るためである（処理中に他プロセスが積んだ行も拾える）。

        ``exclude`` は、処理しても pending から外れなかった行を除くためのもの。無限ループを
        防ぐ。ワーカーの 1 回の起動で処理する件数には上限があるため、この集合は小さいままになる。

        ここでは行をロックしない：実際の確保は claim_for_generation の条件付き UPDATE が
        原子的に行うため、複数のワーカーが同じ id を拾っても generating へ進めるのは一方だけ。
        """
        query = (
            select(ManufacturingData.id)
            .where(ManufacturingData.status == MfgDataStatus.PENDING.value)
            .order_by(ManufacturingData.created_at)
            .limit(1)
        )
        if exclude:
            query = query.where(ManufacturingData.id.notin_(exclude))
        result = await self._db.execute(query)
        return result.scalars().first()

    async def find_by_cache_key(
        self,
        order_source_id: str | None,
        product_code: str,
        size: str | None,
        variant: str | None,
    ) -> ManufacturingData | None:
        """Find manufacturing data by cache key (order_source × product_code × size × variant).

        NULL の size/variant は NULL 同士で一致させる（キャッシュ一意制約と整合）。
        """
        conditions = [
            ManufacturingData.product_code == product_code,
            _eq_or_null(ManufacturingData.order_source_id, order_source_id),
            _eq_or_null(ManufacturingData.size, size),
            _eq_or_null(ManufacturingData.variant, variant),
        ]
        result = await self._db.execute(
            select(ManufacturingData).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def create(self, mfg_data: ManufacturingData) -> ManufacturingData:
        """Create a new manufacturing data row."""
        self._db.add(mfg_data)
        await self._db.flush()
        await self._db.refresh(mfg_data)
        return mfg_data

    async def update(self, mfg_data: ManufacturingData) -> ManufacturingData:
        """Persist changes to a manufacturing data row."""
        await self._db.flush()
        await self._db.refresh(mfg_data)
        return mfg_data

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        order_source_id: str | None = None,
        product_code: str | None = None,
    ) -> tuple[list[ManufacturingData], int]:
        """List manufacturing data rows with pagination and filters."""
        # 条件を一度だけ組み立て、本体クエリと件数クエリの双方に適用する
        conditions = []
        if status:
            conditions.append(ManufacturingData.status == status)
        if order_source_id:
            conditions.append(ManufacturingData.order_source_id == order_source_id)
        if product_code:
            conditions.append(ManufacturingData.product_code == product_code)

        query = select(ManufacturingData).where(*conditions)
        count_query = select(func.count(ManufacturingData.id)).where(*conditions)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * limit
        query = (
            query.order_by(ManufacturingData.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._db.execute(query)
        return list(result.scalars().all()), total


def _eq_or_null(column: Any, value: Any) -> Any:
    """value が None なら IS NULL、そうでなければ等価比較を返す."""
    if value is None:
        return column.is_(None)
    return column == value
