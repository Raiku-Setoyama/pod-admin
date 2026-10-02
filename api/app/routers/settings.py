"""Settings router."""

from collections.abc import Callable
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
from app.schemas.app_setting import (
    AppSettingListResponse,
    AppSettingResponse,
    AppSettingUpdate,
)
from app.services import monitoring_alert_notification, order_deadline
from app.services.estimated_shipping_service import recalculate_all_estimated_shipping_dates
from app.services.external_order_notification import (
    NOTIFICATION_ENABLED_KEY,
    NOTIFICATION_RECIPIENTS_KEY,
    validate_setting_value,
)
from app.services.manufacturer_notification import (
    DIGEST_ENABLED_KEY,
    DIGEST_SEND_TIME_KEY,
    validate_digest_setting_value,
)
from app.utils.exceptions import AppException

router = APIRouter(prefix="/settings", tags=["settings"])


def _keyed(validate: Callable[[str, str], None], key: str) -> Callable[[str], None]:
    return lambda value: validate(key, value)


# キー → 値の検証（不正なら日本語メッセージの ValueError）。新しい設定はここに足す。
# 注文〆切時間は空文字を「無効化」として許可する。既存注文の再計算はしない
# （〆切変更は新規注文にのみ適用する方針）。
_SETTING_VALIDATORS: dict[str, Callable[[str], None]] = {
    **{
        key: _keyed(validate_setting_value, key)
        for key in (NOTIFICATION_ENABLED_KEY, NOTIFICATION_RECIPIENTS_KEY)
    },
    **{
        key: _keyed(validate_digest_setting_value, key)
        for key in (DIGEST_ENABLED_KEY, DIGEST_SEND_TIME_KEY)
    },
    **{
        key: _keyed(monitoring_alert_notification.validate_setting_value, key)
        for key in (
            monitoring_alert_notification.ALERT_ENABLED_KEY,
            monitoring_alert_notification.ALERT_RECIPIENTS_KEY,
        )
    },
    order_deadline.ORDER_DEADLINE_TIME_KEY: order_deadline.validate_setting_value,
}


@router.get("", response_model=AppSettingListResponse)
async def list_settings(
    repo: Annotated[AppSettingRepository, Depends(get_app_setting_repository)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> AppSettingListResponse:
    """全設定を取得する."""
    settings = await repo.find_all()
    return AppSettingListResponse(
        items=[AppSettingResponse.model_validate(s) for s in settings]
    )


@router.put("/{key}", response_model=AppSettingResponse)
async def update_setting(
    key: str,
    data: AppSettingUpdate,
    repo: Annotated[AppSettingRepository, Depends(get_app_setting_repository)],
    holiday_repo: Annotated[CompanyHolidayRepository, Depends(get_company_holiday_repository)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> AppSettingResponse:
    """設定値を更新する."""
    # Validate shipping_preparation_days
    if key == "shipping_preparation_days":
        try:
            days = int(data.value)
            if days < 0 or days > 365:
                raise ValueError
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="発送準備日数は0〜365の整数で指定してください",
            ) from None

    # 機能ごとの設定値の検証。AppException を使うことで、フロントの共通エラー envelope
    # （error.message）に日本語メッセージが乗り、422 として画面に表示できる。
    validator = _SETTING_VALIDATORS.get(key)
    if validator is not None:
        try:
            validator(data.value)
        except ValueError as e:
            raise AppException(422, "VALIDATION_ERROR", str(e)) from None

    setting = await repo.upsert(key, data.value)

    # 発送準備日数の変更時は未出荷注文を再計算
    if key == "shipping_preparation_days":
        await recalculate_all_estimated_shipping_dates(db, repo, holiday_repo)

    return AppSettingResponse.model_validate(setting)
