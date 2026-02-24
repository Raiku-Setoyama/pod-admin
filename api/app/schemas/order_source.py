"""OrderSource schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderSourceCreate(BaseModel):
    """OrderSource creation schema."""

    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=1, max_length=20)
    postal_code: str = Field(..., min_length=1, max_length=10)
    address_prefecture: str = Field(..., min_length=1, max_length=50)
    address_city: str = Field(..., min_length=1)
    address_building: str | None = Field(None, max_length=200)


class OrderSourceUpdate(BaseModel):
    """OrderSource update schema."""

    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, min_length=1, max_length=20)
    postal_code: str | None = Field(None, min_length=1, max_length=10)
    address_prefecture: str | None = Field(None, min_length=1, max_length=50)
    address_city: str | None = Field(None, min_length=1)
    address_building: str | None = Field(None, max_length=200)
    is_active: bool | None = None


class OrderSourceResponse(BaseModel):
    """OrderSource response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    api_key: str
    phone: str
    postal_code: str
    address_prefecture: str
    address_city: str
    address_building: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OrderSourceListResponse(BaseModel):
    """OrderSource list response schema."""

    items: list[OrderSourceResponse]
    total: int
    page: int
    limit: int
