"""Product attribute schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductAttributeOptionCreate(BaseModel):
    """Schema for creating an attribute option."""

    product_type: str = Field(..., min_length=1, max_length=50)
    attribute_name: str = Field(..., pattern=r"^(size|color|position)$")
    attribute_value: str = Field(..., min_length=1, max_length=50)
    display_order: int = Field(0, ge=0)


class ProductAttributeOptionUpdate(BaseModel):
    """Schema for updating an attribute option."""

    attribute_value: str | None = Field(None, min_length=1, max_length=50)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ProductAttributeOptionResponse(BaseModel):
    """Response schema for an attribute option."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    product_type: str
    attribute_name: str
    attribute_value: str
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductAttributeRequirementResponse(BaseModel):
    """Response schema for attribute requirements."""

    model_config = ConfigDict(from_attributes=True)

    product_type: str
    required_size: bool
    required_color: bool
    required_position: bool


class ProductAttributeRequirementUpdate(BaseModel):
    """Schema for updating attribute requirements."""

    required_size: bool | None = None
    required_color: bool | None = None
    required_position: bool | None = None


class ProductAttributeSpecResponse(BaseModel):
    """Combined response: options + requirements for a product type."""

    product_type: str
    sizes: list[str]
    colors: list[str]
    positions: list[str]
    required_size: bool
    required_color: bool
    required_position: bool
