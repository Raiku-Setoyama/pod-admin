"""App setting repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting


class AppSettingRepository:
    """Repository for AppSetting model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_key(self, key: str) -> AppSetting | None:
        """設定値をキーで取得する."""
        result = await self._db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        return result.scalar_one_or_none()

    async def find_all(self) -> list[AppSetting]:
        """全設定を取得する."""
        result = await self._db.execute(
            select(AppSetting).order_by(AppSetting.key)
        )
        return list(result.scalars().all())

    async def upsert(self, key: str, value: str, description: str | None = None) -> AppSetting:
        """設定値を作成または更新する."""
        setting = await self.find_by_key(key)
        if setting:
            setting.value = value
            if description is not None:
                setting.description = description
        else:
            setting = AppSetting(key=key, value=value, description=description)
            self._db.add(setting)
        await self._db.flush()
        await self._db.refresh(setting)
        return setting
