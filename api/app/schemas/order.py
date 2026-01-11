"""Order schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.order import OrderStatus
from app.models.product import ProductType


# Customer info schema
class CustomerInfo(BaseModel):
    """Customer information schema."""

    name: str = Field(..., min_length=1, max_length=100)
    postal_code: str = Field(..., min_length=1, max_length=10)
    address: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1, max_length=20)
    email: EmailStr | None = None


# Order item schemas
class OrderItemCreate(BaseModel):
    """Order item creation schema (from external sales site)."""

    # 外部販売サイトのオリジナル商品ID
    uid: str = Field(..., min_length=1, max_length=100)

    # 製造種類（商品タイプ）
    product_type: ProductType

    # 外部販売サイトの商品名
    product_name: str = Field(..., min_length=1, max_length=200)

    price: int = Field(..., ge=0)
    quantity: int = Field(1, ge=1)
    size: str | None = Field(None, max_length=50)
    position: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=50)
    design_image_url: str | None = Field(None, max_length=2048)
    thumbnail_image_url: str | None = Field(None, max_length=2048)


class OrderItemResponse(BaseModel):
    """Order item response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    uid: str  # 外部販売サイトのオリジナル商品ID
    product_name: str
    product_type: str  # 製造種類
    price: int
    quantity: int
    size: str | None = None
    position: str | None = None
    color: str | None = None
    design_image_url: str | None = None
    thumbnail_image_url: str | None = None
    created_at: datetime
    updated_at: datetime


# Legacy manufacturing data info (for backward compatibility)
class ManufacturingDataInfo(BaseModel):
    """Manufacturing data information (deprecated)."""

    filename: str | None = None
    path: str | None = None
    size: int | None = None
    download_url: str | None = None


# Order create schema (new format with items)
class OrderCreate(BaseModel):
    """Order creation schema (from external sales site)."""

    order_number: str = Field(..., min_length=1, max_length=50)
    ordered_at: datetime
    customer: CustomerInfo
    items: list[OrderItemCreate] = Field(..., min_length=1)


# Order response schema
class OrderResponse(BaseModel):
    """Order response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_number: str
    status: OrderStatus
    customer_name: str
    customer_postal_code: str
    customer_address: str
    customer_phone: str
    customer_email: str | None = None
    ordered_at: datetime
    total_price: int
    items: list[OrderItemResponse] = []
    # Legacy fields (for backward compatibility)
    product_id: str | None = None
    product_name: str | None = None
    price: int | None = None
    quantity: int | None = None
    manufacturing_data: ManufacturingDataInfo | None = None
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    """Order list response schema."""

    items: list[OrderResponse]
    total: int
    page: int
    limit: int


class OrderStatusUpdate(BaseModel):
    """Order status update schema."""

    status: OrderStatus
