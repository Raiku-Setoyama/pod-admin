"""Manufacturer notification settings repository."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturer import Manufacturer
from app.models.manufacturer_notification_settings import ManufacturerNotificationSettings


class ManufacturerNotificationSettingsRepository:
    """Repository for ManufacturerNotificationSettings model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_manufacturer_id(
        self, manufacturer_id: str
    ) -> ManufacturerNotificationSettings | None:
        """メーカーIDで通知設定を取得する."""
        result = await self._db.execute(
            select(ManufacturerNotificationSettings).where(
                ManufacturerNotificationSettings.manufacturer_id == manufacturer_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        manufacturer_id: str,
        *,
        daily_digest_enabled: bool,
        to_emails: list[str],
        cc_emails: list[str],
    ) -> ManufacturerNotificationSettings:
        """通知設定を作成または更新する（last_notified_at は変更しない）."""
        settings = await self.find_by_manufacturer_id(manufacturer_id)
        if settings is None:
            settings = ManufacturerNotificationSettings(manufacturer_id=manufacturer_id)
            self._db.add(settings)
        settings.daily_digest_enabled = daily_digest_enabled
        settings.to_emails = to_emails
        settings.cc_emails = cc_emails
        await self._db.flush()
        await self._db.refresh(settings)
        return settings

    async def list_enabled_with_manufacturer(
        self,
    ) -> list[tuple[ManufacturerNotificationSettings, Manufacturer]]:
        """通知 ON かつ有効なメーカーの (設定, メーカー) の一覧を返す."""
        result = await self._db.execute(
            select(ManufacturerNotificationSettings, Manufacturer)
            .join(
                Manufacturer,
                Manufacturer.id == ManufacturerNotificationSettings.manufacturer_id,
            )
            .where(ManufacturerNotificationSettings.daily_digest_enabled.is_(True))
            .where(Manufacturer.is_active.is_(True))
            .order_by(Manufacturer.name)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def update_last_notified_at(
        self, settings: ManufacturerNotificationSettings, notified_at: datetime
    ) -> None:
        """送信成功時のウォーターマークを更新する."""
        settings.last_notified_at = notified_at
        await self._db.flush()
