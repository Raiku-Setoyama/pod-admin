"""Company holiday schemas."""

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class CompanyHolidayResponse(BaseModel):
    """Company holiday response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    date: dt.date
    name: str
    created_at: dt.datetime
    updated_at: dt.datetime


class CompanyHolidayCreate(BaseModel):
    """Company holiday creation schema."""

    date: dt.date
    name: str = Field(..., min_length=1, max_length=100)


class CompanyHolidayListResponse(BaseModel):
    """Company holiday list response schema."""

    items: list[CompanyHolidayResponse]
