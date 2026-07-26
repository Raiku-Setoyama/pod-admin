"""Manufacturing data router (admin).

製造データの状態一覧・手動リトライ・再作成、および元画像（PNGレイヤー）の差し替えを提供する。
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile

from app.dependencies import get_current_admin, get_manufacturing_data_service
from app.models.user import User
from app.schemas.manufacturing_data import (
    ManufacturingDataDetailResponse,
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


@router.get("/{mfg_data_id}", response_model=ManufacturingDataDetailResponse)
async def get_manufacturing_data(
    mfg_data_id: str,
    service: Annotated[ManufacturingDataService, Depends(get_manufacturing_data_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturingDataDetailResponse:
    """製造データ詳細を取得する（元画像レイヤーの由来つき一覧を含む）."""
    return await service.get_detail(mfg_data_id)


@router.post("/{mfg_data_id}/retry", response_model=ManufacturingDataResponse)
async def retry_manufacturing_data(
    mfg_data_id: str,
    background_tasks: BackgroundTasks,
    service: Annotated[ManufacturingDataService, Depends(get_manufacturing_data_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturingDataResponse:
    """製造データ生成を手動で再駆動する（失敗・停滞した行の再実行）."""
    return await service.retry(mfg_data_id, background_tasks)


@router.post("/{mfg_data_id}/regenerate", response_model=ManufacturingDataResponse)
async def regenerate_manufacturing_data(
    mfg_data_id: str,
    background_tasks: BackgroundTasks,
    service: Annotated[ManufacturingDataService, Depends(get_manufacturing_data_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturingDataResponse:
    """製造データを手動で再作成する（製造着手前の明細のみ、同じ元データで再生成）.

    製造中/納入済みの注文と共有されている製造データは、その完成データを保護するため
    409（ConflictError）で拒否する。生成中の行も進行中ジョブと競合させないため拒否する。
    """
    return await service.regenerate(mfg_data_id, background_tasks)


@router.post("/{mfg_data_id}/source-images", response_model=ManufacturingDataDetailResponse)
async def replace_source_images(
    mfg_data_id: str,
    background_tasks: BackgroundTasks,
    service: Annotated[ManufacturingDataService, Depends(get_manufacturing_data_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    color: Annotated[UploadFile | None, File()] = None,
    cutline: Annotated[UploadFile | None, File()] = None,
    white: Annotated[UploadFile | None, File()] = None,
    design: Annotated[UploadFile | None, File()] = None,
) -> ManufacturingDataDetailResponse:
    """元画像（PNGレイヤー）を差し替えて製造データを再生成する.

    差し替えたいレイヤー種別と同名のファイル項目に PNG を指定する（複数指定可。1リクエスト
    で差し替えて再生成は1回だけ起動する）。差し替えられるのは行が既に持つレイヤー種別のみ。

    再作成と同じゲートを適用し、生成中／製造中・納入済みの注文と共有されている製造データは
    409 で拒否する。
    """
    uploads = {
        "color": color,
        "cutline": cutline,
        "white": white,
        "design": design,
    }
    return await service.replace_source_images(
        mfg_data_id,
        {layer: file for layer, file in uploads.items() if file is not None},
        replaced_by=current_user.email,
        background_tasks=background_tasks,
    )


@router.get("/{mfg_data_id}/source-images/{layer_type}")
async def download_source_image(
    mfg_data_id: str,
    layer_type: str,
    service: Annotated[ManufacturingDataService, Depends(get_manufacturing_data_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> Response:
    """差し替え済み元画像を取得する（プレビュー用）.

    外部受注由来（URL のみ）のレイヤーは pod-admin 側に実体を持たないため 404 を返す。
    """
    content = await service.get_source_image(mfg_data_id, layer_type)
    return Response(content=content, media_type="image/png")
