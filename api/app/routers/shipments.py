"""Shipments router."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_admin, get_shipment_service
from app.models.shipment import ShipmentStatus
from app.models.user import User
from urllib.parse import quote

from app.schemas.shipment import (
    ShipmentBulkStatusUpdate,
    ShipmentBulkStatusUpdateResponse,
    ShipmentExportRequest,
    ShipmentListResponse,
    ShipmentResponse,
    ShipmentStatusUpdate,
    ShipmentThumbnailDownloadRequest,
    TrackingFileImportResult,
    TrackingImportRequest,
)
from app.services.shipment_service import ShipmentService
from app.utils.csv_generator import CSVGenerator

router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.get("", response_model=ShipmentListResponse)
async def list_shipments(
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: ShipmentStatus | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    search: str | None = None,
    tracking_number: str | None = None,
    carrier: str | None = None,
    shipped_from: date | None = None,
    shipped_to: date | None = None,
    delivered_from: date | None = None,
    delivered_to: date | None = None,
    sort_by: Literal["created_at", "shipped_at", "delivered_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> ShipmentListResponse:
    """List shipments with pagination and filters."""
    return await service.list(
        page=page,
        limit=limit,
        status=status,
        created_from=created_from,
        created_to=created_to,
        search=search,
        tracking_number=tracking_number,
        carrier=carrier,
        shipped_from=shipped_from,
        shipped_to=shipped_to,
        delivered_from=delivered_from,
        delivered_to=delivered_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.patch("/bulk-status", response_model=ShipmentBulkStatusUpdateResponse)
async def bulk_update_shipment_status(
    data: ShipmentBulkStatusUpdate,
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ShipmentBulkStatusUpdateResponse:
    """配送ステータスを一括更新"""
    return await service.bulk_update_status(data)


@router.post("/export-csv")
async def export_shipments_csv(
    data: ShipmentExportRequest,
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """配送CSVをエクスポート

    選択された発送データを配送業者向けCSVとしてエクスポートします。
    17列のCSV形式で、配送元情報はOrderSourceから取得します。

    Args:
        data: エクスポート対象のshipment_idsリスト

    Returns:
        UTF-8 BOM付きCSVファイル
    """
    csv_bytes, filename = await service.export_csv(data.shipment_ids)

    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@router.post("/download-thumbnails")
async def download_thumbnails(
    data: ShipmentThumbnailDownloadRequest,
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """配送サムネイル画像をZIPファイルとしてダウンロード."""
    zip_bytes, filename = await service.download_thumbnails(data.shipment_ids)

    encoded_filename = quote(filename)
    content_disposition = (
        f"attachment; filename*=UTF-8''{encoded_filename}"
    )

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Disposition": content_disposition,
        },
    )


@router.post("/import", response_model=TrackingFileImportResult)
async def import_tracking_from_file(
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    file: UploadFile = File(...),
) -> TrackingFileImportResult:
    """CSV/XLSXファイルから伝票番号を一括インポート.

    注文番号・伝票番号・運送会社名を含むCSV/XLSXファイルをアップロードし、
    対応する配送レコードの伝票番号・運送会社を一括更新します。
    """
    return await service.import_tracking_from_file(file)


@router.get("/import-template")
async def download_import_template(
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """伝票番号インポート用のサンプルCSVテンプレートをダウンロード."""
    csv_bytes, filename = await service.generate_import_template()

    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@router.get("/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: str,
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ShipmentResponse:
    """Get a shipment by ID."""
    return await service.get_by_id(shipment_id)


@router.patch("/{shipment_id}/status", response_model=ShipmentResponse)
async def update_shipment_status(
    shipment_id: str,
    data: ShipmentStatusUpdate,
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ShipmentResponse:
    """Update shipment status."""
    return await service.update_status(shipment_id, data)


@router.post("/{shipment_id}/packing-photo", response_model=ShipmentResponse)
async def upload_packing_photo(
    shipment_id: str,
    photo: Annotated[UploadFile, File()],
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ShipmentResponse:
    """Upload packing photo for a shipment."""
    return await service.upload_packing_photo(shipment_id, photo)


@router.get("/{shipment_id}/packing-photo")
async def get_packing_photo(
    shipment_id: str,
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """Get packing photo for a shipment.

    Returns the packing photo image as a binary stream with appropriate Content-Type.
    Requires authentication.

    Args:
        shipment_id: The shipment ID (UUID).

    Returns:
        StreamingResponse with image binary data.

    Raises:
        404: If shipment not found or has no packing photo.
        401: If not authenticated.
    """
    content, content_type = await service.get_packing_photo(shipment_id)
    return StreamingResponse(
        iter([content]),
        media_type=content_type,
    )


@router.post("/import-tracking", response_model=list[ShipmentResponse])
async def import_tracking_numbers(
    data: TrackingImportRequest,
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> list[ShipmentResponse]:
    """Import tracking numbers from CSV data."""
    return await service.import_tracking_numbers(data)


@router.get("/{shipment_id}/documents")
async def download_shipment_documents(
    shipment_id: str,
    service: Annotated[ShipmentService, Depends(get_shipment_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    format: Literal["shipping_label", "packing_list"] = Query("shipping_label"),
    carrier: str = Query("yamato"),
) -> StreamingResponse:
    """Download shipment documents."""
    shipment = await service.get_by_id(shipment_id)

    csv_gen = CSVGenerator()

    # ShipmentResponse already contains customer info from first order
    if not shipment.customer_name:
        raise HTTPException(status_code=400, detail="Shipment has no orders")

    if format == "shipping_label":
        content = csv_gen.generate_shipping_csv(
            carrier=carrier,
            shipments=[{
                "postal_code": shipment.customer_postal_code,
                "address": shipment.customer_full_address,
                "name": shipment.customer_name,
                "phone": shipment.customer_phone,
                "product_name": "グッズ",
                "quantity": len(shipment.items),
            }],
        )
        filename = f"配送ラベル_{shipment_id[:8]}.csv"
    else:  # packing_list
        items = [{"product_name": item.product_name, "size": "", "quantity": 1} for item in shipment.items]
        content = csv_gen.generate_packing_list_csv(
            order_number=shipment.items[0].order_number if shipment.items else "",
            items=items,
        )
        filename = f"同梱リスト_{shipment_id[:8]}.csv"

    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )
