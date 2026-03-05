"""Shipment schemas."""

from datetime import datetime
from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.shipment import ShipmentStatus


class PendingOrderStatus(str, Enum):
    """Pending order status - derived from OrderItem statuses."""

    PREPARING = "preparing"  # 商品準備中（全OrderItemがDELIVEREDでない）
    AWAITING_SHIPMENT = "awaiting_shipment"  # 配送準備待ち（全OrderItemがDELIVERED）


class OrderItemSummary(BaseModel):
    """Order item summary for PendingOrderResponse."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    product_name: str
    product_type: str
    quantity: int
    status: str
    thumbnail_image_url: str | None = None


class PendingOrderResponse(BaseModel):
    """Pending order response schema - orders without shipments.

    Represents orders that don't have a Shipment yet.
    Status is derived from OrderItem statuses.
    """

    model_config = ConfigDict(from_attributes=True)

    type: Literal["pending_order"] = "pending_order"
    order_id: str
    order_number: str
    customer_name: str
    customer_address: str
    item_count: int
    items_delivered: int
    status: PendingOrderStatus
    created_at: datetime
    order_items: list[OrderItemSummary] = []


class ShipmentCreate(BaseModel):
    """Shipment creation schema."""

    order_ids: list[str] = Field(..., min_length=1)


class ShipmentStatusUpdate(BaseModel):
    """Shipment status update schema."""

    status: ShipmentStatus
    tracking_number: str | None = None
    carrier: str | None = None
    note: str | None = None
    delivered_at: datetime | None = None  # 配送完了予定日時


class TrackingImportItem(BaseModel):
    """Tracking number import item."""

    shipment_id: str
    tracking_number: str
    carrier: str | None = None


class TrackingImportRequest(BaseModel):
    """Tracking number import request."""

    items: list[TrackingImportItem]


class ShipmentItemResponse(BaseModel):
    """Shipment item response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    order_number: str | None = None
    product_name: str | None = None
    quantity: int | None = None
    thumbnail_image_url: str | None = None


class ShipmentResponse(BaseModel):
    """Shipment response schema.

    顧客情報は紐づく注文の first_order から取得します。
    """

    id: str
    type: Literal["shipment"] = "shipment"
    status: ShipmentStatus
    tracking_number: str | None
    carrier: str | None
    packing_photo_path: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    note: str | None
    # Customer info (populated from first order)
    customer_name: str
    customer_postal_code: str
    customer_address_prefecture: str
    customer_address_city: str
    customer_address_building: str | None = None
    customer_phone: str
    items: list[ShipmentItemResponse]
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


class ShipmentListResponse(BaseModel):
    """Shipment list response schema."""

    items: list[ShipmentResponse]
    total: int
    page: int
    limit: int


# Union type for mixed list items
ShipmentOrPendingOrder = Union[ShipmentResponse, PendingOrderResponse]


class ShipmentListWithPendingResponse(BaseModel):
    """Shipment list response with pending orders.

    Contains both shipments and pending orders in a single list.
    Use the 'type' field to distinguish between them.
    """

    items: list[ShipmentOrPendingOrder]
    total: int
    page: int
    limit: int


class ShipmentBulkStatusUpdate(BaseModel):
    """配送ステータス一括更新スキーマ"""

    shipment_ids: list[str] = Field(..., min_length=1)
    status: ShipmentStatus
    tracking_number: str | None = None
    carrier: str | None = None


class ShipmentBulkStatusUpdateResponse(BaseModel):
    """配送ステータス一括更新レスポンス"""

    updated_count: int
    failed_count: int
    failed_ids: list[str]


class ShipmentExportRequest(BaseModel):
    """配送CSVエクスポートリクエスト"""

    shipment_ids: list[str] = Field(..., min_length=1)


class ShipmentThumbnailDownloadRequest(BaseModel):
    """配送サムネイル画像ZIPダウンロードリクエスト"""

    shipment_ids: list[str] = Field(..., min_length=1)


class TrackingFileImportError(BaseModel):
    """伝票番号ファイルインポートのエラー詳細"""

    row: int
    order_number: str | None = None
    message: str


class TrackingFileImportResult(BaseModel):
    """伝票番号ファイルインポートの結果"""

    total_count: int
    success_count: int
    error_count: int
    errors: list[TrackingFileImportError]
    updated_shipments: list[ShipmentResponse] = []
