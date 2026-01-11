"""Manufacturer schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.product import ProductType


class ManufacturerBase(BaseModel):
    """Base manufacturer schema."""

    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(None, max_length=20)
    supported_products: list[ProductType]
    unit_prices: dict[str, int] = Field(default_factory=dict)
    lead_time_days: int = Field(..., ge=1)
    daily_order_limit: int = Field(..., ge=1)
    sharing_method: Literal["drive", "portal"] = "portal"


class ManufacturerCreate(ManufacturerBase):
    """Manufacturer creation schema."""

    password: str | None = Field(None, min_length=8)  # Required for portal


class ManufacturerUpdate(BaseModel):
    """Manufacturer update schema."""

    name: str | None = Field(None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    supported_products: list[ProductType] | None = None
    unit_prices: dict[str, int] | None = None
    lead_time_days: int | None = Field(None, ge=1)
    daily_order_limit: int | None = Field(None, ge=1)
    sharing_method: Literal["drive", "portal"] | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8)


class ManufacturerResponse(ManufacturerBase):
    """Manufacturer response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ManufacturerListResponse(BaseModel):
    """Manufacturer list response schema."""

    items: list[ManufacturerResponse]
    total: int
    page: int
    limit: int


# === メーカー発注管理用スキーマ ===


class ManufacturerOrderSummary(BaseModel):
    """メーカー別発注サマリー"""

    id: str
    name: str
    email: EmailStr
    phone: str | None
    ordered_item_count: int  # ORDEREDステータスの受注明細数
    total_quantity: int  # 合計数量
    total_amount: int  # 合計金額
    lead_time_days: int
    is_active: bool


class ManufacturerOrderSummaryListResponse(BaseModel):
    """メーカー発注サマリー一覧レスポンス"""

    items: list[ManufacturerOrderSummary]
    total: int
    page: int
    limit: int


class ManufacturerOrderItemResponse(BaseModel):
    """メーカー別受注明細レスポンス"""

    model_config = ConfigDict(from_attributes=True)

    id: str  # OrderItem.id
    order_id: str
    order_number: str
    uid: str | None
    product_id: str
    product_name: str
    product_type: str
    price: int
    quantity: int
    size: str | None
    position: str | None
    color: str | None
    design_image_url: str | None
    thumbnail_image_url: str | None
    ordered_at: datetime
    customer_name: str


class ManufacturerOrderItemListResponse(BaseModel):
    """メーカー別受注明細一覧レスポンス"""

    manufacturer_id: str
    manufacturer_name: str
    items: list[ManufacturerOrderItemResponse]
    total: int
    total_quantity: int
    total_amount: int


class ManufacturerOrderStatusUpdate(BaseModel):
    """メーカー別受注ステータス一括更新"""

    status: Literal["manufacturing", "delivered"]  # MANUFACTURING, DELIVERED
    order_item_ids: list[str] | None = None  # 指定がなければ全てのORDERED明細
    note: str | None = None
