"""Shipment schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

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
    """Shipment response schema.

    顧客情報は紐づく注文の first_order から取得します。
    """

    id: str
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
