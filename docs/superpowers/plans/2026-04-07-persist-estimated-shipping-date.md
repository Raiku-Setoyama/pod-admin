# 納品予定日のDB永続化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shipment作成時に `estimated_shipping_date` を計算してDBに永続化する。未発注（pending order）は「-」表示にする。

**Architecture:** `shipments` テーブルに `estimated_shipping_date` カラム（DATE, nullable）を追加。Shipment自動作成時（OrderService, ManufacturerOrderService）に計算してセット。`list_with_pending_orders()` のShipment側はDB値をそのまま返し、pending order側は `estimated_shipping_date = None` を返す（フロントは既に null → "-" 表示済み）。

**Tech Stack:** Alembic, SQLAlchemy, FastAPI, pytest

---

### Task 1: Alembicマイグレーション — `estimated_shipping_date` カラム追加

**Files:**
- Create: `api/alembic/versions/add_estimated_shipping_date.py`

- [ ] **Step 1: マイグレーションファイルを作成**

```python
"""Add estimated_shipping_date column to shipments table.

Revision ID: add_est_ship_date_001
Revises: add_sys_settings_001
Create Date: 2026-04-07

Shipment作成時に計算した納品予定日を永続化する。
"""

from alembic import op
import sqlalchemy as sa


revision = "add_est_ship_date_001"
down_revision = "add_sys_settings_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column("estimated_shipping_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shipments", "estimated_shipping_date")
```

- [ ] **Step 2: マイグレーション実行確認**

Run: `cd api && uv run alembic upgrade head`
Expected: SUCCESS, カラムが追加される

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/add_estimated_shipping_date.py
git commit -m "feat: add estimated_shipping_date column to shipments table"
```

---

### Task 2: Shipmentモデルにカラム追加

**Files:**
- Modify: `api/app/models/shipment.py:1-10` (import追加), `api/app/models/shipment.py:39-40` (カラム追加)

- [ ] **Step 1: importに `Date` を追加**

`api/app/models/shipment.py` の import行を修正:

```python
# Before:
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text

# After:
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
```

- [ ] **Step 2: `estimated_shipping_date` カラムをモデルに追加**

`api/app/models/shipment.py` の `note` カラムの後に追加:

```python
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_shipping_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    shipping_email_sent: Mapped[bool] = mapped_column(
```

`datetime` importに `date` を追加:

```python
# Before:
from datetime import datetime

# After:
from datetime import date, datetime
```

- [ ] **Step 3: Commit**

```bash
git add api/app/models/shipment.py
git commit -m "feat: add estimated_shipping_date field to Shipment model"
```

---

### Task 3: ShipmentRepository.create に `estimated_shipping_date` パラメータ追加

**Files:**
- Modify: `api/app/repositories/shipment_repository.py:153-173`
- Test: `api/tests/unit/test_shipment_repo_estimated_date.py`

- [ ] **Step 1: テストを書く**

```python
"""Test ShipmentRepository.create with estimated_shipping_date."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.shipment_repository import ShipmentRepository


@pytest.mark.asyncio
async def test_create_sets_estimated_shipping_date():
    """Shipment作成時にestimated_shipping_dateがセットされる."""
    db = AsyncMock()
    repo = ShipmentRepository(db)

    mock_shipment = MagicMock()
    mock_shipment.id = "ship-1"

    # Patch find_by_id to return a mock
    with patch.object(repo, "find_by_id", return_value=mock_shipment):
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        # capture what Shipment() gets created with
        created_shipments = []
        original_add = db.add

        def capture_add(obj):
            from app.models.shipment import Shipment
            if isinstance(obj, Shipment):
                created_shipments.append(obj)

        db.add.side_effect = capture_add

        await repo.create(
            order_ids=["order-1"],
            estimated_shipping_date=date(2026, 4, 15),
        )

        assert len(created_shipments) == 1
        assert created_shipments[0].estimated_shipping_date == date(2026, 4, 15)


@pytest.mark.asyncio
async def test_create_without_estimated_shipping_date():
    """estimated_shipping_dateがNoneの場合もShipmentが作成される."""
    db = AsyncMock()
    repo = ShipmentRepository(db)

    mock_shipment = MagicMock()
    mock_shipment.id = "ship-1"

    with patch.object(repo, "find_by_id", return_value=mock_shipment):
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        created_shipments = []

        def capture_add(obj):
            from app.models.shipment import Shipment
            if isinstance(obj, Shipment):
                created_shipments.append(obj)

        db.add.side_effect = capture_add

        await repo.create(order_ids=["order-1"])

        assert len(created_shipments) == 1
        assert created_shipments[0].estimated_shipping_date is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd api && uv run pytest tests/unit/test_shipment_repo_estimated_date.py -v`
Expected: FAIL — `create()` が `estimated_shipping_date` パラメータを受け取らない

- [ ] **Step 3: Repository.create を修正**

`api/app/repositories/shipment_repository.py` の `create` メソッドを修正:

```python
    async def create(
        self,
        order_ids: list[str],
        estimated_shipping_date: date | None = None,
    ) -> Shipment:
        """Create a new shipment.

        顧客情報は order_ids の最初の注文から参照します。
        """
        shipment = Shipment(estimated_shipping_date=estimated_shipping_date)
        self._db.add(shipment)
        await self._db.flush()

        # Create items
        for order_id in order_ids:
            item = ShipmentItem(
                shipment_id=shipment.id,
                order_id=order_id,
            )
            self._db.add(item)

        await self._db.flush()
        await self._db.refresh(shipment)

        return await self.find_by_id(shipment.id)  # type: ignore
```

`date` の import を追加（ファイル先頭）:

```python
# Before:
from datetime import date

# After (変更なし — 既にimportされている):
from datetime import date
```

- [ ] **Step 4: テストがパスすることを確認**

Run: `cd api && uv run pytest tests/unit/test_shipment_repo_estimated_date.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/repositories/shipment_repository.py api/tests/unit/test_shipment_repo_estimated_date.py
git commit -m "feat: accept estimated_shipping_date in ShipmentRepository.create"
```

---

### Task 4: Shipment作成時に納品予定日を計算して保存 — OrderService

**Files:**
- Modify: `api/app/services/order_service.py:250-270`
- Test: `api/tests/unit/test_order_service_status.py` (既存テストに追加)

- [ ] **Step 1: テストを書く**

`api/tests/unit/test_order_estimated_shipping_date.py` を新規作成:

```python
"""Test estimated_shipping_date is persisted when OrderService creates a shipment."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.order import Order, OrderItem, OrderStatus
from app.services.order_service import OrderService


def _make_order(ordered_at: datetime, lead_time_days: int = 10) -> MagicMock:
    """Create a mock Order with items."""
    product = MagicMock()
    product.lead_time_days = lead_time_days

    order_item = MagicMock(spec=OrderItem)
    order_item.product = product

    order = MagicMock(spec=Order)
    order.id = "order-1"
    order.status = OrderStatus.DELIVERED.value
    order.ordered_at = ordered_at
    order.items = [order_item]
    return order


@pytest.mark.asyncio
async def test_create_shipment_persists_estimated_shipping_date():
    """delivered時にShipment作成で estimated_shipping_date が渡される."""
    order_repo = AsyncMock()
    shipment_repo = AsyncMock()
    file_storage = MagicMock()
    settings_service = AsyncMock()

    settings_service.get_shipping_preparation_days_value = AsyncMock(return_value=5)
    settings_service.get_company_holiday_dates = AsyncMock(return_value=set())

    service = OrderService(
        order_repo=order_repo,
        shipment_repo=shipment_repo,
        file_storage=file_storage,
        settings_service=settings_service,
    )

    ordered_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order = _make_order(ordered_at=ordered_at, lead_time_days=10)

    shipment_repo.exists_for_order = AsyncMock(return_value=False)
    shipment_repo.create = AsyncMock()

    await service._create_shipment_for_order(order)

    shipment_repo.create.assert_called_once()
    call_kwargs = shipment_repo.create.call_args
    assert call_kwargs.kwargs.get("estimated_shipping_date") is not None
    # ordered_at(4/1) + 10日 = 4/11, then + 5 business days
    assert isinstance(call_kwargs.kwargs["estimated_shipping_date"], date)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd api && uv run pytest tests/unit/test_order_estimated_shipping_date.py -v`
Expected: FAIL — `_create_shipment_for_order` がまだ `estimated_shipping_date` を渡していない

- [ ] **Step 3: OrderService._create_shipment_for_order を修正**

`api/app/services/order_service.py` の `_create_shipment_for_order` メソッドを修正:

```python
    async def _create_shipment_for_order(self, order: Order) -> None:
        """Create a shipment for the delivered order.

        This method is idempotent - if a shipment already exists for the order,
        it will not create a duplicate. The shipment creation happens within
        the same transaction as the order status update, ensuring atomicity.

        顧客情報は Shipment から Order のリレーションを経由して取得します。

        Args:
            order: The order that was just marked as delivered.

        Raises:
            Exception: If shipment creation fails, the entire transaction
                       (including order status update) will be rolled back.
        """
        # Check if shipment already exists (prevent duplicates)
        if await self._shipment_repo.exists_for_order(order.id):
            return

        estimated_date = await self._calculate_estimated_shipping_date(order)
        await self._shipment_repo.create(
            order_ids=[order.id],
            estimated_shipping_date=estimated_date,
        )

    async def _calculate_estimated_shipping_date(self, order: Order) -> date | None:
        """注文の納品予定日を計算する."""
        if not self._settings_service:
            return None

        from datetime import timedelta
        from app.utils.business_day_calculator import add_business_days

        prep_days = await self._settings_service.get_shipping_preparation_days_value()
        company_holidays = await self._settings_service.get_company_holiday_dates()

        delivery_dates: list[date] = []
        if order.items:
            for order_item in order.items:
                product = order_item.product if order_item.product else None
                if product and product.lead_time_days is not None:
                    d = order.ordered_at.date() + timedelta(days=product.lead_time_days)
                    delivery_dates.append(d)

        if not delivery_dates:
            return None

        latest_delivery = max(delivery_dates)
        return add_business_days(latest_delivery, prep_days, company_holidays)
```

`OrderService.__init__` に `settings_service` パラメータが既にあるか確認し、なければ追加する。

- [ ] **Step 4: テストがパスすることを確認**

Run: `cd api && uv run pytest tests/unit/test_order_estimated_shipping_date.py -v`
Expected: PASS

- [ ] **Step 5: 既存テストが壊れていないことを確認**

Run: `cd api && uv run pytest tests/unit/test_order_service_status.py tests/unit/test_order_service_bulk_status.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add api/app/services/order_service.py api/tests/unit/test_order_estimated_shipping_date.py
git commit -m "feat: persist estimated_shipping_date when OrderService creates shipment"
```

---

### Task 5: Shipment作成時に納品予定日を計算して保存 — ManufacturerOrderService

**Files:**
- Modify: `api/app/services/manufacturer_order_service.py:278-293`
- Test: `api/tests/unit/test_manufacturer_order_estimated_date.py`

- [ ] **Step 1: テストを書く**

```python
"""Test ManufacturerOrderService persists estimated_shipping_date on shipment creation."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderItem, OrderItemStatus
from app.services.manufacturer_order_service import ManufacturerOrderService


@pytest.mark.asyncio
async def test_create_shipment_persists_estimated_shipping_date():
    """全OrderItem delivered時にShipment作成でestimated_shipping_dateが渡される."""
    order_repo = AsyncMock()
    shipment_repo = AsyncMock()
    settings_service = AsyncMock()

    settings_service.get_shipping_preparation_days_value = AsyncMock(return_value=5)
    settings_service.get_company_holiday_dates = AsyncMock(return_value=set())

    service = ManufacturerOrderService(
        order_repo=order_repo,
        shipment_repo=shipment_repo,
        settings_service=settings_service,
    )

    product = MagicMock()
    product.lead_time_days = 7

    order_item = MagicMock(spec=OrderItem)
    order_item.product = product

    order = MagicMock(spec=Order)
    order.id = "order-1"
    order.ordered_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order.items = [order_item]

    shipment_repo.exists_for_order = AsyncMock(return_value=False)
    shipment_repo.create = AsyncMock()

    await service._create_shipment_for_order(order)

    shipment_repo.create.assert_called_once()
    call_kwargs = shipment_repo.create.call_args
    assert call_kwargs.kwargs.get("estimated_shipping_date") is not None
    assert isinstance(call_kwargs.kwargs["estimated_shipping_date"], date)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd api && uv run pytest tests/unit/test_manufacturer_order_estimated_date.py -v`
Expected: FAIL

- [ ] **Step 3: ManufacturerOrderService._create_shipment_for_order を修正**

`api/app/services/manufacturer_order_service.py` の `_create_shipment_for_order` メソッドを修正:

```python
    async def _create_shipment_for_order(self, order: Order) -> bool:
        """Create a shipment for the delivered order.

        This method is idempotent - if a shipment already exists for the order,
        it will not create a duplicate.

        Returns:
            bool: True if a shipment was created, False if it already existed
        """
        # Check if shipment already exists (prevent duplicates)
        if await self._shipment_repo.exists_for_order(order.id):
            return False

        estimated_date = await self._calculate_estimated_shipping_date(order)
        await self._shipment_repo.create(
            order_ids=[order.id],
            estimated_shipping_date=estimated_date,
        )
        return True

    async def _calculate_estimated_shipping_date(self, order: Order) -> date | None:
        """注文の納品予定日を計算する."""
        if not self._settings_service:
            return None

        from datetime import timedelta
        from app.utils.business_day_calculator import add_business_days

        prep_days = await self._settings_service.get_shipping_preparation_days_value()
        company_holidays = await self._settings_service.get_company_holiday_dates()

        delivery_dates: list[date] = []
        if order.items:
            for order_item in order.items:
                product = order_item.product if order_item.product else None
                if product and product.lead_time_days is not None:
                    d = order.ordered_at.date() + timedelta(days=product.lead_time_days)
                    delivery_dates.append(d)

        if not delivery_dates:
            return None

        latest_delivery = max(delivery_dates)
        return add_business_days(latest_delivery, prep_days, company_holidays)
```

`ManufacturerOrderService.__init__` に `settings_service` パラメータが既にあるか確認し、なければ追加。DIコンテナ（依存注入の箇所）でも `settings_service` を渡すようにする。

- [ ] **Step 4: テストがパスすることを確認**

Run: `cd api && uv run pytest tests/unit/test_manufacturer_order_estimated_date.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/services/manufacturer_order_service.py api/tests/unit/test_manufacturer_order_estimated_date.py
git commit -m "feat: persist estimated_shipping_date when ManufacturerOrderService creates shipment"
```

---

### Task 6: ShipmentService — DB値を使うように変更 & pending orderのestimated_shipping_dateをNullに

**Files:**
- Modify: `api/app/services/shipment_service.py:142-163, 198-247`
- Modify: `api/app/services/shipment_service.py:73-89` (ShipmentService.create)
- Test: `api/tests/unit/test_shipment_pending_orders.py` (既存テスト修正)

- [ ] **Step 1: テストを書く**

`api/tests/unit/test_shipment_estimated_date_persistence.py` を新規作成:

```python
"""Test that ShipmentService uses DB value for estimated_shipping_date."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus
from app.schemas.shipment import PendingOrderStatus
from app.services.shipment_service import ShipmentService


def _make_shipment(estimated_date: date | None = None) -> MagicMock:
    """Create a mock Shipment with estimated_shipping_date."""
    order = MagicMock()
    order.id = "order-1"
    order.order_number = "ORD-001"
    order.customer_name = "テスト太郎"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "東京都"
    order.customer_address_city = "千代田区"
    order.customer_address_building = None
    order.customer_phone = "03-1234-5678"
    order.items = []

    item = MagicMock(spec=ShipmentItem)
    item.id = "item-1"
    item.order_id = "order-1"
    item.order = order

    shipment = MagicMock(spec=Shipment)
    shipment.id = "ship-1"
    shipment.status = ShipmentStatus.PENDING.value
    shipment.tracking_number = None
    shipment.carrier = None
    shipment.packing_photo_path = None
    shipment.shipped_at = None
    shipment.delivered_at = None
    shipment.note = None
    shipment.created_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    shipment.updated_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    shipment.estimated_shipping_date = estimated_date
    shipment.items = [item]
    shipment.first_order = order
    return shipment


@pytest.mark.asyncio
async def test_list_shipment_uses_db_estimated_date():
    """Shipmentの納品予定日はDBの値をそのまま返す."""
    shipment_repo = AsyncMock()
    order_repo = AsyncMock()
    file_storage = MagicMock()
    settings_service = AsyncMock()

    shipment = _make_shipment(estimated_date=date(2026, 4, 20))
    shipment_repo.find_all = AsyncMock(return_value=([shipment], 1))
    order_repo.find_pending_orders = AsyncMock(return_value=([], 0))

    service = ShipmentService(
        shipment_repo=shipment_repo,
        order_repo=order_repo,
        file_storage=file_storage,
        settings_service=settings_service,
    )

    result = await service.list_with_pending_orders()

    assert result.items[0].estimated_shipping_date == date(2026, 4, 20)
    # settings_service should NOT be called for calculation
    settings_service.get_shipping_preparation_days_value.assert_not_called()


@pytest.mark.asyncio
async def test_pending_order_has_null_estimated_date():
    """Pending orderの納品予定日はNone（フロントで「-」表示）."""
    shipment_repo = AsyncMock()
    order_repo = AsyncMock()
    file_storage = MagicMock()
    settings_service = AsyncMock()

    order = MagicMock()
    order.id = "order-1"
    order.order_number = "ORD-001"
    order.customer_name = "テスト太郎"
    order.customer_postal_code = "100-0001"
    order.customer_address_prefecture = "東京都"
    order.customer_address_city = "千代田区"
    order.customer_address_building = None
    order.customer_phone = "03-1234-5678"
    order.ordered_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order.created_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    order.items = []

    shipment_repo.find_all = AsyncMock(return_value=([], 0))
    order_repo.find_pending_orders = AsyncMock(return_value=([order], 1))

    service = ShipmentService(
        shipment_repo=shipment_repo,
        order_repo=order_repo,
        file_storage=file_storage,
        settings_service=settings_service,
    )

    result = await service.list_with_pending_orders(
        pending_order_status=PendingOrderStatus.PREPARING,
    )

    assert result.items[0].estimated_shipping_date is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd api && uv run pytest tests/unit/test_shipment_estimated_date_persistence.py -v`
Expected: FAIL — まだ動的計算している

- [ ] **Step 3: ShipmentService.list_with_pending_orders を修正**

`api/app/services/shipment_service.py` の `list_with_pending_orders` メソッドを修正:

1. Shipment側: 動的計算を削除し、`_to_response` がDB値をそのまま返すようにする
2. Pending order側: `estimated_shipping_date` の動的計算を削除（常にNone）
3. settings取得ロジック（prep_days, company_holidays）を削除

```python
    async def list_with_pending_orders(
        self,
        page: int = 1,
        limit: int = 20,
        shipment_status: ShipmentStatus | None = None,
        pending_order_status: PendingOrderStatus | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        search: str | None = None,
        tracking_number: str | None = None,
        carrier: str | None = None,
        shipped_from: date | None = None,
        shipped_to: date | None = None,
        delivered_from: date | None = None,
        delivered_to: date | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> ShipmentListWithPendingResponse:
        """List shipments with pending orders."""
        items: list = []
        shipment_total = 0
        pending_total = 0

        # If filtering by PendingOrderStatus, skip shipments
        if pending_order_status is None:
            shipments, shipment_total = await self._shipment_repo.find_all(
                page=page,
                limit=limit,
                status=shipment_status,
                created_from=created_from,
                created_to=created_to,
                search=search,
                tracking_number=tracking_number,
                carrier=carrier,
                shipped_from=shipped_from,
                shipped_to=shipped_to,
                delivered_from=delivered_from,
                delivered_to=delivered_to,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            for shipment in shipments:
                response = self._to_response(shipment)
                response.estimated_shipping_date = shipment.estimated_shipping_date
                items.append(response)

        # If filtering by ShipmentStatus, skip pending orders
        if shipment_status is None:
            pending_orders, pending_total = await self._order_repo.find_pending_orders(
                page=page,
                limit=limit,
                status=pending_order_status,
            )
            for order in pending_orders:
                response = self._to_pending_order_response(order)
                # pending orderは納品予定日なし（フロントで「-」表示）
                response.estimated_shipping_date = None
                items.append(response)

        total = shipment_total + pending_total

        return ShipmentListWithPendingResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )
```

- [ ] **Step 4: ShipmentService.create にもestimated_shipping_date計算を追加**

`api/app/services/shipment_service.py` の `create` メソッドを修正（手動でShipment作成する場合もDB保存する）:

```python
    async def create(self, data: ShipmentCreate) -> ShipmentResponse:
        """Create a new shipment."""
        orders = []
        for order_id in data.order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if not order:
                raise ValidationError(f"Order {order_id} not found")
            if order.status != OrderStatus.DELIVERED.value:
                raise ValidationError(f"Order {order_id} is not in delivered status")
            if await self._shipment_repo.exists_for_order(order_id):
                raise ValidationError(f"Order {order_id} already has a shipment")
            orders.append(order)

        estimated_date = await self._calculate_estimated_shipping_date_for_orders(orders)
        shipment = await self._shipment_repo.create(
            order_ids=data.order_ids,
            estimated_shipping_date=estimated_date,
        )

        return self._to_response(shipment)

    async def _calculate_estimated_shipping_date_for_orders(
        self, orders: list
    ) -> date | None:
        """複数注文から納品予定日を計算する."""
        if not self._settings_service:
            return None

        prep_days = await self._settings_service.get_shipping_preparation_days_value()
        company_holidays = await self._settings_service.get_company_holiday_dates()

        return self._calculate_estimated_shipping_date(orders, prep_days, company_holidays)
```

- [ ] **Step 5: テストがパスすることを確認**

Run: `cd api && uv run pytest tests/unit/test_shipment_estimated_date_persistence.py -v`
Expected: PASS

- [ ] **Step 6: 既存テストが壊れていないことを確認**

Run: `cd api && uv run pytest tests/unit/test_shipment_pending_orders.py tests/unit/test_shipment_service_status.py -v`
Expected: ALL PASS（既存テストの修正が必要な場合は対応）

- [ ] **Step 7: Commit**

```bash
git add api/app/services/shipment_service.py api/tests/unit/test_shipment_estimated_date_persistence.py
git commit -m "feat: use DB-persisted estimated_shipping_date, remove dynamic calculation for pending orders"
```

---

### Task 7: フロントエンド — pending orderで「-」表示の確認

**Files:**
- Review: `web/src/features/shipments/components/shipment-list.tsx:63-65`

- [ ] **Step 1: 既存のフロント実装を確認**

`shipment-list.tsx` の `getEstimatedShippingDate` 関数を確認:

```typescript
function getEstimatedShippingDate(item: ShipmentOrPendingOrder): string {
  const dateStr = "estimated_shipping_date" in item ? item.estimated_shipping_date : null;
  if (!dateStr) return "-";
  // ...
}
```

既に `null` → `"-"` の変換が実装されている。バックエンドが pending order に対して `estimated_shipping_date: null` を返すようにしたので、**フロントエンドの変更は不要**。

- [ ] **Step 2: Commit（変更なし）**

フロントエンドの変更は不要。確認のみ。

---

### Task 8: 全体テスト実行 & DIコンテナ修正

**Files:**
- Modify: DI設定ファイル（`settings_service` の注入箇所を確認・修正）

- [ ] **Step 1: OrderServiceのDI設定を確認**

`OrderService` に `settings_service` が注入されているか確認。されていなければ、DIコンテナ（`api/app/dependencies.py` や `api/app/routers/` の依存注入箇所）で `settings_service` を渡すように修正。

- [ ] **Step 2: ManufacturerOrderServiceのDI設定を確認**

同様に `ManufacturerOrderService` に `settings_service` が注入されているか確認・修正。

- [ ] **Step 3: 全ユニットテスト実行**

Run: `cd api && uv run pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 4: 全統合テスト実行**

Run: `cd api && uv run pytest tests/integration/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit（DI修正があった場合）**

```bash
git add -A
git commit -m "fix: inject settings_service into OrderService and ManufacturerOrderService for estimated date calculation"
```

---

### Task 9: 既存Shipmentデータのバックフィル（オプション）

**Files:**
- Review: 既存データの扱い

- [ ] **Step 1: 既存データの扱いを確認**

既存Shipmentの `estimated_shipping_date` は `NULL` のまま。フロントで `null` → `"-"` 表示されるので表示上は問題なし。

必要に応じて手動でバックフィルするSQLを用意できるが、「発注時点で確定」の方針なので、過去データは NULL のままが自然。

- [ ] **Step 2: 完了確認**

動作確認を実施して完了。
