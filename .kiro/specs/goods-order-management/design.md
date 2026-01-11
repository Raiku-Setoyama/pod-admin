# Technical Design: goods-order-management

## Overview

PODグッズ受発注管理システムの技術設計ドキュメント。フロントエンド（Next.js）とバックエンド（FastAPI）をモノレポ構成で実装する。

### Scope

**バックエンド（api/）**:
- FastAPI による REST API
- PostgreSQL データベース
- レイヤードアーキテクチャ

**フロントエンド（web/）**:
- 管理者向け Web アプリケーション
- メーカー専用ページ
- バックエンド API との通信層

**共有（openapi/）**:
- OpenAPI スキーマ定義
- フロントエンド型生成のソース

### Out of Scope

- インフラストラクチャ（デプロイ環境）
- 外部連携の詳細実装（TOSYO DRIVE API仕様が未確定）

---

## Architecture Pattern & Boundary Map

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          External Systems                                │
├─────────────────────────────────────────────────────────────────────────┤
│  [外部販売サイト]     [TOSYO DRIVE]      [配送代行PG]    [運送会社]       │
│       │                   ▲                  ▲              ▲           │
│       │ POST /api/orders  │ Upload           │ CSV          │ CSV       │
│       ▼                   │                  │              │           │
├─────────────────────────────────────────────────────────────────────────┤
│                         api/ (FastAPI)                                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        Routers                                    │   │
│  │  /orders    /purchase-orders    /manufacturers    /shipments     │   │
│  │  /products  /chat               /manufacturer-portal              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        Services                                   │   │
│  │  OrderService  PurchaseOrderService  ManufacturerService  ...    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Repositories                                 │   │
│  │  OrderRepository  ManufacturerRepository  ShipmentRepository ...  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    PostgreSQL Database                            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                              ▲                                           │
│                              │ HTTP (REST API)                           │
│                              ▼                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                         web/ (Next.js)                                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     App Router (Pages)                            │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │   │
│  │  │ (dashboard)/    │  │ (manufacturer)/ │  │ (auth)/         │   │   │
│  │  │ - orders        │  │ - login         │  │ - login         │   │   │
│  │  │ - manufacturers │  │ - orders        │  │                 │   │   │
│  │  │ - shipments     │  │ - status        │  │                 │   │   │
│  │  │ - products      │  │                 │  │                 │   │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Feature Modules                                │   │
│  │  orders  │  manufacturers  │  shipments  │  products             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              lib/api/ (API Client)                                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Backend Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Routers                                │
│  - HTTP リクエスト/レスポンス処理                              │
│  - 入力バリデーション（Pydantic Schema）                       │
│  - Service 呼び出し                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Services                               │
│  - ビジネスロジック実装                                        │
│  - 複数 Repository の連携                                     │
│  - トランザクション管理                                        │
│  - 業務例外の発生                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Repositories                             │
│  - CRUD 操作                                                  │
│  - クエリ構築                                                 │
│  - DB セッション利用                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Models                                 │
│  - SQLAlchemy ORM マッピング                                  │
│  - テーブル定義                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack & Alignment

### Backend (api/)

| カテゴリ | 技術 | 根拠 |
|---------|------|------|
| フレームワーク | FastAPI | fastapi-architecture-guide.md 指定 |
| 言語 | Python 3.12+ | 最新 LTS |
| ORM | SQLAlchemy 2.0 (async) | research.md ADR-004 |
| DB ドライバ | asyncpg | 非同期 PostgreSQL |
| バリデーション | Pydantic v2 | FastAPI 標準 |
| データベース | PostgreSQL 16 | 信頼性・機能性 |
| マイグレーション | Alembic | SQLAlchemy 標準 |
| 認証 | python-jose (JWT) | 軽量・標準的 |
| Excel 生成 | openpyxl | research.md ADR-002 |
| ZIP 処理 | zipfile (標準ライブラリ) | 発注資料 ZIP 化 |
| CSV 処理 | csv (標準ライブラリ) | 配送ラベル CSV |

### Frontend (web/)

| カテゴリ | 技術 | 根拠 |
|---------|------|------|
| フレームワーク | Next.js 15 (App Router) | steering 指定 |
| 言語 | TypeScript | steering 指定 |
| UI ライブラリ | shadcn/ui | steering 指定 |
| スタイリング | Tailwind CSS | steering 指定 |
| データフェッチング | SWR | research.md ADR-001 |
| フォーム | React Hook Form + Zod | steering 指定 |
| API 型生成 | openapi-typescript | steering 指定 |

---

## Components & Interface Contracts

### Database Models (SQLAlchemy)

```python
# models/order.py
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[OrderStatus] = mapped_column(default=OrderStatus.PENDING)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(200))
    price: Mapped[int] = mapped_column()
    quantity: Mapped[int] = mapped_column(default=1)

    # Customer info (embedded)
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_postal_code: Mapped[str] = mapped_column(String(10))
    customer_address: Mapped[str] = mapped_column(String(500))
    customer_phone: Mapped[str] = mapped_column(String(20))
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Manufacturing data (1ファイル/受注)
    manufacturing_data_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturing_data_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manufacturing_data_size: Mapped[int | None] = mapped_column(nullable=True)

    ordered_at: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="orders")
    purchase_order_items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="order")


class OrderStatus(str, Enum):
    PENDING = "pending"           # 受注済み（発注前）
    ORDERED = "ordered"           # 発注済み
    MANUFACTURING = "manufacturing"  # 製造中
    DELIVERED = "delivered"       # 納入済み
    SHIPPING = "shipping"         # 配送中
    COMPLETED = "completed"       # 配送完了


# models/manufacturer.py
class Manufacturer(Base):
    __tablename__ = "manufacturers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    supported_products: Mapped[list[str]] = mapped_column(ARRAY(String))
    unit_prices: Mapped[dict] = mapped_column(JSONB)  # {"acrylic_keychain": 500, ...}
    lead_time_days: Mapped[int] = mapped_column()
    daily_order_limit: Mapped[int] = mapped_column()
    sharing_method: Mapped[str] = mapped_column(String(20))  # "drive" or "portal"
    is_active: Mapped[bool] = mapped_column(default=True)

    # Auth for portal
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="manufacturer")


# models/purchase_order.py
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    manufacturer_id: Mapped[UUID] = mapped_column(ForeignKey("manufacturers.id"))
    status: Mapped[PurchaseOrderStatus] = mapped_column(default=PurchaseOrderStatus.ORDERED)
    ordered_at: Mapped[datetime] = mapped_column(default=func.now())
    expected_delivery_at: Mapped[datetime] = mapped_column()
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="purchase_order")


class PurchaseOrderStatus(str, Enum):
    ORDERED = "ordered"
    MANUFACTURING = "manufacturing"
    DELIVERED = "delivered"


# models/product.py
class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    size: Mapped[str] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manufacturer_id: Mapped[UUID] = mapped_column(ForeignKey("manufacturers.id"))
    cost: Mapped[int] = mapped_column()
    lead_time_days: Mapped[int] = mapped_column()
    order_limit: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    manufacturer: Mapped["Manufacturer"] = relationship()
    orders: Mapped[list["Order"]] = relationship(back_populates="product")


# models/shipment.py
class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[ShipmentStatus] = mapped_column(default=ShipmentStatus.PENDING)
    tracking_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    carrier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    packing_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    items: Mapped[list["ShipmentItem"]] = relationship(back_populates="shipment")


class ShipmentStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    SHIPPING = "shipping"
    COMPLETED = "completed"
```

### Pydantic Schemas

```python
# schemas/order.py
class OrderBase(BaseModel):
    order_number: str
    product_id: UUID
    product_name: str
    price: int
    quantity: int = 1
    customer_name: str
    customer_postal_code: str
    customer_address: str
    customer_phone: str
    customer_email: str | None = None
    ordered_at: datetime


class OrderCreate(OrderBase):
    """外部販売サイトからの受注登録リクエスト"""
    pass


class ManufacturingDataInfo(BaseModel):
    """製造データ情報（1受注1ファイル）"""
    filename: str | None
    path: str | None
    size: int | None
    download_url: str | None = None  # 動的に生成


class OrderResponse(OrderBase):
    id: UUID
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    manufacturing_data: ManufacturingDataInfo | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    limit: int


# schemas/manufacturer.py
class ManufacturerBase(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    supported_products: list[ProductType]
    unit_prices: dict[ProductType, int]
    lead_time_days: int
    daily_order_limit: int
    sharing_method: Literal["drive", "portal"]


class ManufacturerCreate(ManufacturerBase):
    password: str | None = None  # portal の場合は必須


class ManufacturerUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    supported_products: list[ProductType] | None = None
    unit_prices: dict[ProductType, int] | None = None
    lead_time_days: int | None = None
    daily_order_limit: int | None = None
    sharing_method: Literal["drive", "portal"] | None = None
    is_active: bool | None = None


class ManufacturerResponse(ManufacturerBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# schemas/purchase_order.py
class PurchaseOrderCreate(BaseModel):
    order_ids: list[UUID]
    manufacturer_id: UUID


class PurchaseOrderStatusUpdate(BaseModel):
    status: PurchaseOrderStatus
    note: str | None = None


class PurchaseOrderResponse(BaseModel):
    id: UUID
    manufacturer_id: UUID
    manufacturer_name: str
    status: PurchaseOrderStatus
    order_ids: list[UUID]
    ordered_at: datetime
    expected_delivery_at: datetime
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### API Endpoints (FastAPI Routers)

```python
# routers/orders.py
router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    manufacturing_data: UploadFile = File(...),  # 1受注1ファイル
    service: OrderService = Depends(get_order_service),
    api_key: str = Depends(verify_api_key),
) -> OrderResponse:
    """外部販売サイトからの受注登録（F-001: 要件 1.1.1-1.1.6）"""
    return await service.create_order(data, manufacturing_data)


@router.get("/", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: OrderStatus | None = None,
    product_type: ProductType | None = None,
    ordered_from: date | None = None,
    ordered_to: date | None = None,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_admin),
) -> OrderListResponse:
    """受注一覧取得（F-002: 要件 1.2.1-1.2.4）"""
    return await service.list_orders(page, limit, status, product_type, ordered_from, ordered_to)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_admin),
) -> OrderResponse:
    """受注詳細取得（F-002: 要件 1.2.2-1.2.3）"""
    return await service.get_order(order_id)


# routers/purchase_orders.py
router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])

@router.post("/", response_model=PurchaseOrderResponse, status_code=201)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    service: PurchaseOrderService = Depends(get_purchase_order_service),
    current_user: User = Depends(get_current_admin),
) -> PurchaseOrderResponse:
    """メーカー発注実行（F-003: 要件 2.1.1-2.1.4）"""
    return await service.create_purchase_order(data)


@router.get("/{po_id}/documents")
async def download_purchase_order_documents(
    po_id: UUID,
    format: Literal["xlsx", "csv", "zip"] = "zip",
    service: PurchaseOrderService = Depends(get_purchase_order_service),
    current_user: User = Depends(get_current_admin),
) -> StreamingResponse:
    """発注資料ダウンロード（F-004: 要件 2.2.1-2.2.4）"""
    return await service.generate_documents(po_id, format)


@router.patch("/{po_id}/status", response_model=PurchaseOrderResponse)
async def update_purchase_order_status(
    po_id: UUID,
    data: PurchaseOrderStatusUpdate,
    service: PurchaseOrderService = Depends(get_purchase_order_service),
    current_user: User = Depends(get_current_admin),
) -> PurchaseOrderResponse:
    """発注ステータス更新（F-006: 要件 2.4.1-2.4.4）"""
    return await service.update_status(po_id, data)


# routers/manufacturers.py
router = APIRouter(prefix="/manufacturers", tags=["manufacturers"])

@router.get("/", response_model=list[ManufacturerResponse])
@router.post("/", response_model=ManufacturerResponse, status_code=201)
@router.get("/{manufacturer_id}", response_model=ManufacturerResponse)
@router.patch("/{manufacturer_id}", response_model=ManufacturerResponse)
@router.delete("/{manufacturer_id}", status_code=204)
# F-007: 要件 3.1.1-3.1.4

@router.get("/{manufacturer_id}/chat", response_model=list[ChatMessageResponse])
@router.post("/{manufacturer_id}/chat", response_model=ChatMessageResponse)
# F-008: 要件 3.2.1-3.2.4


# routers/manufacturer_portal.py
router = APIRouter(prefix="/manufacturer-portal", tags=["manufacturer-portal"])

@router.post("/login")
async def manufacturer_login(
    data: ManufacturerLoginRequest,
    service: ManufacturerPortalService = Depends(get_manufacturer_portal_service),
) -> TokenResponse:
    """メーカーログイン（F-009: 要件 4.1）"""
    return await service.login(data)


@router.get("/orders", response_model=list[ManufacturerOrderResponse])
async def list_manufacturer_orders(
    service: ManufacturerPortalService = Depends(get_manufacturer_portal_service),
    current_manufacturer: Manufacturer = Depends(get_current_manufacturer),
) -> list[ManufacturerOrderResponse]:
    """メーカー向け発注一覧（F-009: 要件 4.2）"""
    return await service.list_orders(current_manufacturer.id)


@router.get("/orders/{po_id}/documents")
async def download_manufacturer_documents(
    po_id: UUID,
    format: Literal["xlsx", "csv", "zip"] = "zip",
    service: ManufacturerPortalService = Depends(get_manufacturer_portal_service),
    current_manufacturer: Manufacturer = Depends(get_current_manufacturer),
) -> StreamingResponse:
    """発注資料ダウンロード（F-009: 要件 4.3-4.4）"""
    return await service.download_documents(po_id, current_manufacturer.id, format)


@router.patch("/orders/{po_id}/status")
async def update_manufacturer_order_status(
    po_id: UUID,
    data: ManufacturerStatusUpdate,
    service: ManufacturerPortalService = Depends(get_manufacturer_portal_service),
    current_manufacturer: Manufacturer = Depends(get_current_manufacturer),
):
    """ステータス更新（F-009: 要件 4.5-4.6）"""
    return await service.update_status(po_id, current_manufacturer.id, data)


# routers/shipments.py
router = APIRouter(prefix="/shipments", tags=["shipments"])

@router.post("/", response_model=ShipmentResponse, status_code=201)
# F-010: 要件 5.1.1-5.1.3

@router.get("/{shipment_id}/documents")
# F-011: 要件 5.2.1-5.2.5

@router.post("/{shipment_id}/packing-photo")
# F-012: 要件 5.3.1-5.3.3

@router.patch("/{shipment_id}/status")
@router.post("/import-tracking")
# F-013: 要件 5.4.1-5.4.4


# routers/products.py
router = APIRouter(prefix="/products", tags=["products"])

@router.get("/", response_model=list[ProductResponse])
@router.post("/", response_model=ProductResponse, status_code=201)
@router.get("/{product_id}", response_model=ProductResponse)
@router.patch("/{product_id}", response_model=ProductResponse)
@router.delete("/{product_id}", status_code=204)
# F-014: 要件 6.1.1-6.1.5


# routers/dashboard.py
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/summary", response_model=DashboardSummary)
# S-001: 要件 7.1.1-7.1.3
```

### Service Layer Example

```python
# services/order_service.py
class OrderService:
    def __init__(
        self,
        order_repo: OrderRepository,
        product_repo: ProductRepository,
        file_storage: FileStorage,
    ):
        self._order_repo = order_repo
        self._product_repo = product_repo
        self._file_storage = file_storage

    async def create_order(
        self,
        data: OrderCreate,
        manufacturing_data: UploadFile,  # 1受注1ファイル
    ) -> Order:
        # 1. 商品マスタ照合（要件 1.1.2）
        product = await self._product_repo.find_by_id(data.product_id)
        if not product:
            raise ProductNotFoundError(data.product_id)

        # 2. 製造データ保存（要件 1.1.4 - そのまま保存）
        file_path = await self._file_storage.save(
            manufacturing_data,
            f"orders/{data.order_number}/",
        )

        # 3. 受注データ登録（要件 1.1.4）
        order = await self._order_repo.create(
            data,
            manufacturing_data_filename=manufacturing_data.filename,
            manufacturing_data_path=file_path,
            manufacturing_data_size=manufacturing_data.size,
        )

        return order

    async def list_orders(
        self,
        page: int,
        limit: int,
        status: OrderStatus | None,
        product_type: ProductType | None,
        ordered_from: date | None,
        ordered_to: date | None,
    ) -> OrderListResponse:
        orders, total = await self._order_repo.find_all(
            page=page,
            limit=limit,
            status=status,
            product_type=product_type,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
        )
        return OrderListResponse(
            items=orders,
            total=total,
            page=page,
            limit=limit,
        )


# services/purchase_order_service.py
class PurchaseOrderService:
    def __init__(
        self,
        po_repo: PurchaseOrderRepository,
        order_repo: OrderRepository,
        manufacturer_repo: ManufacturerRepository,
        excel_generator: ExcelGenerator,
        file_storage: FileStorage,
        drive_client: DriveClient | None = None,
    ):
        self._po_repo = po_repo
        self._order_repo = order_repo
        self._manufacturer_repo = manufacturer_repo
        self._excel_generator = excel_generator
        self._file_storage = file_storage
        self._drive_client = drive_client

    async def create_purchase_order(
        self,
        data: PurchaseOrderCreate,
    ) -> PurchaseOrder:
        # 1. メーカー取得（要件 2.1.1）
        manufacturer = await self._manufacturer_repo.find_by_id(data.manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(data.manufacturer_id)

        # 2. 1日発注上限チェック（要件 2.1.2）
        today_count = await self._po_repo.count_today_orders(data.manufacturer_id)
        if today_count >= manufacturer.daily_order_limit:
            raise DailyOrderLimitExceededError(manufacturer.name)

        # 3. 発注作成（要件 2.1.3-2.1.4）
        expected_delivery = self._calculate_delivery_date(manufacturer.lead_time_days)
        po = await self._po_repo.create(
            manufacturer_id=data.manufacturer_id,
            order_ids=data.order_ids,
            expected_delivery_at=expected_delivery,
        )

        # 4. 受注ステータス更新
        for order_id in data.order_ids:
            await self._order_repo.update_status(order_id, OrderStatus.ORDERED)

        # 5. DRIVE アップロード（要件 2.3.3）
        if manufacturer.sharing_method == "drive" and self._drive_client:
            documents = await self.generate_documents(po.id, "zip")
            await self._drive_client.upload(documents)

        return po
```

### Dependency Injection

```python
# dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def get_order_repository(db: AsyncSession = Depends(get_db)) -> OrderRepository:
    return OrderRepository(db)


def get_product_repository(db: AsyncSession = Depends(get_db)) -> ProductRepository:
    return ProductRepository(db)


def get_file_storage() -> FileStorage:
    return LocalFileStorage(settings.UPLOAD_DIR)


def get_order_service(
    order_repo: OrderRepository = Depends(get_order_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
    file_storage: FileStorage = Depends(get_file_storage),
) -> OrderService:
    return OrderService(order_repo, product_repo, file_storage)
```

### Exception Handling

```python
# utils/exceptions.py
class AppException(Exception):
    def __init__(self, status_code: int, code: str, detail: str):
        self.status_code = status_code
        self.code = code
        self.detail = detail


class NotFoundError(AppException):
    def __init__(self, resource: str, id: UUID):
        super().__init__(404, "NOT_FOUND", f"{resource} with id {id} not found")


class ProductNotFoundError(NotFoundError):
    def __init__(self, product_id: UUID):
        super().__init__("Product", product_id)


class ManufacturerNotFoundError(NotFoundError):
    def __init__(self, manufacturer_id: UUID):
        super().__init__("Manufacturer", manufacturer_id)


class DailyOrderLimitExceededError(AppException):
    def __init__(self, manufacturer_name: str):
        super().__init__(
            400,
            "DAILY_LIMIT_EXCEEDED",
            f"Daily order limit exceeded for {manufacturer_name}",
        )


class ValidationError(AppException):
    def __init__(self, detail: str, errors: dict[str, list[str]] | None = None):
        super().__init__(400, "VALIDATION_ERROR", detail)
        self.errors = errors


class UnauthorizedError(AppException):
    def __init__(self):
        super().__init__(401, "UNAUTHORIZED", "Authentication required")


class ForbiddenError(AppException):
    def __init__(self):
        super().__init__(403, "FORBIDDEN", "Access denied")


# main.py
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    content = {"error": {"code": exc.code, "message": exc.detail}}
    if hasattr(exc, "errors") and exc.errors:
        content["error"]["details"] = exc.errors
    return JSONResponse(status_code=exc.status_code, content=content)
```

---

## File Structure

```
project/
├── api/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI アプリケーション
│   │   ├── config.py                  # 環境設定
│   │   ├── database.py                # DB 接続設定
│   │   ├── dependencies.py            # DI 関数
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── orders.py              # 受注 API
│   │   │   ├── purchase_orders.py     # 発注 API
│   │   │   ├── manufacturers.py       # メーカー API
│   │   │   ├── manufacturer_portal.py # メーカーポータル API
│   │   │   ├── shipments.py           # 配送 API
│   │   │   ├── products.py            # 商品マスタ API
│   │   │   ├── chat.py                # チャット API
│   │   │   ├── dashboard.py           # ダッシュボード API
│   │   │   └── auth.py                # 認証 API
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── order_service.py
│   │   │   ├── purchase_order_service.py
│   │   │   ├── manufacturer_service.py
│   │   │   ├── manufacturer_portal_service.py
│   │   │   ├── shipment_service.py
│   │   │   ├── product_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── dashboard_service.py
│   │   │   └── auth_service.py
│   │   │
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── order_repository.py
│   │   │   ├── purchase_order_repository.py
│   │   │   ├── manufacturer_repository.py
│   │   │   ├── shipment_repository.py
│   │   │   ├── product_repository.py
│   │   │   └── chat_repository.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # Base クラス
│   │   │   ├── order.py               # 製造データ情報を含む
│   │   │   ├── purchase_order.py
│   │   │   ├── manufacturer.py
│   │   │   ├── shipment.py
│   │   │   ├── product.py
│   │   │   ├── chat_message.py
│   │   │   └── user.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── order.py
│   │   │   ├── purchase_order.py
│   │   │   ├── manufacturer.py
│   │   │   ├── shipment.py
│   │   │   ├── product.py
│   │   │   ├── chat.py
│   │   │   ├── dashboard.py
│   │   │   ├── auth.py
│   │   │   └── common.py              # 共通スキーマ
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── exceptions.py          # カスタム例外
│   │       ├── security.py            # JWT, パスワードハッシュ
│   │       ├── file_storage.py        # ファイル保存
│   │       ├── excel_generator.py     # Excel 生成
│   │       ├── csv_generator.py       # CSV 生成
│   │       ├── zip_builder.py         # ZIP 作成
│   │       └── drive_client.py        # TOSYO DRIVE 連携
│   │
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── alembic.ini
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_orders.py
│   │   ├── test_purchase_orders.py
│   │   └── ...
│   │
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pyproject.toml
│
├── web/
│   └── src/
│       ├── app/
│       │   ├── (auth)/
│       │   │   ├── login/
│       │   │   │   └── page.tsx
│       │   │   └── layout.tsx
│       │   │
│       │   ├── (dashboard)/
│       │   │   ├── page.tsx           # ダッシュボード
│       │   │   ├── orders/
│       │   │   │   ├── page.tsx
│       │   │   │   └── [id]/
│       │   │   │       └── page.tsx
│       │   │   ├── purchase-orders/
│       │   │   │   ├── page.tsx
│       │   │   │   └── [id]/
│       │   │   │       └── page.tsx
│       │   │   ├── manufacturers/
│       │   │   │   ├── page.tsx
│       │   │   │   ├── [id]/
│       │   │   │   │   └── page.tsx
│       │   │   │   └── [id]/chat/
│       │   │   │       └── page.tsx
│       │   │   ├── shipments/
│       │   │   │   ├── page.tsx
│       │   │   │   └── [id]/
│       │   │   │       └── page.tsx
│       │   │   ├── products/
│       │   │   │   ├── page.tsx
│       │   │   │   ├── new/
│       │   │   │   │   └── page.tsx
│       │   │   │   └── [id]/
│       │   │   │       └── page.tsx
│       │   │   └── layout.tsx
│       │   │
│       │   ├── (manufacturer)/
│       │   │   ├── manufacturer-login/
│       │   │   │   └── page.tsx
│       │   │   ├── manufacturer/
│       │   │   │   ├── page.tsx
│       │   │   │   └── [id]/
│       │   │   │       └── page.tsx
│       │   │   └── layout.tsx
│       │   │
│       │   ├── layout.tsx
│       │   └── page.tsx
│       │
│       ├── features/
│       │   ├── orders/
│       │   ├── purchase-orders/
│       │   ├── manufacturers/
│       │   ├── shipments/
│       │   ├── products/
│       │   ├── dashboard/
│       │   └── auth/
│       │
│       ├── components/
│       │   ├── ui/
│       │   ├── layout/
│       │   └── common/
│       │
│       ├── lib/
│       │   ├── api/
│       │   │   ├── client.ts
│       │   │   ├── orders.ts
│       │   │   ├── purchase-orders.ts
│       │   │   ├── manufacturers.ts
│       │   │   ├── shipments.ts
│       │   │   ├── products.ts
│       │   │   └── index.ts
│       │   └── utils/
│       │
│       ├── types/
│       │   ├── api/
│       │   │   └── generated.ts
│       │   └── index.ts
│       │
│       └── styles/
│           └── globals.css
│
└── openapi/
    └── schema.yaml                    # FastAPI から生成
```

---

## Requirements Traceability

| 要件 ID | Backend | Frontend |
|--------|---------|----------|
| 1.1.1-1.1.6 | `routers/orders.py`, `OrderService` | - |
| 1.2.1-1.2.4 | `GET /orders` | `features/orders` |
| 2.1.1-2.1.4 | `routers/purchase_orders.py`, `PurchaseOrderService` | `features/purchase-orders` |
| 2.2.1-2.2.4 | `utils/excel_generator.py`, `utils/zip_builder.py` | - |
| 2.3.1-2.3.5 | `utils/drive_client.py` | - |
| 2.4.1-2.4.4 | `PATCH /purchase-orders/{id}/status` | `features/purchase-orders` |
| 3.1.1-3.1.4 | `routers/manufacturers.py` | `features/manufacturers` |
| 3.2.1-3.2.4 | `routers/chat.py`, `ChatService` | `features/manufacturers` |
| 4.1-4.6 | `routers/manufacturer_portal.py` | `(manufacturer)/` routes |
| 5.1.1-5.1.3 | `routers/shipments.py`, `ShipmentService` | `features/shipments` |
| 5.2.1-5.2.5 | `utils/csv_generator.py` | - |
| 5.3.1-5.3.3 | `POST /shipments/{id}/packing-photo` | `features/shipments` |
| 5.4.1-5.4.4 | `POST /shipments/import-tracking` | `features/shipments` |
| 6.1.1-6.1.5 | `routers/products.py` | `features/products` |
| 7.1.1-7.1.3 | `routers/dashboard.py` | `features/dashboard` |
| 8.1.1-8.1.2 | DB indexing, async processing | Pagination |
| 8.3.1-8.3.3 | `utils/security.py`, API Key auth | Auth middleware |

---

## Security Considerations

### Authentication

1. **管理者認証**
   - JWT ベース認証
   - アクセストークン + リフレッシュトークン

2. **メーカー認証**
   - 専用の JWT 発行
   - メーカー ID に基づくデータアクセス制限

3. **外部 API 認証**
   - API Key 認証（`X-API-Key` ヘッダー）
   - IP ホワイトリスト（オプション）

### Input Validation

- Pydantic スキーマによる厳密なバリデーション
- ファイルアップロード時の MIME タイプ検証
- ファイルサイズ制限（100MB）

---

*Generated: 2025-12-27*
*Updated: 2025-12-27 - 製造データを1受注1ファイルに変更（ManufacturingData テーブル削除、Order テーブルに統合）*
*Based on: requirements.md, steering context, research.md, fastapi-architecture-guide.md*
