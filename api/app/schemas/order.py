"""Order schemas."""

import datetime as dt
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.models.order import OrderStatus
from app.models.product import ProductType


# Customer info schema
class CustomerInfo(BaseModel):
    """Customer information schema."""

    name: str = Field(..., min_length=1, max_length=100)
    postal_code: str = Field(..., min_length=1, max_length=10)
    address_prefecture: str = Field(..., min_length=1, max_length=50)  # 都道府県（必須）
    address_city: str = Field(..., min_length=1)  # 市区町村以降（必須）
    address_building: str | None = Field(None, max_length=200)  # 建物名等（任意）
    phone: str = Field(..., min_length=1, max_length=20)
    email: EmailStr | None = None


# Order item schemas
class OrderItemCreate(BaseModel):
    """Order item creation schema (from external sales site)."""

    # 製品番号（7桁数字）
    uid: str = Field(
        ...,
        min_length=7,
        max_length=7,
        pattern=r"^\d{7}$",
        description="製品番号（7桁数字）",
        examples=["0000001"],
    )

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


class MfgDataItemInfo(BaseModel):
    """明細に紐づく製造データの状態（v2）."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str  # pending | generating | ready | failed
    output_filename: str | None = None
    file_size: int | None = None
    error_message: str | None = None


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
    expected_delivery_date: date | None = None  # メーカーからの納品予定日
    # v2（製造データ生成）用フィールド
    product_code: str | None = None
    manufacturing_data: MfgDataItemInfo | None = None
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

    order_number: str = Field(
        ...,
        min_length=7,
        max_length=7,
        pattern=r"^\d{7}$",
        description="受注番号（7桁数字）",
        examples=["0000001"],
    )
    customer: CustomerInfo
    items: list[OrderItemCreate] = Field(..., min_length=1)


# === v2: 製造データ生成用（元データ = PNGレイヤーURL を受け取る） ===
class SourceImage(BaseModel):
    """製造データ生成の元データ（レイヤーPNGのURL）."""

    layer_type: Literal["color", "cutline", "white", "design"]
    url: str = Field(..., min_length=1, max_length=2048)


class OrderItemCreateV2(BaseModel):
    """Order item creation schema (v2 / 製造データ生成)."""

    uid: str = Field(
        ...,
        min_length=7,
        max_length=7,
        pattern=r"^\d{7}$",
        description="製品番号（7桁数字）",
        examples=["0000001"],
    )
    product_type: ProductType
    product_name: str = Field(..., min_length=1, max_length=200)
    price: int = Field(..., ge=0)
    quantity: int = Field(1, ge=1)
    size: str | None = Field(None, max_length=50)
    position: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=50)
    # rksyo の商品識別子（製造データキャッシュキー）
    product_code: str = Field(..., min_length=1, max_length=255)
    # 製造データ生成に必要な元データ（color / cutline / white / design）
    source_images: list[SourceImage] = Field(..., min_length=1)
    # サムネイル用途（従来通り受理）
    thumbnail_image_url: str | None = Field(None, max_length=2048)


class OrderCreateV2(BaseModel):
    """Order creation schema (v2 / 製造データ生成)."""

    order_number: str = Field(
        ...,
        min_length=7,
        max_length=7,
        pattern=r"^\d{7}$",
        description="受注番号（7桁数字）",
        examples=["0000001"],
    )
    customer: CustomerInfo
    items: list[OrderItemCreateV2] = Field(..., min_length=1)


# Order shipment info schema
class OrderShipmentInfo(BaseModel):
    """Shipment info embedded in order response."""

    id: str
    status: str  # "pending" | "ready" | "shipped"
    tracking_number: str | None = None
    carrier: str | None = None


# Order response schema
class OrderResponse(BaseModel):
    """Order response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_number: str
    status: OrderStatus
    source: str | None = None  # Derived from order_source.code
    order_source_id: str | None = None
    customer_name: str
    customer_postal_code: str
    customer_address_prefecture: str
    customer_address_city: str
    customer_address_building: str | None = None
    customer_phone: str
    customer_email: str | None = None
    ordered_at: datetime
    total_price: int
    estimated_shipping_date: dt.date | None = None
    items: list[OrderItemResponse] = []
    shipment: OrderShipmentInfo | None = None
    # Legacy fields (for backward compatibility)
    product_id: str | None = None
    product_name: str | None = None
    price: int | None = None
    quantity: int | None = None
    manufacturing_data: ManufacturingDataInfo | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def customer_full_address(self) -> str:
        """結合された完全な住所."""
        parts = [
            self.customer_address_prefecture,
            self.customer_address_city,
            self.customer_address_building,
        ]
        return "".join(p for p in parts if p)


class OrderListResponse(BaseModel):
    """Order list response schema."""

    items: list[OrderResponse]
    total: int
    page: int
    limit: int


class OrderStatusUpdate(BaseModel):
    """Order status update schema."""

    status: OrderStatus


class OrderBulkStatusUpdate(BaseModel):
    """受注ステータス一括更新スキーマ"""

    order_ids: list[str] = Field(..., min_length=1)
    status: OrderStatus


class OrderBulkStatusUpdateResponse(BaseModel):
    """受注ステータス一括更新レスポンス"""

    updated_count: int
    failed_count: int
    failed_ids: list[str]


class OrderImageDownloadRequest(BaseModel):
    """受注イメージ画像ZIPダウンロードリクエスト"""

    order_ids: list[str] = Field(..., min_length=1)


class OrderExportCsvRequest(BaseModel):
    """受注CSVエクスポートリクエスト（pending_order向け）"""

    order_ids: list[str] = Field(..., min_length=1)


class OrderThumbnailDownloadRequest(BaseModel):
    """受注サムネイル画像ZIPダウンロードリクエスト"""

    order_ids: list[str] = Field(..., min_length=1)
