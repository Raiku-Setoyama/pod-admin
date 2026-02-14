"""OrderSource model - 受注元管理."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SenderAddressMixin, TimestampMixin, UUIDPrimaryKeyMixin


class OrderSource(Base, UUIDPrimaryKeyMixin, SenderAddressMixin, TimestampMixin):
    """OrderSource model - 受注元（外部販売サイト）の管理.

    SenderAddressMixin provides: name, phone, postal_code,
    address_prefecture, address_city, address_building, full_address property
    """

    __tablename__ = "order_sources"

    # 受注元コード（例: "RKSYO"）
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    # 外部APIキー
    api_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    # 有効/無効フラグ
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    def __repr__(self) -> str:
        return f"<OrderSource(id={self.id}, code={self.code}, name={self.name})>"
