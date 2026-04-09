"""Company holidays router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_app_setting_repository,
    get_company_holiday_repository,
    get_current_admin,
    get_db_session,
)
from app.models.user import User
from app.repositories.app_setting_repository import AppSettingRepository
from app.repositories.company_holiday_repository import CompanyHolidayRepository
from app.schemas.company_holiday import (
    CompanyHolidayCreate,
    CompanyHolidayListResponse,
    CompanyHolidayResponse,
)
from app.services.estimated_shipping_service import recalculate_all_estimated_shipping_dates

router = APIRouter(prefix="/company-holidays", tags=["company-holidays"])


@router.get("", response_model=CompanyHolidayListResponse)
async def list_company_holidays(
    repo: Annotated[CompanyHolidayRepository, Depends(get_company_holiday_repository)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> CompanyHolidayListResponse:
    """会社休日一覧を取得する."""
    holidays = await repo.find_all()
    return CompanyHolidayListResponse(
        items=[CompanyHolidayResponse.model_validate(h) for h in holidays]
    )


@router.post("", response_model=CompanyHolidayResponse, status_code=201)
async def create_company_holiday(
    data: CompanyHolidayCreate,
    repo: Annotated[CompanyHolidayRepository, Depends(get_company_holiday_repository)],
    setting_repo: Annotated[AppSettingRepository, Depends(get_app_setting_repository)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> CompanyHolidayResponse:
    """会社休日を追加する."""
    existing = await repo.find_by_date(data.date)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"{data.date} は既に登録されています",
        )

    holiday = await repo.create(data.date, data.name)

    # 休日追加時は未出荷注文の配送予定日を再計算
    await recalculate_all_estimated_shipping_dates(db, setting_repo, repo)

    return CompanyHolidayResponse.model_validate(holiday)


@router.delete("/{holiday_id}", status_code=204)
async def delete_company_holiday(
    holiday_id: str,
    repo: Annotated[CompanyHolidayRepository, Depends(get_company_holiday_repository)],
    setting_repo: Annotated[AppSettingRepository, Depends(get_app_setting_repository)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> None:
    """会社休日を削除する."""
    deleted = await repo.delete(holiday_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="休日が見つかりません")

    # 休日削除時は未出荷注文の配送予定日を再計算
    await recalculate_all_estimated_shipping_dates(db, setting_repo, repo)
