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

    async def find_all(self) -> list[CompanyHoliday]:
        """全ての独自休日を取得する."""
        result = await self._db.execute(
            select(CompanyHoliday).order_by(CompanyHoliday.date)
        )
        return list(result.scalars().all())

    async def find_by_id(self, holiday_id: str) -> CompanyHoliday | None:
        """IDで独自休日を取得する."""
        result = await self._db.execute(
            select(CompanyHoliday).where(CompanyHoliday.id == holiday_id)
        )
        return result.scalar_one_or_none()

    async def find_by_date(self, date: datetime.date) -> CompanyHoliday | None:
        """日付で独自休日を取得する."""
        result = await self._db.execute(
            select(CompanyHoliday).where(CompanyHoliday.date == date)
        )
        return result.scalar_one_or_none()

    async def create(self, date: datetime.date, name: str) -> CompanyHoliday:
        """独自休日を作成する."""
        holiday = CompanyHoliday(date=date, name=name)
        self._db.add(holiday)
        await self._db.flush()
        await self._db.refresh(holiday)
        return holiday

    async def delete(self, holiday_id: str) -> bool:
        """独自休日を削除する."""
        holiday = await self.find_by_id(holiday_id)
        if not holiday:
            return False
        await self._db.delete(holiday)
        await self._db.flush()
        return True
