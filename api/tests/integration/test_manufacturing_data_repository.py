"""Integration tests for ManufacturingDataRepository (cache key + NULLS NOT DISTINCT)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.repositories.manufacturing_data_repository import ManufacturingDataRepository


def _md(order_source_id, *, product_code="PC", size="50x50mm", variant=None):
    return ManufacturingData(
        order_source_id=order_source_id,
        product_code=product_code,
        product_type="acrylic_keychain",
        size=size,
        variant=variant,
        status=MfgDataStatus.PENDING.value,
    )


class TestCacheKey:
    @pytest.mark.asyncio
    async def test_find_by_cache_key_null_variant(self, db_session, test_order_source):
        repo = ManufacturingDataRepository(db_session)
        src = test_order_source["id"]
        created = await repo.create(_md(src, product_code="PC-NULL", variant=None))
        found = await repo.find_by_cache_key(src, "PC-NULL", "50x50mm", None)
        assert found is not None
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_find_by_cache_key_distinguishes_variant(self, db_session, test_order_source):
        repo = ManufacturingDataRepository(db_session)
        src = test_order_source["id"]
        clear = await repo.create(_md(src, product_code="PC-VAR", variant="clear"))
        color = await repo.create(_md(src, product_code="PC-VAR", variant="color"))

        found_clear = await repo.find_by_cache_key(src, "PC-VAR", "50x50mm", "clear")
        found_color = await repo.find_by_cache_key(src, "PC-VAR", "50x50mm", "color")
        assert found_clear is not None and found_clear.id == clear.id
        assert found_color is not None and found_color.id == color.id

    @pytest.mark.asyncio
    async def test_null_variant_second_insert_conflicts(self, db_session, test_order_source):
        # NULLS NOT DISTINCT: 同一(source, code, size)で variant=NULL の2行目は一意制約違反
        repo = ManufacturingDataRepository(db_session)
        src = test_order_source["id"]
        await repo.create(_md(src, product_code="PC-DUP", variant=None))
        with pytest.raises(IntegrityError):
            await repo.create(_md(src, product_code="PC-DUP", variant=None))
