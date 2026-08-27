"""Manufacturing data repository for database operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, update
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

    async def claim_next_generation(
        self, lease_seconds: float
    ) -> tuple[str, datetime] | None:
        """生成待ちの最も古い 1 行を確保して generating にし、``(id, リース期限)`` を返す.

        生成待ちが無ければ None。

        **これがキューからの取り出しである。**候補の選択・確保・リースの付与を 1 つの文で
        行うので、複数のワーカーが同時に走っても同じ行を 2 度取り出すことはない
        （``FOR UPDATE SKIP LOCKED`` が、他のワーカーが掴んでいる行を黙って飛ばす）。

        リースの期限は、その行を「今まさに処理している」と見なす期限である。期限を過ぎても
        generating のままなら、処理していたワーカーが落ちたと判断できる
        （→ reclaim_expired_generation_leases）。

        **返すリース期限は、その所有権の証明として使う。**結果を書き戻すときにこの値を
        添えれば、リースが失効して別のワーカーに再確保された行を、古いワーカーが
        上書きしてしまうことを防げる（→ finish_generation）。
        """
        oldest_pending = (
            select(ManufacturingData.id)
            .where(ManufacturingData.status == MfgDataStatus.PENDING.value)
            .order_by(ManufacturingData.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        result = await self._db.execute(
            update(ManufacturingData)
            .where(ManufacturingData.id == oldest_pending)
            .values(
                status=MfgDataStatus.GENERATING.value,
                attempts=ManufacturingData.attempts + 1,
                error_message=None,
                lease_expires_at=func.now() + timedelta(seconds=lease_seconds),
            )
            .returning(ManufacturingData.id, ManufacturingData.lease_expires_at)
            .execution_options(synchronize_session=False)
        )
        row = result.first()
        return None if row is None else (row[0], row[1])

    async def finish_generation(
        self, mfg_data_id: str, *, lease_token: datetime, values: dict[str, Any]
    ) -> bool:
        """リースを保持している間だけ、生成結果を書き戻してリースを外す.

        ``lease_token`` は claim_next_generation が返したリース期限である。
        書き戻しの時点でこの値が一致していなければ、**リースが失効して別のワーカーが
        再確保した後**ということなので、何も書かずに False を返す。

        これが無いと、期限を誤って短く設定したときに、古いワーカーの結果が新しい
        ワーカーの処理を静かに上書きする（しかも誰も気づけない）。
        """
        result = await self._db.execute(
            update(ManufacturingData)
            .where(
                ManufacturingData.id == mfg_data_id,
                ManufacturingData.lease_expires_at == lease_token,
            )
            .values(**values, lease_expires_at=None)
            .returning(ManufacturingData.id)
            .execution_options(synchronize_session=False)
        )
        return result.scalars().first() is not None

    async def reclaim_expired_leases(self) -> int:
        """リースが切れた generating 行を pending へ戻し、戻した件数を返す.

        **この判定は、ワーカーが何本走っているかに依存しない。**期限内のリースを持つ行は
        誰かが処理中なので触らない。リースを持たない generating は、リース導入前に確保された
        行（または確保直後に落ちた行）なので、期限切れとして扱う。

        pending の行は対象にしない。戻す必要が無いうえ、同じ値で UPDATE すると
        バックログ全件の updated_at が動き、戻した件数も読めなくなる。
        """
        result = await self._db.execute(
            update(ManufacturingData)
            .where(
                ManufacturingData.status == MfgDataStatus.GENERATING.value,
                or_(
                    ManufacturingData.lease_expires_at.is_(None),
                    ManufacturingData.lease_expires_at < func.now(),
                ),
            )
            .values(status=MfgDataStatus.PENDING.value, lease_expires_at=None)
            .returning(ManufacturingData.id)
            .execution_options(synchronize_session=False)
        )
        return len(result.scalars().all())

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
