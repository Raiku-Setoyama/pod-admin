"""Settings schemas."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ShippingPreparationDaysResponse(BaseModel):
    """Response for shipping preparation days setting."""

    value: int
    description: str | None = None


class ShippingPreparationDaysUpdate(BaseModel):
    """Request to update shipping preparation days."""

    value: int = Field(..., ge=0, le=30, description="発送準備日数（0〜30日）")


class CompanyHolidayResponse(BaseModel):
    """Response for a company holiday."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    date: date
    name: str


class CompanyHolidayCreate(BaseModel):
    """Request to create a company holiday."""

    date: date
    name: str = Field(..., min_length=1, max_length=100)


class CompanyHolidayListResponse(BaseModel):
    """Response for company holiday list."""

    items: list[CompanyHolidayResponse]
