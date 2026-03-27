"""System setting repository for database operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting


class SystemSettingRepository:
    """Repository for SystemSetting model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_key(self, key: str) -> SystemSetting | None:
        """Get a setting by key."""
        result = await self._db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        return result.scalar_one_or_none()

    async def upsert(self, key: str, value: str, description: str | None = None) -> SystemSetting:
        """Create or update a setting."""
        setting = await self.get_by_key(key)
        if setting:
            setting.value = value
            if description is not None:
                setting.description = description
        else:
            setting = SystemSetting(key=key, value=value, description=description)
            self._db.add(setting)
        await self._db.flush()
        await self._db.refresh(setting)
        return setting
