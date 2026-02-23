"""Chat router."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_chat_repository,
    get_chat_service,
    get_current_admin,
    get_file_storage,
)
from app.models.chat_message import MessageSender
from app.models.user import User
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
)
from app.services.chat_service import ChatService
from app.utils.exceptions import NotFoundError
from app.utils.file_storage import FileStorage

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/manufacturers/{manufacturer_id}", response_model=ChatMessageListResponse)
async def get_chat_messages(
    manufacturer_id: str,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> ChatMessageListResponse:
    """Get chat messages for a manufacturer."""
    return await service.get_messages(
        manufacturer_id=manufacturer_id,
        page=page,
        limit=limit,
    )


@router.post("/manufacturers/{manufacturer_id}", response_model=ChatMessageResponse)
async def send_chat_message(
    manufacturer_id: str,
    content: Annotated[str, Form()],
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    attachments: list[UploadFile] | None = File(None),
) -> ChatMessageResponse:
    """Send a chat message to a manufacturer."""
    return await service.send_message(
        manufacturer_id=manufacturer_id,
        data=ChatMessageCreate(content=content),
        sender_type=MessageSender.ADMIN,
        sender_name=current_user.name,
        attachments=attachments,
    )


@router.get("/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: str,
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repository)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> StreamingResponse:
    """Download a chat attachment."""
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
