# 配送予定日表示機能 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 配送一覧に配送予定日カラムを追加し、営業日ベースで自動計算・表示する。設定ページで発送準備日数と独自休日を管理できるようにする。

**Architecture:** バックエンドで営業日計算ユーティリティを作成し、ShipmentServiceで配送予定日を算出してAPIレスポンスに含める。設定（発送準備日数・独自休日）はsystem_settings/company_holidaysテーブルで管理し、設定APIで操作する。フロントエンドは配送一覧テーブルにカラム追加と設定ページ拡張。

**Tech Stack:** Python(FastAPI, SQLAlchemy, jpholiday, Alembic), TypeScript(Next.js, React, SWR), PostgreSQL

---

## File Structure

### 新規ファイル（バックエンド）
- `api/app/models/system_setting.py` - SystemSettingモデル
- `api/app/models/company_holiday.py` - CompanyHolidayモデル
- `api/app/repositories/system_setting_repository.py` - 設定CRUD
- `api/app/repositories/company_holiday_repository.py` - 独自休日CRUD
- `api/app/services/settings_service.py` - 設定管理サービス
- `api/app/schemas/settings.py` - 設定Pydanticスキーマ
- `api/app/routers/settings.py` - 設定APIルーター
- `api/app/utils/business_day_calculator.py` - 営業日計算ユーティリティ
- `api/alembic/versions/xxxx_add_system_settings_and_company_holidays.py` - マイグレーション
- `api/tests/unit/test_business_day_calculator.py` - 営業日計算テスト
- `api/tests/unit/test_settings_service.py` - 設定サービステスト

### 新規ファイル（フロントエンド）
- `web/src/features/settings/components/shipping-settings.tsx` - 発送準備日数設定UI
- `web/src/features/settings/components/company-holidays.tsx` - 独自休日管理UI

### 変更ファイル（バックエンド）
- `api/app/schemas/shipment.py` - ShipmentResponse/PendingOrderResponseにestimated_shipping_date追加
- `api/app/services/shipment_service.py` - 配送予定日計算ロジック追加
- `api/app/repositories/shipment_repository.py` - Product eager loading追加
- `api/app/dependencies.py` - 新リポジトリ/サービスのDI登録
- `api/app/main.py` - 設定ルーター登録
- `api/alembic/env.py` - 新モデルimport追加

### 変更ファイル（フロントエンド）
- `web/src/types/api/index.ts` - 型定義追加
- `web/src/features/shipments/components/shipment-list.tsx` - 配送予定日カラム追加
- `web/src/app/(dashboard)/settings/page.tsx` - 設定ページ拡張

---

## Task 1: 営業日計算ユーティリティ

**Files:**
- Create: `api/app/utils/business_day_calculator.py`
- Create: `api/tests/unit/test_business_day_calculator.py`

- [ ] **Step 1: テストファイルを作成**

```python
# api/tests/unit/test_business_day_calculator.py
"""Tests for business day calculator."""

from datetime import date

import pytest

from app.utils.business_day_calculator import add_business_days, is_business_day


class TestIsBusinessDay:
    """Test is_business_day function."""

    def test_weekday_is_business_day(self):
        """月曜日は営業日."""
        assert is_business_day(date(2026, 3, 30), set()) is True  # Monday

    def test_saturday_is_not_business_day(self):
        """土曜日は営業日ではない."""
        assert is_business_day(date(2026, 3, 28), set()) is False  # Saturday

    def test_sunday_is_not_business_day(self):
        """日曜日は営業日ではない."""
        assert is_business_day(date(2026, 3, 29), set()) is False  # Sunday

    def test_national_holiday_is_not_business_day(self):
        """祝日は営業日ではない（元日）."""
        assert is_business_day(date(2026, 1, 1), set()) is False  # 元日

    def test_company_holiday_is_not_business_day(self):
        """独自休日は営業日ではない."""
        company_holidays = {date(2026, 8, 13)}
        assert is_business_day(date(2026, 8, 13), company_holidays) is False

    def test_weekday_not_holiday_is_business_day(self):
        """祝日でない平日は営業日."""
        assert is_business_day(date(2026, 4, 1), set()) is True  # Wednesday


class TestAddBusinessDays:
    """Test add_business_days function."""

    def test_add_zero_days(self):
        """0日加算は翌営業日を返す（起算日の翌日から）."""
        # 2026-03-27 (Friday) + 0 business days = next business day = 2026-03-30 (Monday)
        result = add_business_days(date(2026, 3, 27), 0, set())
        assert result == date(2026, 3, 30)

    def test_add_days_within_week(self):
        """平日のみの加算（週内）."""
        # 2026-03-30 (Monday) + 3 business days = Thursday 2026-04-02
        result = add_business_days(date(2026, 3, 30), 3, set())
        assert result == date(2026, 4, 2)

    def test_add_days_across_weekend(self):
        """週末をまたぐ加算."""
        # 2026-03-26 (Thursday) + 5 business days
        # Fri 27, Mon 30, Tue 31, Wed Apr1, Thu Apr2
        result = add_business_days(date(2026, 3, 26), 5, set())
        assert result == date(2026, 4, 2)

    def test_add_days_with_national_holiday(self):
        """祝日を含む加算（昭和の日: 4/29）."""
        # 2026-04-27 (Monday) + 3 business days
        # Tue 28, (Wed 29 = 昭和の日 skip), Thu 30, Fri May 1
        result = add_business_days(date(2026, 4, 27), 3, set())
        assert result == date(2026, 5, 1)

    def test_add_days_with_company_holiday(self):
        """独自休日を含む加算."""
        company_holidays = {date(2026, 3, 31)}
        # 2026-03-30 (Monday) + 2 business days
        # (Tue 31 = company holiday skip), Wed Apr1, Thu Apr2
        result = add_business_days(date(2026, 3, 30), 2, company_holidays)
        assert result == date(2026, 4, 2)

    def test_add_five_business_days_default(self):
        """デフォルト5営業日加算."""
        # 2026-03-30 (Monday) + 5 business days
        # Tue 31, Wed Apr1, Thu Apr2, Fri Apr3, Mon Apr6
        result = add_business_days(date(2026, 3, 30), 5, set())
        assert result == date(2026, 4, 6)

    def test_start_date_is_friday(self):
        """金曜日起算の場合、翌営業日（月曜日）からカウント."""
        # 2026-03-27 (Friday) + 5 business days
        # Mon 30, Tue 31, Wed Apr1, Thu Apr2, Fri Apr3
        result = add_business_days(date(2026, 3, 27), 5, set())
        assert result == date(2026, 4, 3)

    def test_golden_week(self):
        """GW期間の計算."""
        # 2026-04-28 (Tuesday) + 5 business days
        # 4/29 昭和の日(skip), 4/30(Thu), 5/1(Fri), 5/2(Sat skip), 5/3(Sun skip),
        # 5/4 みどりの日(skip), 5/5 こどもの日(skip), 5/6 振替休日(skip),
        # 5/7(Thu), 5/8(Fri), 5/11(Mon)
        result = add_business_days(date(2026, 4, 28), 5, set())
        # 4/30, 5/1, 5/7, 5/8, 5/11
        assert result == date(2026, 5, 11)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /Users/raiku_setoyama/github/tosyo/pod-admin/api && python -m pytest tests/unit/test_business_day_calculator.py -v`
Expected: FAIL with import error

- [ ] **Step 3: 営業日計算ユーティリティを実装**

```python
# api/app/utils/business_day_calculator.py
"""Business day calculator utility.

営業日計算ユーティリティ。
土日、日本の祝日、TOSYO独自休日を除外して営業日を加算する。
"""

from datetime import date, timedelta

import jpholiday


def is_business_day(target_date: date, company_holidays: set[date]) -> bool:
    """指定日が営業日かどうかを判定する.

    Args:
        target_date: 判定対象の日付
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        営業日であればTrue
    """
    # 土日チェック
    if target_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False

    # 日本の祝日チェック
    if jpholiday.is_holiday(target_date):
        return False

    # 独自休日チェック
    if target_date in company_holidays:
        return False

    return True


def add_business_days(start_date: date, days: int, company_holidays: set[date]) -> date:
    """起算日の翌日から営業日を加算した日付を返す.

    Args:
        start_date: 起算日（この日はカウントに含まない）
        days: 加算する営業日数
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        加算後の日付
    """
    current = start_date
    remaining = days

    while True:
        current += timedelta(days=1)
        if is_business_day(current, company_holidays):
            if remaining <= 0:
                return current
            remaining -= 1
```

- [ ] **Step 4: jpholidayパッケージをインストール**

Run: `cd /Users/raiku_setoyama/github/tosyo/pod-admin/api && pip install jpholiday`
Also add to requirements if exists.

- [ ] **Step 5: テストが通ることを確認**

Run: `cd /Users/raiku_setoyama/github/tosyo/pod-admin/api && python -m pytest tests/unit/test_business_day_calculator.py -v`
Expected: All tests PASS

- [ ] **Step 6: コミット**

```bash
git add api/app/utils/business_day_calculator.py api/tests/unit/test_business_day_calculator.py
git commit -m "feat: add business day calculator utility with jpholiday support"
```

---

## Task 2: SystemSettingモデルとCompanyHolidayモデル

**Files:**
- Create: `api/app/models/system_setting.py`
- Create: `api/app/models/company_holiday.py`
- Modify: `api/alembic/env.py`

- [ ] **Step 1: SystemSettingモデルを作成**

```python
# api/app/models/system_setting.py
"""System setting model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SystemSetting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """System setting model - key/value store for application settings."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<SystemSetting(key={self.key}, value={self.value})>"
```

- [ ] **Step 2: CompanyHolidayモデルを作成**

```python
# api/app/models/company_holiday.py
"""Company holiday model."""

from datetime import date as date_type

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CompanyHoliday(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Company holiday model - TOSYO独自休日."""

    __tablename__ = "company_holidays"

    date: Mapped[date_type] = mapped_column(Date, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<CompanyHoliday(date={self.date}, name={self.name})>"
```

- [ ] **Step 3: alembic/env.pyに新モデルのimportを追加**

`api/alembic/env.py` の既存import群の後に追加:
```python
from app.models.system_setting import SystemSetting  # noqa: F401
from app.models.company_holiday import CompanyHoliday  # noqa: F401
```

- [ ] **Step 4: Alembicマイグレーションを生成**

Run: `cd /Users/raiku_setoyama/github/tosyo/pod-admin/api && python -m alembic revision --autogenerate -m "add_system_settings_and_company_holidays"`

Note: DBに接続できない場合は手動でマイグレーションファイルを作成する。

- [ ] **Step 5: マイグレーションファイルに初期データ挿入を追加**

生成されたマイグレーションファイルの `upgrade()` 関数の末尾に追加:
```python
# Insert default shipping preparation days
op.execute(
    "INSERT INTO system_settings (id, key, value, description, created_at, updated_at) "
    "VALUES (gen_random_uuid(), 'shipping_preparation_days', '5', '発送準備日数', now(), now())"
)
```

- [ ] **Step 6: コミット**

```bash
git add api/app/models/system_setting.py api/app/models/company_holiday.py api/alembic/env.py api/alembic/versions/
git commit -m "feat: add SystemSetting and CompanyHoliday models with migration"
```

---

## Task 3: リポジトリ層

**Files:**
- Create: `api/app/repositories/system_setting_repository.py`
- Create: `api/app/repositories/company_holiday_repository.py`

- [ ] **Step 1: SystemSettingRepositoryを作成**

```python
# api/app/repositories/system_setting_repository.py
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
```

- [ ] **Step 2: CompanyHolidayRepositoryを作成**

```python
# api/app/repositories/company_holiday_repository.py
"""Company holiday repository for database operations."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_holiday import CompanyHoliday


class CompanyHolidayRepository:
    """Repository for CompanyHoliday model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_all(self) -> list[CompanyHoliday]:
        """Get all company holidays ordered by date."""
        result = await self._db.execute(
            select(CompanyHoliday).order_by(CompanyHoliday.date.asc())
        )
        return list(result.scalars().all())

    async def find_all_dates(self) -> set[date]:
        """Get all company holiday dates as a set (for business day calculation)."""
        holidays = await self.find_all()
        return {h.date for h in holidays}

    async def find_by_id(self, holiday_id: str) -> CompanyHoliday | None:
        """Find a company holiday by ID."""
        result = await self._db.execute(
            select(CompanyHoliday).where(CompanyHoliday.id == holiday_id)
        )
        return result.scalar_one_or_none()

    async def create(self, holiday_date: date, name: str) -> CompanyHoliday:
        """Create a new company holiday."""
        holiday = CompanyHoliday(date=holiday_date, name=name)
        self._db.add(holiday)
        await self._db.flush()
        await self._db.refresh(holiday)
        return holiday

    async def delete(self, holiday_id: str) -> bool:
        """Delete a company holiday. Returns True if deleted."""
        holiday = await self.find_by_id(holiday_id)
        if not holiday:
            return False
        await self._db.delete(holiday)
        await self._db.flush()
        return True
```

- [ ] **Step 3: コミット**

```bash
git add api/app/repositories/system_setting_repository.py api/app/repositories/company_holiday_repository.py
git commit -m "feat: add SystemSetting and CompanyHoliday repositories"
```

---

## Task 4: 設定スキーマ・サービス・ルーター

**Files:**
- Create: `api/app/schemas/settings.py`
- Create: `api/app/services/settings_service.py`
- Create: `api/app/routers/settings.py`
- Modify: `api/app/dependencies.py`
- Modify: `api/app/main.py`

- [ ] **Step 1: Pydanticスキーマを作成**

```python
# api/app/schemas/settings.py
"""Settings schemas."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ShippingPreparationDaysResponse(BaseModel):
    """Response for shipping preparation days setting."""

    value: int
    description: str | None = None


class ShippingPreparationDaysUpdate(BaseModel):
    """Request to update shipping preparation days."""

    value: int = Field(..., ge=0, le=30, description="発送準備日数（0〜30日）")


class CompanyHolidayResponse(BaseModel):
    """Response for a company holiday."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    date: date
    name: str


class CompanyHolidayCreate(BaseModel):
    """Request to create a company holiday."""

    date: date
    name: str = Field(..., min_length=1, max_length=100)


class CompanyHolidayListResponse(BaseModel):
    """Response for company holiday list."""

    items: list[CompanyHolidayResponse]
```

- [ ] **Step 2: 設定サービスを作成**

```python
# api/app/services/settings_service.py
"""Settings service."""

from datetime import date

from app.models.company_holiday import CompanyHoliday
from app.repositories.company_holiday_repository import CompanyHolidayRepository
from app.repositories.system_setting_repository import SystemSettingRepository
from app.schemas.settings import (
    CompanyHolidayCreate,
    CompanyHolidayListResponse,
    CompanyHolidayResponse,
    ShippingPreparationDaysResponse,
    ShippingPreparationDaysUpdate,
)
from app.utils.exceptions import NotFoundError, ValidationError

SHIPPING_PREPARATION_DAYS_KEY = "shipping_preparation_days"
SHIPPING_PREPARATION_DAYS_DEFAULT = 5


class SettingsService:
    """Service for settings operations."""

    def __init__(
        self,
        system_setting_repo: SystemSettingRepository,
        company_holiday_repo: CompanyHolidayRepository,
    ):
        self._system_setting_repo = system_setting_repo
        self._company_holiday_repo = company_holiday_repo

    async def get_shipping_preparation_days(self) -> ShippingPreparationDaysResponse:
        """Get shipping preparation days setting."""
        setting = await self._system_setting_repo.get_by_key(SHIPPING_PREPARATION_DAYS_KEY)
        if setting:
            return ShippingPreparationDaysResponse(
                value=int(setting.value),
                description=setting.description,
            )
        return ShippingPreparationDaysResponse(
            value=SHIPPING_PREPARATION_DAYS_DEFAULT,
            description="発送準備日数",
        )

    async def update_shipping_preparation_days(
        self, data: ShippingPreparationDaysUpdate
    ) -> ShippingPreparationDaysResponse:
        """Update shipping preparation days setting."""
        setting = await self._system_setting_repo.upsert(
            key=SHIPPING_PREPARATION_DAYS_KEY,
            value=str(data.value),
            description="発送準備日数",
        )
        return ShippingPreparationDaysResponse(
            value=int(setting.value),
            description=setting.description,
        )

    async def get_shipping_preparation_days_value(self) -> int:
        """Get shipping preparation days as integer (for internal use)."""
        setting = await self._system_setting_repo.get_by_key(SHIPPING_PREPARATION_DAYS_KEY)
        if setting:
            return int(setting.value)
        return SHIPPING_PREPARATION_DAYS_DEFAULT

    async def get_company_holidays(self) -> CompanyHolidayListResponse:
        """Get all company holidays."""
        holidays = await self._company_holiday_repo.find_all()
        return CompanyHolidayListResponse(
            items=[
                CompanyHolidayResponse(id=h.id, date=h.date, name=h.name)
                for h in holidays
            ]
        )

    async def get_company_holiday_dates(self) -> set[date]:
        """Get all company holiday dates as set (for business day calculation)."""
        return await self._company_holiday_repo.find_all_dates()

    async def create_company_holiday(
        self, data: CompanyHolidayCreate
    ) -> CompanyHolidayResponse:
        """Create a new company holiday."""
        holiday = await self._company_holiday_repo.create(
            holiday_date=data.date, name=data.name
        )
        return CompanyHolidayResponse(id=holiday.id, date=holiday.date, name=holiday.name)

    async def delete_company_holiday(self, holiday_id: str) -> None:
        """Delete a company holiday."""
        deleted = await self._company_holiday_repo.delete(holiday_id)
        if not deleted:
            raise NotFoundError("CompanyHoliday", holiday_id)
```

- [ ] **Step 3: 設定ルーターを作成**

```python
# api/app/routers/settings.py
"""Settings router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_current_admin, get_settings_service
from app.models.user import User
from app.schemas.settings import (
    CompanyHolidayCreate,
    CompanyHolidayListResponse,
    CompanyHolidayResponse,
    ShippingPreparationDaysResponse,
    ShippingPreparationDaysUpdate,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/shipping-preparation-days", response_model=ShippingPreparationDaysResponse)
async def get_shipping_preparation_days(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ShippingPreparationDaysResponse:
    """発送準備日数を取得."""
    return await service.get_shipping_preparation_days()


@router.put("/shipping-preparation-days", response_model=ShippingPreparationDaysResponse)
async def update_shipping_preparation_days(
    data: ShippingPreparationDaysUpdate,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ShippingPreparationDaysResponse:
    """発送準備日数を更新."""
    return await service.update_shipping_preparation_days(data)


@router.get("/company-holidays", response_model=CompanyHolidayListResponse)
async def get_company_holidays(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> CompanyHolidayListResponse:
    """独自休日一覧を取得."""
    return await service.get_company_holidays()


@router.post("/company-holidays", response_model=CompanyHolidayResponse, status_code=201)
async def create_company_holiday(
    data: CompanyHolidayCreate,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> CompanyHolidayResponse:
    """独自休日を追加."""
    return await service.create_company_holiday(data)


@router.delete("/company-holidays/{holiday_id}", status_code=204)
async def delete_company_holiday(
    holiday_id: str,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> None:
    """独自休日を削除."""
    await service.delete_company_holiday(holiday_id)
```

- [ ] **Step 4: dependencies.pyに新しいDIを追加**

`api/app/dependencies.py` に以下を追加:

imports:
```python
from app.repositories.system_setting_repository import SystemSettingRepository
from app.repositories.company_holiday_repository import CompanyHolidayRepository
from app.services.settings_service import SettingsService
```

repository functions:
```python
def get_system_setting_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SystemSettingRepository:
    """Get system setting repository."""
    return SystemSettingRepository(db)


def get_company_holiday_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompanyHolidayRepository:
    """Get company holiday repository."""
    return CompanyHolidayRepository(db)
```

service function:
```python
def get_settings_service(
    system_setting_repo: Annotated[SystemSettingRepository, Depends(get_system_setting_repository)],
    company_holiday_repo: Annotated[CompanyHolidayRepository, Depends(get_company_holiday_repository)],
) -> SettingsService:
    """Get settings service."""
    return SettingsService(system_setting_repo, company_holiday_repo)
```

- [ ] **Step 5: main.pyに設定ルーターを登録**

`api/app/main.py` のimportsに追加:
```python
from app.routers import (
    ...
    settings,
)
```

router登録に追加:
```python
app.include_router(settings.router, prefix=settings_module.API_V1_PREFIX)
```

Note: `settings` が config の `settings` と名前衝突するため、router importは `from app.routers import settings as settings_router` とし、 `app.include_router(settings_router.router, prefix=settings.API_V1_PREFIX)` とする。

- [ ] **Step 6: コミット**

```bash
git add api/app/schemas/settings.py api/app/services/settings_service.py api/app/routers/settings.py api/app/dependencies.py api/app/main.py
git commit -m "feat: add settings API for shipping preparation days and company holidays"
```

---

## Task 5: ShipmentServiceに配送予定日計算を追加

**Files:**
- Modify: `api/app/repositories/shipment_repository.py` - Product eager loading追加
- Modify: `api/app/schemas/shipment.py` - estimated_shipping_date追加
- Modify: `api/app/services/shipment_service.py` - 配送予定日計算追加
- Modify: `api/app/dependencies.py` - ShipmentServiceにSettingsService DI追加

- [ ] **Step 1: ShipmentRepositoryにProduct eager loadingを追加**

`api/app/repositories/shipment_repository.py` の `find_all` メソッドのqueryに、OrderItemのProductをeager loadするオプションを追加:

```python
query = select(Shipment).options(
    selectinload(Shipment.items)
    .selectinload(ShipmentItem.order)
    .selectinload(Order.items)
    .selectinload(OrderItem.product),  # ← 追加
    selectinload(Shipment.items)
    .selectinload(ShipmentItem.order)
    .selectinload(Order.items),
)
```

同様に `find_by_id` にも追加。

Note: `OrderItem.product` のリレーションと `Product` のimportが必要:
```python
from app.models.product import Product  # noqa: F401
```

- [ ] **Step 2: ShipmentResponseとPendingOrderResponseにestimated_shipping_dateを追加**

`api/app/schemas/shipment.py` に追加:

`ShipmentResponse` クラスに:
```python
estimated_shipping_date: date | None = None
```

`PendingOrderResponse` クラスに:
```python
estimated_shipping_date: date | None = None
```

importに `date` を追加:
```python
from datetime import date, datetime
```

- [ ] **Step 3: ShipmentServiceのコンストラクタにsettings_serviceを追加**

`api/app/services/shipment_service.py` のコンストラクタを変更:

```python
def __init__(
    self,
    shipment_repo: ShipmentRepository,
    order_repo: OrderRepository,
    file_storage: FileStorage,
    order_source_repo: OrderSourceRepository | None = None,
    email_service: "EmailService | None" = None,
    settings_service: "SettingsService | None" = None,
):
    ...
    self._settings_service = settings_service
```

imports追加:
```python
from datetime import date, datetime, timedelta, timezone
from app.utils.business_day_calculator import add_business_days
```

- [ ] **Step 4: 配送予定日計算メソッドを追加**

`api/app/services/shipment_service.py` に以下のメソッドを追加:

```python
def _calculate_estimated_shipping_date(
    self,
    orders: list,
    prep_days: int,
    company_holidays: set[date],
) -> date | None:
    """配送予定日を計算する.

    Args:
        orders: 注文リスト（OrderモデルまたはOrderItem.productを含む）
        prep_days: 発送準備日数
        company_holidays: 独自休日セット

    Returns:
        配送予定日、または計算できない場合はNone
    """
    delivery_dates: list[date] = []
    for order in orders:
        if not order or not order.items:
            continue
        for order_item in order.items:
            product = getattr(order_item, "product", None)
            if product and hasattr(product, "lead_time_days") and product.lead_time_days:
                d = order.ordered_at.date() + timedelta(days=product.lead_time_days)
                delivery_dates.append(d)

    if not delivery_dates:
        return None

    latest_delivery = max(delivery_dates)
    return add_business_days(latest_delivery, prep_days, company_holidays)
```

- [ ] **Step 5: list_with_pending_ordersに配送予定日計算を組み込む**

`list_with_pending_orders` メソッド内で、設定とホリデーを1回取得し、各アイテムに配送予定日を設定:

```python
async def list_with_pending_orders(self, ...):
    # 配送予定日計算用データを1回取得
    prep_days = 5  # default
    company_holidays: set[date] = set()
    if self._settings_service:
        prep_days = await self._settings_service.get_shipping_preparation_days_value()
        company_holidays = await self._settings_service.get_company_holiday_dates()

    # ... existing logic ...

    # Shipment responses に配送予定日を設定
    for shipment in shipments:
        response = self._to_response(shipment)
        orders = [si.order for si in shipment.items if si.order]
        response.estimated_shipping_date = self._calculate_estimated_shipping_date(
            orders, prep_days, company_holidays
        )
        items.append(response)

    # PendingOrder responses に配送予定日を設定
    for order in pending_orders:
        response = self._to_pending_order_response(order)
        response.estimated_shipping_date = self._calculate_estimated_shipping_date(
            [order], prep_days, company_holidays
        )
        items.append(response)
```

- [ ] **Step 6: dependencies.pyのget_shipment_serviceを更新**

```python
def get_shipment_service(
    shipment_repo: Annotated[ShipmentRepository, Depends(get_shipment_repository)],
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    file_storage: Annotated[FileStorage, Depends(lambda: LocalFileStorage(settings.UPLOAD_DIR))],
    order_source_repo: Annotated[OrderSourceRepository, Depends(get_order_source_repository)],
    email_service: Annotated[EmailService | None, Depends(get_email_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> ShipmentService:
    """Get shipment service."""
    return ShipmentService(
        shipment_repo, order_repo, file_storage, order_source_repo, email_service, settings_service
    )
```

- [ ] **Step 7: コミット**

```bash
git add api/app/repositories/shipment_repository.py api/app/schemas/shipment.py api/app/services/shipment_service.py api/app/dependencies.py
git commit -m "feat: calculate estimated shipping date in shipment list API"
```

---

## Task 6: フロントエンド - 型定義と配送一覧テーブル更新

**Files:**
- Modify: `web/src/types/api/index.ts`
- Modify: `web/src/features/shipments/components/shipment-list.tsx`

- [ ] **Step 1: TypeScript型にestimated_shipping_dateを追加**

`web/src/types/api/index.ts` の `Shipment` インターフェースに追加:
```typescript
estimated_shipping_date: string | null;
```

`PendingOrder` インターフェースに追加:
```typescript
estimated_shipping_date: string | null;
```

設定API用の型を追加:
```typescript
// Settings types
export interface ShippingPreparationDays {
  value: number;
  description: string | null;
}

export interface CompanyHoliday {
  id: string;
  date: string;
  name: string;
}

export interface CompanyHolidayListResponse {
  items: CompanyHoliday[];
}
```

- [ ] **Step 2: shipment-list.tsxに配送予定日カラムを追加**

`web/src/features/shipments/components/shipment-list.tsx` に以下の変更:

ヘルパー関数を追加:
```typescript
function getEstimatedShippingDate(item: ShipmentOrPendingOrder): string {
  const dateStr = "estimated_shipping_date" in item ? item.estimated_shipping_date : null;
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}
```

TableHeaderに「配送予定日」を追加（「作成日」と「ステータス」の間）:
```tsx
<TableHead>配送予定日</TableHead>
```

TableBodyの各行に対応するセルを追加:
```tsx
<TableCell>{getEstimatedShippingDate(item)}</TableCell>
```

colSpanを7→8に変更（空行のセル数）。

- [ ] **Step 3: コミット**

```bash
git add web/src/types/api/index.ts web/src/features/shipments/components/shipment-list.tsx
git commit -m "feat: display estimated shipping date column in shipment list"
```

---

## Task 7: フロントエンド - 設定ページ拡張

**Files:**
- Create: `web/src/features/settings/components/shipping-settings.tsx`
- Create: `web/src/features/settings/components/company-holidays.tsx`
- Modify: `web/src/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: 発送準備日数設定コンポーネントを作成**

```tsx
// web/src/features/settings/components/shipping-settings.tsx
"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import type { ShippingPreparationDays } from "@/types/api";

export function ShippingSettings() {
  const [days, setDays] = useState<number>(5);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSettings() {
      try {
        const data = await apiClient<ShippingPreparationDays>(
          "/settings/shipping-preparation-days"
        );
        setDays(data.value);
      } catch {
        // Use default
      } finally {
        setLoading(false);
      }
    }
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await apiClient<ShippingPreparationDays>(
        "/settings/shipping-preparation-days",
        { method: "PUT", body: { value: days } }
      );
      setMessage("保存しました");
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage("保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>配送設定</CardTitle>
        <CardDescription>発送準備に必要な営業日数を設定します</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-4">
          <div className="space-y-2">
            <Label htmlFor="prep-days">発送準備日数</Label>
            <div className="flex items-center gap-2">
              <Input
                id="prep-days"
                type="number"
                min={0}
                max={30}
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-24"
              />
              <span className="text-sm text-muted-foreground">営業日</span>
            </div>
          </div>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </Button>
        </div>
        {message && (
          <p className="text-sm text-muted-foreground">{message}</p>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: 独自休日管理コンポーネントを作成**

```tsx
// web/src/features/settings/components/company-holidays.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiClient } from "@/lib/api/client";
import type { CompanyHoliday, CompanyHolidayListResponse } from "@/types/api";

export function CompanyHolidays() {
  const [holidays, setHolidays] = useState<CompanyHoliday[]>([]);
  const [loading, setLoading] = useState(true);
  const [newDate, setNewDate] = useState("");
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);

  const fetchHolidays = useCallback(async () => {
    try {
      const data = await apiClient<CompanyHolidayListResponse>(
        "/settings/company-holidays"
      );
      setHolidays(data.items);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHolidays();
  }, [fetchHolidays]);

  const handleAdd = async () => {
    if (!newDate || !newName) return;
    setAdding(true);
    try {
      await apiClient<CompanyHoliday>("/settings/company-holidays", {
        method: "POST",
        body: { date: newDate, name: newName },
      });
      setNewDate("");
      setNewName("");
      await fetchHolidays();
    } catch {
      // ignore
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiClient<void>(`/settings/company-holidays/${id}`, {
        method: "DELETE",
      });
      await fetchHolidays();
    } catch {
      // ignore
    }
  };

  if (loading) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>会社休日</CardTitle>
        <CardDescription>
          TOSYO独自の休日を登録します。配送予定日の計算から除外されます。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-4">
          <div className="space-y-2">
            <Label htmlFor="holiday-date">日付</Label>
            <Input
              id="holiday-date"
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              className="w-44"
            />
          </div>
          <div className="space-y-2 flex-1">
            <Label htmlFor="holiday-name">休日名</Label>
            <Input
              id="holiday-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="例: 夏季休暇"
            />
          </div>
          <Button onClick={handleAdd} disabled={adding || !newDate || !newName}>
            {adding ? "追加中..." : "追加"}
          </Button>
        </div>

        {holidays.length > 0 && (
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>日付</TableHead>
                  <TableHead>休日名</TableHead>
                  <TableHead className="w-[80px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {holidays.map((holiday) => (
                  <TableRow key={holiday.id}>
                    <TableCell>{holiday.date}</TableCell>
                    <TableCell>{holiday.name}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(holiday.id)}
                        className="text-destructive hover:text-destructive"
                      >
                        削除
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {holidays.length === 0 && (
          <p className="text-sm text-muted-foreground">登録された休日はありません</p>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: 設定ページを拡張**

`web/src/app/(dashboard)/settings/page.tsx` を更新:

```tsx
"use client";

import { PageContainer } from "@/components/layout/page-container";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ShippingSettings } from "@/features/settings/components/shipping-settings";
import { CompanyHolidays } from "@/features/settings/components/company-holidays";

export default function SettingsPage() {
  return (
    <PageContainer title="設定" description="システム設定">
      <div className="max-w-2xl space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>アカウント情報</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">メールアドレス</Label>
              <Input id="email" defaultValue="admin@example.com" disabled />
            </div>
          </CardContent>
        </Card>

        <ShippingSettings />
        <CompanyHolidays />
      </div>
    </PageContainer>
  );
}
```

- [ ] **Step 4: コミット**

```bash
git add web/src/features/settings/components/shipping-settings.tsx web/src/features/settings/components/company-holidays.tsx web/src/app/\(dashboard\)/settings/page.tsx
git commit -m "feat: add shipping preparation days and company holidays to settings page"
```

---

## Task 8: jpholidayをrequirementsに追加

**Files:**
- Modify: `api/requirements.txt` or `api/pyproject.toml` (whichever exists)

- [ ] **Step 1: requirements/依存関係ファイルを確認し、jpholidayを追加**

Run: `ls api/requirements*.txt api/pyproject.toml 2>/dev/null` to find the dependency file.
Add `jpholiday` to the appropriate file.

- [ ] **Step 2: コミット**

```bash
git add api/requirements*.txt api/pyproject.toml  # whichever was modified
git commit -m "chore: add jpholiday dependency for Japanese holiday calculation"
```
