"""Manufacturer notification settings model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ManufacturerNotificationSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """メーカー別の通知設定モデル.

    日次発注ダイジェストメールの宛先（To/CC・各複数可）と有効/無効、および
    最後に送信した時刻 last_notified_at を保持する。
    メーカー 1 件につき 1 行（manufacturer_id は unique）。
    """

    __tablename__ = "manufacturer_notification_settings"

    manufacturer_id: Mapped[str] = mapped_column(
        ForeignKey("manufacturers.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    # メーカー別 ON/OFF
    daily_digest_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    # To（複数可）。空の場合は送信時に manufacturer.email をデフォルトにする
    to_emails: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default=text("'{}'"), nullable=False
    )
    # CC（複数可）
    cc_emails: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default=text("'{}'"), nullable=False
    )
    # 最後に送信した時刻。送信成功時のみ実行時刻へ更新する。
    # どの明細を載せるかの判定には使わない（OrderItem.manufacturer_notified_at で判定する）
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            "<ManufacturerNotificationSettings("
            f"manufacturer_id={self.manufacturer_id}, enabled={self.daily_digest_enabled})>"
        )
