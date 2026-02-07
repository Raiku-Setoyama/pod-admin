"""Manufacturers router."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from urllib.parse import quote

from app.dependencies import (
    get_chat_service,
    get_current_admin,
    get_manufacturer_order_service,
    get_manufacturer_service,
    get_order_list_service,
)
from app.models.chat_message import MessageSender
from app.models.order import OrderStatus
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
)
from app.schemas.manufacturer import (
    ManufacturerCreate,
    ManufacturerListResponse,
    ManufacturerOrderItemListResponse,
    ManufacturerOrderStatusUpdate,
    ManufacturerOrderSummaryListResponse,
    ManufacturerResponse,
    ManufacturerUpdate,
)
from app.services.chat_service import ChatService
from app.services.manufacturer_order_service import ManufacturerOrderService
from app.services.manufacturer_service import ManufacturerService
from app.services.order_list_service import OrderListService

router = APIRouter(prefix="/manufacturers", tags=["manufacturers"])


@router.get("", response_model=ManufacturerListResponse)
async def list_manufacturers(
    service: Annotated[ManufacturerService, Depends(get_manufacturer_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    is_active: bool | None = None,
    search: str | None = None,
) -> ManufacturerListResponse:
    """List manufacturers with pagination and filters."""
    return await service.list(
        page=page,
        limit=limit,
        is_active=is_active,
        search=search,
    )


@router.post("", response_model=ManufacturerResponse, status_code=201)
async def create_manufacturer(
    data: ManufacturerCreate,
    service: Annotated[ManufacturerService, Depends(get_manufacturer_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturerResponse:
    """Create a new manufacturer."""
    return await service.create(data)


# === メーカー発注管理エンドポイント ===
# Note: These routes must be defined BEFORE /{manufacturer_id} to avoid path conflicts


@router.get("/order-summary", response_model=ManufacturerOrderSummaryListResponse)
async def get_manufacturer_order_summary(
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> ManufacturerOrderSummaryListResponse:
    """メーカー別発注サマリー一覧を取得

    発注中（ORDERED）ステータスの受注明細を持つメーカーの一覧を返します。
    各メーカーの発注明細数、合計数量、合計金額を集計して返します。
    """
    return await service.get_order_summary_list(page=page, limit=limit)


@router.get("/{manufacturer_id}", response_model=ManufacturerResponse)
async def get_manufacturer(
    manufacturer_id: str,
    service: Annotated[ManufacturerService, Depends(get_manufacturer_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturerResponse:
    """Get a manufacturer by ID."""
    return await service.get_by_id(manufacturer_id)


@router.patch("/{manufacturer_id}", response_model=ManufacturerResponse)
async def update_manufacturer(
    manufacturer_id: str,
    data: ManufacturerUpdate,
    service: Annotated[ManufacturerService, Depends(get_manufacturer_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturerResponse:
    """Update a manufacturer."""
    return await service.update(manufacturer_id, data)


@router.delete("/{manufacturer_id}", status_code=204)
async def delete_manufacturer(
    manufacturer_id: str,
    service: Annotated[ManufacturerService, Depends(get_manufacturer_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a manufacturer."""
    await service.delete(manufacturer_id)


@router.get("/{manufacturer_id}/order-list")
async def download_order_list(
    manufacturer_id: str,
    service: Annotated[OrderListService, Depends(get_order_list_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    status: OrderStatus | None = None,
) -> StreamingResponse:
    """Download order list CSV for a manufacturer.

    Generates a CSV file with the following columns:
    - 注文日 (MM月DD日 format)
    - 注文番号
    - 製品番号 (OrderItem.uid)
    - 商品名
    - 個数
    - シール用テキスト情報

    Args:
        manufacturer_id: The manufacturer ID.
        ordered_from: Optional start date filter.
        ordered_to: Optional end date filter.
        status: Optional order status filter.

    Returns:
        CSV file as StreamingResponse.
    """
    csv_content, filename = await service.generate_order_list_csv(
        manufacturer_id=manufacturer_id,
        ordered_from=ordered_from,
        ordered_to=ordered_to,
        status=status,
    )

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{manufacturer_id}/order-items", response_model=ManufacturerOrderItemListResponse)
async def get_manufacturer_order_items(
    manufacturer_id: str,
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturerOrderItemListResponse:
    """メーカー別受注明細一覧を取得

    指定されたメーカーに紐づく発注中（ORDERED）ステータスの受注明細一覧を返します。
    """
    return await service.get_order_items_by_manufacturer(manufacturer_id)


@router.get("/{manufacturer_id}/order-documents")
async def download_manufacturer_order_documents(
    manufacturer_id: str,
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """メーカー別発注資料ZIPをダウンロード

    指定されたメーカーに紐づく発注中（ORDERED）ステータスの受注明細を含む
    発注資料ZIPファイルを生成してダウンロードします。

    ZIPには以下が含まれます:
    - 商品タイプ別のCSV（発注リスト）
    - デザイン画像
    - サムネイル画像
    """
    content, filename = await service.generate_order_documents(manufacturer_id)

    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([content]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@router.patch("/{manufacturer_id}/order-status")
async def update_manufacturer_order_status(
    manufacturer_id: str,
    data: ManufacturerOrderStatusUpdate,
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> dict:
    """メーカーの受注ステータスを一括更新

    指定されたメーカーに紐づく発注中（ORDERED）ステータスの受注を
    指定されたステータス（manufacturing または delivered）に一括更新します。

    Args:
        manufacturer_id: メーカーID
        data: ステータス更新リクエスト
            - status: 新しいステータス（manufacturing または delivered）
            - order_item_ids: 更新対象のOrderItem ID（省略時は全て）
            - note: 備考

    Returns:
        updated_count: 更新された受注数
    """
    updated_count = await service.update_order_status(manufacturer_id, data)
    return {"updated_count": updated_count}


# === チャットエンドポイント ===


@router.get("/{manufacturer_id}/chat", response_model=ChatMessageListResponse)
async def get_chat_messages(
    manufacturer_id: str,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> ChatMessageListResponse:
    """メーカーとのチャットメッセージ一覧を取得"""
    return await service.get_messages(
        manufacturer_id=manufacturer_id,
        page=page,
        limit=limit,
    )


@router.post("/{manufacturer_id}/chat", response_model=ChatMessageResponse)
async def send_chat_message(
    manufacturer_id: str,
    data: ChatMessageCreate,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ChatMessageResponse:
    """メーカーにチャットメッセージを送信"""
    return await service.send_message(
        manufacturer_id=manufacturer_id,
        data=data,
        sender_type=MessageSender.ADMIN,
        sender_name=current_user.name,
        attachments=None,
    )
