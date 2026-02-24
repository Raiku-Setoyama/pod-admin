"""Order status history model."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrderStatusHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Order status history model - ステータス変更履歴."""

    __tablename__ = "order_status_history"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<OrderStatusHistory(id={self.id}, order_id={self.order_id}, "
            f"from={self.from_status}, to={self.to_status})>"
        )
