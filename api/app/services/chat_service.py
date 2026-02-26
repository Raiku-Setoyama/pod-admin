"""Chat service."""

from fastapi import UploadFile

from app.models.chat_message import MessageSender
from app.repositories.chat_repository import ChatRepository
from app.repositories.manufacturer_repository import ManufacturerRepository
from app.schemas.chat import (
    ChatAttachmentResponse,
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
)
from app.utils.exceptions import ManufacturerNotFoundError, ValidationError
from app.utils.file_storage import FileStorage

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

ALLOWED_CONTENT_TYPES = {
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    # PDF
    "application/pdf",
    # Word
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Excel
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Text
    "text/plain",
    "text/csv",
    # ZIP
    "application/zip",
    "application/x-zip-compressed",
}


class ChatService:
    """Service for chat operations."""

    def __init__(
        self,
        chat_repo: ChatRepository,
        manufacturer_repo: ManufacturerRepository,
        file_storage: FileStorage,
    ):
        self._chat_repo = chat_repo
        self._manufacturer_repo = manufacturer_repo
        self._file_storage = file_storage

    async def get_messages(
        self,
        manufacturer_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> ChatMessageListResponse:
        """Get messages for a manufacturer."""
        # Verify manufacturer exists
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(manufacturer_id)

        messages, total = await self._chat_repo.find_by_manufacturer(
            manufacturer_id=manufacturer_id,
            page=page,
            limit=limit,
        )

        return ChatMessageListResponse(
            items=[self._to_response(m) for m in messages],
            total=total,
            page=page,
            limit=limit,
        )

    async def send_message(
        self,
        manufacturer_id: str,
        data: ChatMessageCreate,
        sender_type: MessageSender,
        sender_name: str,
        attachments: list[UploadFile] | None = None,
    ) -> ChatMessageResponse:
        """Send a message."""
        # Verify manufacturer exists
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(manufacturer_id)

        # Create message
        message = await self._chat_repo.create(
            manufacturer_id=manufacturer_id,
            sender_type=sender_type,
            sender_name=sender_name,
            content=data.content,
        )

        # Handle attachments
        if attachments:
            for file in attachments:
                # Validate content type
                content_type = file.content_type or "application/octet-stream"
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise ValidationError(
                        f"ファイル形式 '{content_type}' は許可されていません"
                    )

                content = await file.read()
                file_size = len(content)

                # Validate file size
                if file_size > MAX_FILE_SIZE:
                    raise ValidationError(
                        f"ファイルサイズが上限(10MB)を超えています: {file.filename}"
                    )

                await file.seek(0)

                file_path = await self._file_storage.save(
                    file, f"chat/{manufacturer_id}/"
                )

                await self._chat_repo.add_attachment(
                    message_id=message.id,
                    filename=file.filename or "attachment",
                    file_path=file_path,
                    file_size=file_size,
                    content_type=content_type,
                )

        # Reload message with attachments
        message = await self._chat_repo.find_by_id(message.id)
        return self._to_response(message)  # type: ignore

    def _to_response(self, message) -> ChatMessageResponse:
        """Convert message model to response schema."""
        return ChatMessageResponse(
            id=message.id,
            sender_type=MessageSender(message.sender_type),
            sender_name=message.sender_name,
            content=message.content,
            attachments=[
                ChatAttachmentResponse(
                    id=att.id,
                    filename=att.filename,
                    file_size=att.file_size,
                    content_type=att.content_type,
                    download_url=f"/chat/attachments/{att.id}",
                )
                for att in message.attachments
            ],
            created_at=message.created_at,
        )
