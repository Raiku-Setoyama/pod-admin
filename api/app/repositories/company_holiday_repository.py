"""Company holiday repository for database operations."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_holiday import CompanyHoliday


class CompanyHolidayRepository:
    """Repository for CompanyHoliday model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_all(self) -> list[CompanyHoliday]:
        """Get all company holidays ordered by date."""
        result = await self._db.execute(
            select(CompanyHoliday).order_by(CompanyHoliday.date.asc())
        )
        return list(result.scalars().all())

    async def find_all_dates(self) -> set[date]:
        """Get all company holiday dates as a set (for business day calculation)."""
        holidays = await self.find_all()
        return {h.date for h in holidays}

    async def find_by_id(self, holiday_id: str) -> CompanyHoliday | None:
        """Find a company holiday by ID."""
        result = await self._db.execute(
            select(CompanyHoliday).where(CompanyHoliday.id == holiday_id)
        )
        return result.scalar_one_or_none()

    async def create(self, holiday_date: date, name: str) -> CompanyHoliday:
        """Create a new company holiday."""
        holiday = CompanyHoliday(date=holiday_date, name=name)
        self._db.add(holiday)
        await self._db.flush()
        await self._db.refresh(holiday)
        return holiday

    async def delete(self, holiday_id: str) -> bool:
        """Delete a company holiday. Returns True if deleted."""
        holiday = await self.find_by_id(holiday_id)
        if not holiday:
            return False
        await self._db.delete(holiday)
        await self._db.flush()
        return True
