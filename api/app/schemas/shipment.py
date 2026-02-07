"""Shipment schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.shipment import ShipmentStatus


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


class ShipmentResponse(BaseModel):
    """Shipment response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    status: ShipmentStatus
    tracking_number: str | None
    carrier: str | None
    packing_photo_path: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    note: str | None
    customer_name: str
    customer_postal_code: str
    customer_address: str
    customer_phone: str
    items: list[ShipmentItemResponse]
    created_at: datetime
    updated_at: datetime


class ShipmentListResponse(BaseModel):
    """Shipment list response schema."""

    items: list[ShipmentResponse]
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
