"""Manufacturer portal router."""

from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_chat_repository,
    get_chat_service,
    get_current_manufacturer,
    get_file_storage,
    get_invoice_service,
    get_manufacturer_order_service,
    get_manufacturer_portal_service,
)
from app.repositories.chat_repository import ChatRepository
from app.utils.exceptions import NotFoundError
from app.utils.file_storage import FileStorage
from app.models.chat_message import MessageSender
from app.models.manufacturer import Manufacturer
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
)
from app.schemas.invoice import InvoiceItemRequest
from app.schemas.manufacturer import ManufacturerOrderItemListResponse
from app.schemas.manufacturer_portal import (
    ManufacturerLoginRequest,
    ManufacturerLoginResponse,
    ManufacturerProfileResponse,
    ManufacturerProfileUpdate,
)
from app.services.chat_service import ChatService
from app.services.invoice_service import InvoiceService
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


# === プロフィールエンドポイント ===


@router.get("/profile", response_model=ManufacturerProfileResponse)
async def get_profile(
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
) -> ManufacturerProfileResponse:
    """プロフィール取得

    ログイン中のメーカーのプロフィール情報を取得します。
    """
    return ManufacturerProfileResponse.model_validate(manufacturer)


@router.patch("/profile", response_model=ManufacturerProfileResponse)
async def update_profile(
    data: ManufacturerProfileUpdate,
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    service: Annotated[ManufacturerPortalService, Depends(get_manufacturer_portal_service)],
) -> ManufacturerProfileResponse:
    """プロフィール更新

    ログイン中のメーカーのプロフィール情報を更新します。
    """
    updated = await service.update_profile(manufacturer.id, data)
    return ManufacturerProfileResponse.model_validate(updated)


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
    status: str | None = None,
) -> ManufacturerOrderItemListResponse:
    """発注アイテム一覧を取得

    ログイン中のメーカーに紐づく受注明細一覧を返します。
    statusでフィルタ可能（ordered, manufacturing, delivered）。
    """
    return await service.get_order_items_by_manufacturer(
        manufacturer.id,
        ordered_from=ordered_from,
        ordered_to=ordered_to,
        product_type=product_type,
        status=status,
    )


@router.get("/order-documents")
async def download_order_documents(
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    service: Annotated[ManufacturerOrderService, Depends(get_manufacturer_order_service)],
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    product_type: str | None = None,
    order_item_ids: str | None = None,
    status: str | None = None,
) -> StreamingResponse:
    """発注資料ZIPをダウンロード

    ログイン中のメーカーに紐づく受注明細を含む
    発注資料ZIPファイルを生成してダウンロードします。
    発注中（ORDERED）ステータスの明細は製造中（MANUFACTURING）に自動更新されます。

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
        status=status,
        update_status=True,  # メーカーからのダウンロードでは発注中→製造中に更新
    )

    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([content]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


# === 請求書エンドポイント ===


@router.post("/invoices")
async def generate_invoice(
    data: InvoiceItemRequest,
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> StreamingResponse:
    """請求書PDFを発行（選択発行）

    指定された受注明細に対する請求書PDFを生成してダウンロードします。

    Args:
        data: 請求書発行リクエスト
            - order_item_ids: 請求対象のOrderItem IDリスト

    Returns:
        請求書PDFファイル
    """
    pdf_bytes, filename, item_count, total_amount = await service.generate_invoice_by_items(
        manufacturer.id, data.order_item_ids
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
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    content: Annotated[str | None, Form()] = None,
    attachments: list[UploadFile] | None = File(None),
) -> ChatMessageResponse:
    """メーカー向けチャットメッセージ送信

    ログイン中のメーカーとしてメッセージを送信します。
    ファイル添付も可能です。
    """
    has_content = content and content.strip()
    has_attachments = attachments and any(a.filename for a in attachments)

    if not has_content and not has_attachments:
        raise HTTPException(
            status_code=400,
            detail="メッセージ本文またはファイルのいずれかが必要です",
        )

    return await service.send_message(
        manufacturer_id=str(manufacturer.id),
        data=ChatMessageCreate(content=content or ""),
        sender_type=MessageSender.MANUFACTURER,
        sender_name=manufacturer.name,
        attachments=attachments,
    )


@router.get("/chat/attachments/{attachment_id}")
async def download_chat_attachment(
    attachment_id: str,
    manufacturer: Annotated[Manufacturer, Depends(get_current_manufacturer)],
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repository)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> StreamingResponse:
    """メーカー向けチャット添付ファイルダウンロード"""
    attachment = await chat_repo.find_attachment_by_id(attachment_id)
    if not attachment:
        raise NotFoundError("Attachment", attachment_id)

    file_content = await file_storage.get(attachment.file_path)
    if file_content is None:
        raise NotFoundError("Attachment file", attachment_id)

    encoded_filename = quote(attachment.filename)

    return StreamingResponse(
        iter([file_content]),
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )
