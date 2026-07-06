"""Repository for ManufacturingData (製造データ生成キャッシュ)."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import OrderItem


class ManufacturingDataRepository:
    """Repository for the manufacturing_data cache table."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, md: ManufacturingData) -> ManufacturingData:
        """Insert a new manufacturing_data row."""
        self._db.add(md)
        await self._db.flush()
        await self._db.refresh(md)
        return md

    async def get_by_id(self, mfg_data_id: str) -> ManufacturingData | None:
        """Fetch a single row by id."""
        result = await self._db.execute(
            select(ManufacturingData).where(ManufacturingData.id == mfg_data_id)
        )
        return result.scalar_one_or_none()

    async def find_by_cache_key(
        self,
        order_source_id: str,
        product_code: str,
        size: str,
        variant: str | None,
    ) -> ManufacturingData | None:
        """Look up the cached row by (order_source, product_code, size, variant).

        variant is NULLable; NULL is matched with IS NULL so「バリアントなし」商品も
        一意に引ける（DB側は NULLS NOT DISTINCT の一意制約で重複を防止）。
        """
        query = select(ManufacturingData).where(
            ManufacturingData.order_source_id == order_source_id,
            ManufacturingData.product_code == product_code,
            ManufacturingData.size == size,
        )
        if variant is None:
            query = query.where(ManufacturingData.variant.is_(None))
        else:
            query = query.where(ManufacturingData.variant == variant)
        result = await self._db.execute(query)
        return result.scalar_one_or_none()

    async def find_by_ids(self, ids: list[str]) -> list[ManufacturingData]:
        """Fetch multiple rows by id (順不同)."""
        if not ids:
            return []
        result = await self._db.execute(
            select(ManufacturingData).where(ManufacturingData.id.in_(ids))
        )
        return list(result.scalars().all())

    async def find_by_order_id(self, order_id: str) -> list[ManufacturingData]:
        """Fetch manufacturing_data rows linked to an order's items."""
        result = await self._db.execute(
            select(ManufacturingData)
            .join(OrderItem, OrderItem.manufacturing_data_id == ManufacturingData.id)
            .where(OrderItem.order_id == order_id)
        )
        return list(result.scalars().unique().all())

    async def list_recent(
        self, limit: int = 100, status: str | None = None
    ) -> list[ManufacturingData]:
        """List rows (newest first), optionally filtered by status."""
        query = select(ManufacturingData).order_by(ManufacturingData.created_at.desc())
        if status is not None:
            query = query.where(ManufacturingData.status == status)
        query = query.limit(limit)
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def claim_for_generation(self, mfg_data_id: str, *, allow_ready: bool = False) -> bool:
        """原子的に status を generating へ遷移させ生成権を得る（多重生成防止）.

        pending / failed（allow_ready なら ready も）からのみ claim 可能。RETURNING で
        更新できたか判定し、True の場合のみ呼び出し側が生成を続行する。
        """
        claimable = [MfgDataStatus.PENDING.value, MfgDataStatus.FAILED.value]
        if allow_ready:
            claimable.append(MfgDataStatus.READY.value)
        result = await self._db.execute(
            update(ManufacturingData)
            .where(
                ManufacturingData.id == mfg_data_id,
                ManufacturingData.status.in_(claimable),
            )
            .values(
                status=MfgDataStatus.GENERATING.value,
                attempts=ManufacturingData.attempts + 1,
                error_message=None,
            )
            .returning(ManufacturingData.id)
        )
        await self._db.flush()
        return result.scalar_one_or_none() is not None

    async def reset_to_pending(self, mfg_data_id: str) -> ManufacturingData | None:
        """行を pending へ戻す（手動リトライ用。generating スタックからの復旧も可能）."""
        md = await self.get_by_id(mfg_data_id)
        if md is None:
            return None
        md.status = MfgDataStatus.PENDING.value
        md.error_message = None
        await self._db.flush()
        return md

    async def flush(self) -> None:
        """Flush pending changes (状態遷移を中間コミット前に反映するため)."""
        await self._db.flush()
