"""Chat message models."""

from enum import Enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MessageSender(str, Enum):
    """Message sender type."""

    ADMIN = "admin"
    MANUFACTURER = "manufacturer"


class ChatMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Chat message model."""

    __tablename__ = "chat_messages"

    manufacturer_id: Mapped[str] = mapped_column(ForeignKey("manufacturers.id"), index=True)
    sender_type: Mapped[str] = mapped_column(String(20))
    sender_name: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship()
    attachments: Mapped[list["ChatAttachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, sender={self.sender_type})>"


class ChatAttachment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Chat attachment model."""

    __tablename__ = "chat_attachments"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(100))

    # Relationships
    message: Mapped["ChatMessage"] = relationship(back_populates="attachments")

    def __repr__(self) -> str:
        return f"<ChatAttachment(id={self.id}, filename={self.filename})>"


# Import here to avoid circular imports
from app.models.manufacturer import Manufacturer  # noqa: E402, F401
