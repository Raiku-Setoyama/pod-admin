"""Shipment models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ShipmentStatus(str, Enum):
    """Shipment status."""

    PENDING = "pending"  # 配送準備待ち
    READY = "ready"  # 配送準備完了
    SHIPPED = "shipped"  # 発送完了（最終ステータス）


class Shipment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Shipment model."""

    __tablename__ = "shipments"

    status: Mapped[str] = mapped_column(
        String(20), default=ShipmentStatus.PENDING.value, index=True
    )
    tracking_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    carrier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    packing_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Customer info (copied from order for shipping)
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_postal_code: Mapped[str] = mapped_column(String(10))
    customer_address: Mapped[str] = mapped_column(Text)
    customer_phone: Mapped[str] = mapped_column(String(20))

    # Relationships
    items: Mapped[list["ShipmentItem"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Shipment(id={self.id}, status={self.status})>"


class ShipmentItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Shipment item model."""

    __tablename__ = "shipment_items"

    shipment_id: Mapped[str] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)

    # Relationships
    shipment: Mapped["Shipment"] = relationship(back_populates="items")
    order: Mapped["Order"] = relationship()

    def __repr__(self) -> str:
        return f"<ShipmentItem(id={self.id}, order_id={self.order_id})>"


# Import here to avoid circular imports
from app.models.order import Order  # noqa: E402, F401
