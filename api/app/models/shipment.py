"""Shipment models."""

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.order import Order


class ShipmentStatus(str, Enum):
    """Shipment status."""

    PENDING = "pending"  # 配送準備待ち
    READY = "ready"  # 配送準備完了
    SHIPPED = "shipped"  # 発送完了（最終ステータス）


class Shipment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Shipment model.

    顧客情報は items[0].order から取得します。
    """

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
    estimated_shipping_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    shipping_email_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # Relationships
    items: Mapped[list["ShipmentItem"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan"
    )

    @property
    def first_order(self) -> "Order | None":
        """最初の注文を取得（顧客情報の取得元）."""
        if self.items:
            return self.items[0].order
        return None

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
