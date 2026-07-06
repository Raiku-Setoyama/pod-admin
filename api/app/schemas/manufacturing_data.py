"""Manufacturing data response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ManufacturingDataResponse(BaseModel):
    """製造データ生成キャッシュ行のレスポンス."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_source_id: str
    product_code: str
    product_type: str
    size: str
    variant: str | None
    status: str
    vm_job_id: str | None
    output_filename: str | None
    file_path: str | None
    file_size: int | None
    error_message: str | None
    attempts: int
    created_at: datetime
    updated_at: datetime


class ManufacturingDataListResponse(BaseModel):
    """製造データ一覧レスポンス."""

    items: list[ManufacturingDataResponse]
    total: int
