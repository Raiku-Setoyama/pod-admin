"""Chat repository for database operations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat_message import ChatAttachment, ChatMessage, MessageSender


class ChatRepository:
    """Repository for ChatMessage model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, message_id: str) -> ChatMessage | None:
        """Find a message by ID."""
        result = await self._db.execute(
            select(ChatMessage)
            .options(selectinload(ChatMessage.attachments))
            .where(ChatMessage.id == message_id)
        )
        return result.scalar_one_or_none()

    async def find_by_manufacturer(
        self,
        manufacturer_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[ChatMessage], int]:
        """Find messages for a manufacturer with pagination."""
        query = (
            select(ChatMessage)
            .options(selectinload(ChatMessage.attachments))
            .where(ChatMessage.manufacturer_id == manufacturer_id)
        )
        count_query = select(func.count(ChatMessage.id)).where(
            ChatMessage.manufacturer_id == manufacturer_id
        )

        # Get total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination (newest first)
        offset = (page - 1) * limit
        query = query.order_by(ChatMessage.created_at.desc()).offset(offset).limit(limit)

        result = await self._db.execute(query)
        messages = list(result.scalars().all())

        # Reverse to show oldest first in the page
        messages.reverse()

        return messages, total

    async def create(
        self,
        manufacturer_id: str,
        sender_type: MessageSender,
        sender_name: str,
        content: str,
    ) -> ChatMessage:
        """Create a new message."""
        message = ChatMessage(
            manufacturer_id=manufacturer_id,
            sender_type=sender_type.value,
            sender_name=sender_name,
            content=content,
        )
        self._db.add(message)
        await self._db.flush()
        await self._db.refresh(message)
        return message

    async def find_attachment_by_id(self, attachment_id: str) -> ChatAttachment | None:
        """Find an attachment by ID."""
        result = await self._db.execute(
            select(ChatAttachment).where(ChatAttachment.id == attachment_id)
        )
        return result.scalar_one_or_none()

    async def add_attachment(
        self,
        message_id: str,
        filename: str,
        file_path: str,
        file_size: int,
        content_type: str,
    ) -> ChatAttachment:
        """Add an attachment to a message."""
        attachment = ChatAttachment(
            message_id=message_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            content_type=content_type,
        )
        self._db.add(attachment)
        await self._db.flush()
        await self._db.refresh(attachment)
        return attachment
