"""Orders router."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_current_admin,
    get_file_storage,
    get_order_image_service,
    get_order_service,
    verify_api_key,
)
from app.models.order import OrderStatus
from app.models.product import ProductType
from app.models.user import User
from app.schemas.order import (
    OrderBulkStatusUpdate,
    OrderBulkStatusUpdateResponse,
    OrderCreate,
    OrderExportCsvRequest,
    OrderImageDownloadRequest,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
    OrderThumbnailDownloadRequest,
)
from urllib.parse import quote
from app.services.order_image_service import OrderImageService
from app.services.order_service import OrderService
from app.utils.exceptions import OrderNotFoundError, ValidationError
from app.utils.file_storage import FileStorage

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    service: OrderService = Depends(get_order_service),
    api_key_info: tuple[str, str] = Depends(verify_api_key),
) -> OrderResponse:
    """Create a new order from external sales site (API Key authentication).

    Request body (JSON):
    {
        "order_number": "0000001",
        "ordered_at": "2024-01-15T10:30:00+09:00",
        "customer": {
            "name": "山田太郎",
            "postal_code": "123-4567",
            "address_prefecture": "東京都",
            "address_city": "渋谷区〇〇町1-2-3",
            "address_building": "○○ビル101",
            "phone": "03-1234-5678",
            "email": "yamada@example.com"
        },
        "items": [
            {
                "uid": "0000011",
                "product_type": "tshirt",
                "product_name": "オリジナルTシャツ デザインA",
                "price": 2500,
                "quantity": 2,
                "size": "M",
                "position": "正面",
                "color": "白",
                "design_image_url": "https://example.com/designs/design1.png",
                "thumbnail_image_url": "https://example.com/thumbnails/thumb1.png"
            }
        ]
    }
    """
    _, order_source_id = api_key_info
    return await service.create(data, order_source_id=order_source_id)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    service: Annotated[OrderService, Depends(get_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: OrderStatus | None = None,
    product_type: ProductType | None = None,
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    search: str | None = None,
) -> OrderListResponse:
    """List orders with pagination and filters."""
    return await service.list(
        page=page,
        limit=limit,
        status=status,
        product_type=product_type,
        ordered_from=ordered_from,
        ordered_to=ordered_to,
        search=search,
    )


@router.post("/download-images")
async def download_order_images(
    data: OrderImageDownloadRequest,
    image_service: Annotated[OrderImageService, Depends(get_order_image_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """受注イメージ画像をZIPファイルとしてダウンロード."""
    zip_bytes = await image_service.collect_and_build_zip(data.order_ids)
    filename = image_service.generate_zip_filename()

    # RFC 5987: Use filename* for non-ASCII filenames
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


@router.post("/export-csv")
async def export_orders_csv(
    data: OrderExportCsvRequest,
    service: Annotated[OrderService, Depends(get_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """受注CSVをエクスポート

    選択された注文データを配送業者向けCSVとしてエクスポートします。
    18列のCSV形式で、配送元情報はOrderSourceから取得します。

    この機能は、まだShipmentが作成されていない注文（pending_order）の
    CSVエクスポートに使用されます。

    Args:
        data: エクスポート対象のorder_idsリスト

    Returns:
        UTF-8 BOM付きCSVファイル
    """
    csv_bytes, filename = await service.export_csv(data.order_ids)

    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@router.post("/download-thumbnails")
async def download_order_thumbnails(
    data: OrderThumbnailDownloadRequest,
    service: Annotated[OrderService, Depends(get_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """受注サムネイル画像をZIPファイルとしてダウンロード

    この機能は、まだShipmentが作成されていない注文（pending_order）の
    サムネイル画像をダウンロードするために使用されます。
    """
    zip_bytes, filename = await service.download_thumbnails(data.order_ids)

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


@router.patch("/bulk-status", response_model=OrderBulkStatusUpdateResponse)
async def bulk_update_order_status(
    data: OrderBulkStatusUpdate,
    service: Annotated[OrderService, Depends(get_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> OrderBulkStatusUpdateResponse:
    """受注ステータスを一括更新"""
    try:
        return await service.bulk_update_status(data.order_ids, data.status)
    except ValidationError as e:
        # shipped への直接遷移は 422 として返す
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    service: Annotated[OrderService, Depends(get_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> OrderResponse:
    """Get an order by ID."""
    return await service.get_by_id(order_id)


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    data: OrderStatusUpdate,
    service: Annotated[OrderService, Depends(get_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> OrderResponse:
    """Update order status."""
    return await service.update_status(order_id, data.status)


@router.get("/{order_id}/manufacturing-data")
async def download_manufacturing_data(
    order_id: str,
    service: Annotated[OrderService, Depends(get_order_service)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """Download manufacturing data for an order (legacy endpoint)."""
    order = await service.get_by_id(order_id)

    if not order.manufacturing_data or not order.manufacturing_data.path:
        raise OrderNotFoundError(order_id)

    content = await file_storage.get(order.manufacturing_data.path)
    if content is None:
        raise OrderNotFoundError(order_id)

    filename = order.manufacturing_data.filename or "manufacturing_data"

    return StreamingResponse(
        iter([content]),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
