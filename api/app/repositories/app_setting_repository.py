"""App setting repository."""

from sqlalchemy import select, update
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

    async def claim_daily_run(self, key: str, date_str: str) -> bool:
        """本日分の実行権を原子的に取得する（日次ガード）.

        value を条件付きで date_str に更新する。既に value == date_str
        （＝本日実行済み）の場合は何も更新せず False を返す。取得できたら True。

        条件付き UPDATE の rowcount を使うことで、外部トリガの多重発火が
        同時に到達しても本処理を実行するのは 1 回だけに保証する。
        """
        # 行が存在しない場合のみ空値で作成（通常はマイグレーションで seed 済み）
        existing = await self.find_by_key(key)
        if existing is None:
            self._db.add(AppSetting(key=key, value=""))
            await self._db.flush()

        result = await self._db.execute(
            update(AppSetting)
            .where(AppSetting.key == key, AppSetting.value != date_str)
            .values(value=date_str)
            .returning(AppSetting.key)
        )
        return result.first() is not None
