"""Manufacturing data status & retry endpoints (admin)."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_current_admin,
    get_db_session,
    get_manufacturing_data_repository,
)
from app.models.user import User
from app.repositories.manufacturing_data_repository import ManufacturingDataRepository
from app.schemas.manufacturing_data import (
    ManufacturingDataListResponse,
    ManufacturingDataResponse,
)
from app.services.manufacturing_data_service import run_generate_manufacturing_data
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/manufacturing-data", tags=["manufacturing-data"])


@router.get("", response_model=ManufacturingDataListResponse)
async def list_manufacturing_data(
    repo: Annotated[ManufacturingDataRepository, Depends(get_manufacturing_data_repository)],
    current_user: Annotated[User, Depends(get_current_admin)],
    order_id: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> ManufacturingDataListResponse:
    """製造データ一覧（管理者）。order_id 指定でその注文分、status で絞り込み。"""
    if order_id:
        rows = await repo.find_by_order_id(order_id)
        if status:
            rows = [row for row in rows if row.status == status]
    else:
        rows = await repo.list_recent(limit=limit, status=status)
    return ManufacturingDataListResponse(
        items=[ManufacturingDataResponse.model_validate(row) for row in rows],
        total=len(rows),
    )


@router.post("/{mfg_data_id}/retry", response_model=ManufacturingDataResponse)
async def retry_manufacturing_data(
    mfg_data_id: str,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    repo: Annotated[ManufacturingDataRepository, Depends(get_manufacturing_data_repository)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturingDataResponse:
    """失敗 / スタックした製造データ生成を手動リトライ（管理者）。

    行を pending に戻し、生成をバックグラウンドで再実行する。API 再起動で generating の
    まま残った行もこれで再駆動できる（pending 確定後にワーカーが claim するため）。
    """
    md = await repo.reset_to_pending(mfg_data_id)
    if md is None:
        raise NotFoundError("ManufacturingData", mfg_data_id)
    # バックグラウンドの生成ワーカーが pending を確実に見えるよう、ここで確定させる
    await session.commit()
    # onupdate で更新された updated_at 等を再読込（model_validate 時の遅延ロードを回避）
    await session.refresh(md)
    background_tasks.add_task(run_generate_manufacturing_data, mfg_data_id)
    return ManufacturingDataResponse.model_validate(md)
