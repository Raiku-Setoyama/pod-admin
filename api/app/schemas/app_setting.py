"""App setting schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppSettingResponse(BaseModel):
    """App setting response schema."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    description: str | None = None
    updated_at: datetime


class AppSettingUpdate(BaseModel):
    """App setting update schema."""

    value: str = Field(..., min_length=1, max_length=500)


class AppSettingListResponse(BaseModel):
    """App setting list response schema."""

    items: list[AppSettingResponse]
