"""Manufacturer model."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product


class SharingMethod(str, Enum):
    """Sharing method for order documents."""

    DRIVE = "drive"  # TOSYO DRIVE
    PORTAL = "portal"  # メーカー専用ページ


class Manufacturer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Manufacturer model."""

    __tablename__ = "manufacturers"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    supported_products: Mapped[list[str]] = mapped_column(ARRAY(String))
    unit_prices: Mapped[dict] = mapped_column(JSONB, default=dict)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    daily_order_limit: Mapped[int] = mapped_column(Integer)
    sharing_method: Mapped[str] = mapped_column(String(20), default=SharingMethod.PORTAL.value)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    products: Mapped[list["Product"]] = relationship(back_populates="manufacturer")

    def __repr__(self) -> str:
        return f"<Manufacturer(id={self.id}, name={self.name})>"
