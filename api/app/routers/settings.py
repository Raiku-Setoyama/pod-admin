"""Settings router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_current_admin, get_settings_service
from app.models.user import User
from app.schemas.settings import (
    CompanyHolidayCreate,
    CompanyHolidayListResponse,
    CompanyHolidayResponse,
    ShippingPreparationDaysResponse,
    ShippingPreparationDaysUpdate,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/shipping-preparation-days", response_model=ShippingPreparationDaysResponse)
async def get_shipping_preparation_days(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ShippingPreparationDaysResponse:
    """発送準備日数を取得."""
    return await service.get_shipping_preparation_days()


@router.put("/shipping-preparation-days", response_model=ShippingPreparationDaysResponse)
async def update_shipping_preparation_days(
    data: ShippingPreparationDaysUpdate,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ShippingPreparationDaysResponse:
    """発送準備日数を更新."""
    return await service.update_shipping_preparation_days(data)


@router.get("/company-holidays", response_model=CompanyHolidayListResponse)
async def get_company_holidays(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> CompanyHolidayListResponse:
    """独自休日一覧を取得."""
    return await service.get_company_holidays()


@router.post("/company-holidays", response_model=CompanyHolidayResponse, status_code=201)
async def create_company_holiday(
    data: CompanyHolidayCreate,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> CompanyHolidayResponse:
    """独自休日を追加."""
    return await service.create_company_holiday(data)


@router.delete("/company-holidays/{holiday_id}", status_code=204)
async def delete_company_holiday(
    holiday_id: str,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> None:
    """独自休日を削除."""
    await service.delete_company_holiday(holiday_id)
