"""データ出力ルーター（REQ-0047）.

管理画面の「データ出力」タブから、項目・絞り込み・並べ替えを指定して CSV を出力する。
管理者のみ。メーカーポータルからは使わない。

既存の ``POST /orders/export-csv`` / ``POST /shipments/export-csv``（配送業者向けの
固定 18 列）とは別の導線であり、それらは変更しない（ADR-0024）。
"""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_admin, get_data_export_service
from app.models.user import User
from app.schemas.data_export import DataExportColumnsResponse, DataExportCsvRequest
from app.services.data_export_service import DataExportService

router = APIRouter(prefix="/data-export", tags=["data-export"])


@router.get("/columns", response_model=DataExportColumnsResponse)
async def list_data_export_columns(
    service: Annotated[DataExportService, Depends(get_data_export_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> DataExportColumnsResponse:
    """列にできる項目の一覧（画面に並べる順）."""
    return service.list_columns()


@router.post("/csv")
async def export_data_csv(
    data: DataExportCsvRequest,
    service: Annotated[DataExportService, Depends(get_data_export_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """選んだ項目だけを列にした CSV（UTF-8 BOM 付き）を出力する.

    1 行は受注明細 1 件。対象が 0 件のときはヘッダ行だけを返す。
    """
    csv_bytes, filename = await service.export_csv(data)
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
