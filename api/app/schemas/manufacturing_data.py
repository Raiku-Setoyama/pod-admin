"""Manufacturing data schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ManufacturingDataResponse(BaseModel):
    """製造データレスポンス."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_source_id: str | None = None
    product_code: str
    product_type: str
    size: str | None = None
    variant: str | None = None
    status: str  # pending | generating | ready | failed
    vm_job_id: str | None = None
    output_filename: str | None = None
    file_size: int | None = None
    error_message: str | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime


class ManufacturingDataListResponse(BaseModel):
    """製造データ一覧レスポンス."""

    items: list[ManufacturingDataResponse]
    total: int
    page: int
    limit: int
