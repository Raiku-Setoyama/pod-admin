"""Manufacturer portal router."""

from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Header, Query
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_chat_service,
    get_current_manufacturer,
    get_manufacturer_order_service,
    get_manufacturer_portal_service,
)
from app.models.chat_message import MessageSender
from app.models.manufacturer import Manufacturer
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
)
from app.schemas.manufacturer import ManufacturerOrderItemListResponse
from app.schemas.manufacturer_portal import (
    ManufacturerLoginRequest,
    ManufacturerLoginResponse,
)
from app.services.chat_service import ChatService
from app.services.manufacturer_order_service import ManufacturerOrderService
from app.services.manufacturer_portal_service import ManufacturerPortalService
from app.utils.security import decode_token

router = APIRouter(prefix="/manufacturer-portal", tags=["manufacturer-portal"])


@router.post("/login", response_model=ManufacturerLoginResponse)
async def login(
    request: ManufacturerLoginRequest,
    service: Annotated[ManufacturerPortalService, Depends(get_manufacturer_portal_service)],
) -> ManufacturerLoginResponse:
    """メーカーログイン

    メールアドレスとパスワードで認証し、アクセストークンを返します。
    """
    token_response, manufacturer = await service.login(request.email, request.password)
    return ManufacturerLoginResponse(
        access_token=token_response.access_token,
        refresh_token=token_response.refresh_token,
        manufacturer_id=manufacturer.id,
        manufacturer_name=manufacturer.name,
    )


@router.get("/debug-token")
async def debug_token(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """デバッグ用: トークンの検証状態を確認"""
    if not authorization:
        return {"error": "No authorization header", "authorization": None}

    if not authorization.startswith("Bearer "):
        return {"error": "Invalid format", "authorization": authorization[:50]}

    token = authorization[7:]
    payload = decode_token(token)

    return {
        "token_first_20": token[:20] if token else None,
        "token_length": len(token) if token else 0,
        "payload": payload,
        "has_manufacturer_id": bool(payload and payload.get("manufacturer_id")) if payload else False,
    }


@router.get("/order-items", response_model=ManufacturerOrderItemListResponse)
async def get_order_items(
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    product_type: str | None = None,
) -> ManufacturerOrderItemListResponse:
    """発注中アイテム一覧を取得

    ログイン中のメーカーに紐づく発注中（ORDERED）ステータスの受注明細一覧を返します。
    """
    return await service.get_order_items_by_manufacturer(
        manufacturer.id,
        ordered_from=ordered_from,
        ordered_to=ordered_to,
        product_type=product_type,
    )


@router.get("/order-documents")
async def download_order_documents(
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    product_type: str | None = None,
    order_item_ids: str | None = None,
) -> StreamingResponse:
    """発注資料ZIPをダウンロード

    ログイン中のメーカーに紐づく発注中（ORDERED）ステータスの受注明細を含む
    発注資料ZIPファイルを生成してダウンロードします。

    ZIPには以下が含まれます:
    - 商品タイプ別のCSV（発注リスト）
    - デザイン画像
    - サムネイル画像
    """
    item_ids = order_item_ids.split(",") if order_item_ids else None
    content, filename = await service.generate_order_documents(
        manufacturer.id,
        ordered_from=ordered_from,
        ordered_to=ordered_to,
        product_type=product_type,
        order_item_ids=item_ids,
    )

    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([content]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@router.get("/chat", response_model=ChatMessageListResponse)
async def get_chat_messages(
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> ChatMessageListResponse:
    """メーカー向けチャットメッセージ一覧取得

    ログイン中のメーカーのチャットメッセージを取得します。
    """
    return await service.get_messages(
        manufacturer_id=str(manufacturer.id),
        page=page,
        limit=limit,
    )


@router.post("/chat", response_model=ChatMessageResponse)
async def send_chat_message(
    content: Annotated[str, Form()],
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatMessageResponse:
    """メーカー向けチャットメッセージ送信

    ログイン中のメーカーとしてメッセージを送信します。
    """
    return await service.send_message(
        manufacturer_id=str(manufacturer.id),
        data=ChatMessageCreate(content=content),
        sender_type=MessageSender.MANUFACTURER,
        sender_name=manufacturer.name,
        attachments=None,
    )
