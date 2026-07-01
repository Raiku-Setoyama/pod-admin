"""Manufacturing data router (admin).

製造データの状態一覧・手動リトライを提供する。
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.dependencies import get_current_admin, get_manufacturing_data_service
from app.models.user import User
from app.schemas.manufacturing_data import (
    ManufacturingDataListResponse,
    ManufacturingDataResponse,
)
from app.services.manufacturing_data_service import ManufacturingDataService

router = APIRouter(prefix="/manufacturing-data", tags=["manufacturing-data"])


@router.get("", response_model=ManufacturingDataListResponse)
async def list_manufacturing_data(
    service: Annotated[ManufacturingDataService, Depends(get_manufacturing_data_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    order_source_id: str | None = None,
    product_code: str | None = None,
) -> ManufacturingDataListResponse:
    """製造データ一覧を取得する（ステータス/受注元/商品コードでフィルタ可能）."""
    return await service.list(
        page=page,
        limit=limit,
        status=status,
        order_source_id=order_source_id,
        product_code=product_code,
    )


@router.post("/{mfg_data_id}/retry", response_model=ManufacturingDataResponse)
async def retry_manufacturing_data(
    mfg_data_id: str,
    background_tasks: BackgroundTasks,
    service: Annotated[ManufacturingDataService, Depends(get_manufacturing_data_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturingDataResponse:
    """製造データ生成を手動で再駆動する（失敗・停滞した行の再実行）."""
    return await service.retry(mfg_data_id, background_tasks)
