"""External API schemas for external sales sites."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.order import OrderStatus
from app.models.product import ProductType


class ProductOptionsResponse(BaseModel):
    """Response schema for product options."""

    product_type: ProductType
    size: list[str] = Field(default_factory=list)
    color: list[str] = Field(default_factory=list)
    position: list[str] = Field(default_factory=list)


class PriceCalculationRequest(BaseModel):
    """Request schema for price calculation."""

    product_type: ProductType
    size: str = Field(..., min_length=1, max_length=50)
    color: str | None = Field(None, max_length=50)
    position: str | None = Field(None, max_length=50)
    quantity: int = Field(1, ge=1)


class PriceCalculationResponse(BaseModel):
    """Response schema for price calculation."""

    product_type: ProductType
    size: str
    color: str | None = None
    position: str | None = None
    quantity: int
    unit_price: int
    total_price: int


class OrderStatusShipment(BaseModel):
    """Shipment info in the order status lookup."""

    carrier: str | None = Field(None, description="運送会社名。未登録なら null")
    tracking_number: str = Field(..., description="伝票番号")
    shipped_at: datetime | None = Field(
        None, description="発送日時。伝票番号は登録済みでも未発送なら null"
    )


class OrderStatusResponse(BaseModel):
    """Response schema for order status lookup."""

    order_number: str
    status: OrderStatus
    ordered_at: datetime
    updated_at: datetime
    shipment: OrderStatusShipment | None = Field(
        None,
        description=(
            "配送情報。配送が無い、または伝票番号が未登録なら null。"
            "1 注文に配送が複数あるときは、伝票番号ありのうち発送日時が新しい 1 件"
        ),
    )


class OrderCancelResponse(BaseModel):
    """Response schema for order cancellation."""

    order_number: str
    status: OrderStatus
    cancelled_at: datetime
