"""Manufacturers router."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from urllib.parse import quote

from app.dependencies import (
    get_chat_service,
    get_current_admin,
    get_invoice_service,
    get_manufacturer_notification_service,
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
from app.schemas.invoice import InvoiceItemRequest
from app.schemas.manufacturer import (
    AllManufacturerOrderItemListResponse,
    ManufacturerCreate,
    ManufacturerListResponse,
    ManufacturerOrderItemListResponse,
    ManufacturerOrderStatusUpdate,
    ManufacturerOrderSummaryListResponse,
    ManufacturerResponse,
    ManufacturerUpdate,
)
from app.schemas.manufacturer_notification import (
    ManufacturerNotificationSettingsResponse,
    ManufacturerNotificationSettingsUpdate,
)
from app.services.chat_service import ChatService
from app.services.invoice_service import InvoiceService
from app.services.manufacturer_notification import ManufacturerNotificationService
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


@router.get("/all-order-items", response_model=AllManufacturerOrderItemListResponse)
async def get_all_manufacturer_order_items(
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    product_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    manufacturer_id: str | None = None,
    expected_delivery_from: date | None = None,
    expected_delivery_to: date | None = None,
) -> AllManufacturerOrderItemListResponse:
    """全メーカー横断の受注明細一覧を取得

    全メーカーの発注明細を横断的に一覧表示します。
    デフォルトでは shipped 以外の全ステータスを返します。

    Args:
        ordered_from: 発注日From
        ordered_to: 発注日To
        product_type: 商品タイプフィルター
        status: ステータスフィルター（ordered, manufacturing, delivered）
        search: キーワード検索（注文番号、製品番号、商品名）
        manufacturer_id: メーカーIDフィルター
        expected_delivery_from: 納品予定日From
        expected_delivery_to: 納品予定日To
    """
    return await service.get_all_order_items(
        ordered_from=ordered_from,
        ordered_to=ordered_to,
        product_type=product_type,
        status=status,
        search=search,
        manufacturer_id=manufacturer_id,
        expected_delivery_from=expected_delivery_from,
        expected_delivery_to=expected_delivery_to,
    )


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


# === メーカー別 通知設定エンドポイント ===


@router.get(
    "/{manufacturer_id}/notification-settings",
    response_model=ManufacturerNotificationSettingsResponse,
)
async def get_manufacturer_notification_settings(
    manufacturer_id: str,
    service: Annotated[
        ManufacturerNotificationService, Depends(get_manufacturer_notification_service)
    ],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturerNotificationSettingsResponse:
    """メーカー別の通知設定を取得する（未登録ならデフォルト値を返す）."""
    return await service.get_settings(manufacturer_id)


@router.put(
    "/{manufacturer_id}/notification-settings",
    response_model=ManufacturerNotificationSettingsResponse,
)
async def update_manufacturer_notification_settings(
    manufacturer_id: str,
    data: ManufacturerNotificationSettingsUpdate,
    service: Annotated[
        ManufacturerNotificationService, Depends(get_manufacturer_notification_service)
    ],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ManufacturerNotificationSettingsResponse:
    """メーカー別の通知設定（To/CC・ON/OFF）を更新する."""
    return await service.update_settings(manufacturer_id, data)


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
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    product_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    expected_delivery_from: date | None = None,
    expected_delivery_to: date | None = None,
) -> ManufacturerOrderItemListResponse:
    """メーカー別受注明細一覧を取得

    指定されたメーカーに紐づく受注明細一覧を返します。
    デフォルトでは shipped 以外の全ステータスを返します。

    Args:
        manufacturer_id: メーカーID
        ordered_from: 発注日From
        ordered_to: 発注日To
        product_type: 商品タイプフィルター
        status: ステータスフィルター（ordered, manufacturing, delivered）
        search: キーワード検索（注文番号、製品番号、商品名）
        expected_delivery_from: 納品予定日From
        expected_delivery_to: 納品予定日To
    """
    return await service.get_order_items_by_manufacturer(
        manufacturer_id,
        ordered_from=ordered_from,
        ordered_to=ordered_to,
        product_type=product_type,
        status=status,
        search=search,
        expected_delivery_from=expected_delivery_from,
        expected_delivery_to=expected_delivery_to,
    )


@router.get("/{manufacturer_id}/order-documents")
async def download_manufacturer_order_documents(
    manufacturer_id: str,
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    product_type: str | None = None,
    order_item_ids: str | None = None,
    status: str | None = None,
) -> StreamingResponse:
    """メーカー別発注資料ZIPをダウンロード

    指定されたメーカーに紐づく受注明細を含む
    発注資料ZIPファイルを生成してダウンロードします。
    管理者からのダウンロードではステータス更新は行いません。

    ZIPには以下が含まれます:
    - 商品タイプ別のCSV（発注リスト）
    - デザイン画像
    - サムネイル画像
    """
    item_ids = order_item_ids.split(",") if order_item_ids else None
    content, filename = await service.generate_order_documents(
        manufacturer_id,
        ordered_from=ordered_from,
        ordered_to=ordered_to,
        product_type=product_type,
        order_item_ids=item_ids,
        status=status,
        update_status=False,  # 管理者からのダウンロードではステータス更新しない
    )

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

    指定されたメーカーに紐づく受注を指定されたステータスに一括更新します。
    OrderItem単位でステータスを更新し、全OrderItemがdeliveredになった場合のみ
    Shipmentを自動作成します。

    Args:
        manufacturer_id: メーカーID
        data: ステータス更新リクエスト
            - status: 新しいステータス（ordered, manufacturing, delivered）
            - order_item_ids: 更新対象のOrderItem ID（省略時は全て）
            - note: 備考

    Returns:
        updated_count: 更新されたOrderItem数
        shipments_created: 作成されたShipment数（全製品がdeliveredになった注文のみ）
    """
    updated_count, shipments_created = await service.update_order_status(manufacturer_id, data)
    return {"updated_count": updated_count, "shipments_created": shipments_created}


# === 請求書エンドポイント ===


@router.post("/{manufacturer_id}/invoices")
async def generate_invoice(
    manufacturer_id: str,
    data: InvoiceItemRequest,
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """請求書PDFを発行（選択発行）

    指定された受注明細に対する請求書PDFを生成してダウンロードします。

    Args:
        manufacturer_id: メーカーID
        data: 請求書発行リクエスト
            - order_item_ids: 請求対象のOrderItem IDリスト

    Returns:
        請求書PDFファイル
    """
    pdf_bytes, filename, item_count, total_amount = await service.generate_invoice_by_items(
        manufacturer_id, data.order_item_ids
    )

    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "X-Invoice-Item-Count": str(item_count),
            "X-Invoice-Total-Amount": str(total_amount),
        },
    )


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
