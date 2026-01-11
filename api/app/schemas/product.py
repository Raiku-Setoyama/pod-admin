"""Product schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.product import ProductType


class ProductBase(BaseModel):
    """Base product schema."""

    product_type: ProductType
    name: str = Field(..., min_length=1, max_length=200)
    size: str = Field(..., min_length=1, max_length=50)
    color: str | None = Field(None, max_length=50)
    manufacturer_id: str
    cost: int = Field(..., ge=0)
    lead_time_days: int = Field(..., ge=1)
    order_limit: int | None = Field(None, ge=1)


class ProductCreate(ProductBase):
    """Product creation schema."""

    pass


class ProductUpdate(BaseModel):
    """Product update schema."""

    product_type: ProductType | None = None
    name: str | None = Field(None, min_length=1, max_length=200)
    size: str | None = Field(None, min_length=1, max_length=50)
    color: str | None = Field(None, max_length=50)
    manufacturer_id: str | None = None
    cost: int | None = Field(None, ge=0)
    lead_time_days: int | None = Field(None, ge=1)
    order_limit: int | None = Field(None, ge=1)
    is_active: bool | None = None


class ProductResponse(ProductBase):
    """Product response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Product list response schema."""

    items: list[ProductResponse]
    total: int
    page: int
    limit: int
