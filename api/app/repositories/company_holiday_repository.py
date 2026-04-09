"""Company holiday repository."""

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_holiday import CompanyHoliday


class CompanyHolidayRepository:
    """Repository for CompanyHoliday model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_all_dates(self) -> set[datetime.date]:
        """全ての独自休日の日付セットを取得する."""
        result = await self._db.execute(select(CompanyHoliday.date))
        return {row[0] for row in result.all()}
