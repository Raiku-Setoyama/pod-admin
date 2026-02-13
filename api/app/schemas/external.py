"""External API schemas for external sales sites."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.order import OrderStatus, TshirtColor, TshirtPosition, TshirtSize
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


class OrderStatusResponse(BaseModel):
    """Response schema for order status lookup."""

    order_number: str
    status: OrderStatus
    ordered_at: datetime
    updated_at: datetime
