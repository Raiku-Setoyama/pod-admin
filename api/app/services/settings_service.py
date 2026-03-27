"""Settings service."""

from datetime import date

from app.repositories.company_holiday_repository import CompanyHolidayRepository
from app.repositories.system_setting_repository import SystemSettingRepository
from app.schemas.settings import (
    CompanyHolidayCreate,
    CompanyHolidayListResponse,
    CompanyHolidayResponse,
    ShippingPreparationDaysResponse,
    ShippingPreparationDaysUpdate,
)
from app.utils.exceptions import NotFoundError

SHIPPING_PREPARATION_DAYS_KEY = "shipping_preparation_days"
SHIPPING_PREPARATION_DAYS_DEFAULT = 5


class SettingsService:
    """Service for settings operations."""

    def __init__(
        self,
        system_setting_repo: SystemSettingRepository,
        company_holiday_repo: CompanyHolidayRepository,
    ):
        self._system_setting_repo = system_setting_repo
        self._company_holiday_repo = company_holiday_repo

    async def get_shipping_preparation_days(self) -> ShippingPreparationDaysResponse:
        """Get shipping preparation days setting."""
        setting = await self._system_setting_repo.get_by_key(SHIPPING_PREPARATION_DAYS_KEY)
        if setting:
            try:
                value = int(setting.value)
            except (ValueError, TypeError):
                value = SHIPPING_PREPARATION_DAYS_DEFAULT
            return ShippingPreparationDaysResponse(
                value=value,
                description=setting.description,
            )
        return ShippingPreparationDaysResponse(
            value=SHIPPING_PREPARATION_DAYS_DEFAULT,
            description="発送準備日数",
        )

    async def update_shipping_preparation_days(
        self, data: ShippingPreparationDaysUpdate
    ) -> ShippingPreparationDaysResponse:
        """Update shipping preparation days setting."""
        setting = await self._system_setting_repo.upsert(
            key=SHIPPING_PREPARATION_DAYS_KEY,
            value=str(data.value),
            description="発送準備日数",
        )
        return ShippingPreparationDaysResponse(
            value=int(setting.value),
            description=setting.description,
        )

    async def get_shipping_preparation_days_value(self) -> int:
        """Get shipping preparation days as integer (for internal use)."""
        setting = await self._system_setting_repo.get_by_key(SHIPPING_PREPARATION_DAYS_KEY)
        if setting:
            try:
                value = int(setting.value)
            except (ValueError, TypeError):
                value = SHIPPING_PREPARATION_DAYS_DEFAULT
            return value
        return SHIPPING_PREPARATION_DAYS_DEFAULT

    async def get_company_holidays(self) -> CompanyHolidayListResponse:
        """Get all company holidays."""
        holidays = await self._company_holiday_repo.find_all()
        return CompanyHolidayListResponse(
            items=[
                CompanyHolidayResponse(id=h.id, date=h.date, name=h.name)
                for h in holidays
            ]
        )

    async def get_company_holiday_dates(self) -> set[date]:
        """Get all company holiday dates as set (for business day calculation)."""
        return await self._company_holiday_repo.find_all_dates()

    async def create_company_holiday(
        self, data: CompanyHolidayCreate
    ) -> CompanyHolidayResponse:
        """Create a new company holiday."""
        holiday = await self._company_holiday_repo.create(
            holiday_date=data.date, name=data.name
        )
        return CompanyHolidayResponse(id=holiday.id, date=holiday.date, name=holiday.name)

    async def delete_company_holiday(self, holiday_id: str) -> None:
        """Delete a company holiday."""
        deleted = await self._company_holiday_repo.delete(holiday_id)
        if not deleted:
            raise NotFoundError("CompanyHoliday", holiday_id)
