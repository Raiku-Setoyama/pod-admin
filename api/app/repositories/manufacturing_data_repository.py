"""Manufacturing data repository for database operations."""

from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturing_data import ManufacturingData


class ManufacturingDataRepository:
    """Repository for ManufacturingData model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, mfg_data_id: str) -> ManufacturingData | None:
        """Find a manufacturing data row by ID."""
        result = await self._db.execute(
            select(ManufacturingData).where(ManufacturingData.id == mfg_data_id)
        )
        return result.scalar_one_or_none()

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


def _eq_or_null(column, value):
    """value が None なら IS NULL、そうでなければ等価比較を返す."""
    if value is None:
        return column.is_(None)
    return column == value
