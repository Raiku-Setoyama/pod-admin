"""SQLAlchemy base model and common mixins."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Mixin that adds a UUID primary key."""

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )


class CustomerAddressMixin:
    """配送先（顧客）住所のMixin.

    Order モデルで使用。住所は分割フィールドのみで管理し、
    結合が必要な場合は full_address プロパティを使用。
    """

    customer_name: Mapped[str] = mapped_column(String(100))
    customer_postal_code: Mapped[str] = mapped_column(String(10))
    customer_address_prefecture: Mapped[str] = mapped_column(String(50))
    customer_address_city: Mapped[str] = mapped_column(Text)
    customer_address_building: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(20))

    @property
    def customer_full_address(self) -> str:
        """結合された完全な住所を返す."""
        parts = [
            self.customer_address_prefecture,
            self.customer_address_city,
            self.customer_address_building,
        ]
        return "".join(p for p in parts if p)


class SenderAddressMixin:
    """配送元（送り主）住所のMixin.

    OrderSource モデルで使用。
    """

    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    postal_code: Mapped[str] = mapped_column(String(10))
    address_prefecture: Mapped[str] = mapped_column(String(50))
    address_city: Mapped[str] = mapped_column(Text)
    address_building: Mapped[str | None] = mapped_column(String(200), nullable=True)

    @property
    def full_address(self) -> str:
        """結合された完全な住所を返す."""
        parts = [self.address_prefecture, self.address_city, self.address_building]
        return "".join(p for p in parts if p)
