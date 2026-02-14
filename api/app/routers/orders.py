"""Orders router."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_current_admin,
    get_file_storage,
    get_order_service,
    verify_api_key,
)
from app.models.order import OrderStatus
from app.models.product import ProductType
from app.models.user import User
from app.schemas.order import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
)
from app.services.order_service import OrderService
from app.utils.exceptions import OrderNotFoundError
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
        "order_number": "ORD-2024-001",
        "ordered_at": "2024-01-15T10:30:00+09:00",
        "customer": {
            "name": "山田太郎",
            "postal_code": "123-4567",
            "address": "東京都渋谷区...",
            "phone": "03-1234-5678",
            "email": "yamada@example.com"
        },
        "items": [
            {
                "product_id": "uuid",
                "product_name": "Tシャツ Mサイズ 白",
                "product_type": "tshirt",
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
