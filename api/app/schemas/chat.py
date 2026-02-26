"""Chat schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat_message import MessageSender


class ChatAttachmentResponse(BaseModel):
    """Chat attachment response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_size: int
    content_type: str
    download_url: str | None = None


class ChatMessageCreate(BaseModel):
    """Chat message creation schema."""

    content: str = Field("", min_length=0, max_length=5000)


class ChatMessageResponse(BaseModel):
    """Chat message response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    sender_type: MessageSender
    sender_name: str
    content: str
    attachments: list[ChatAttachmentResponse]
    created_at: datetime


class ChatMessageListResponse(BaseModel):
    """Chat message list response schema."""

    items: list[ChatMessageResponse]
    total: int
    page: int
    limit: int
