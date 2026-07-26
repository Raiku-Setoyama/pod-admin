"""Manufacturing data schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.mfg_product_mapping import LayerType


class SourceImageLayer(BaseModel):
    """製造データ1レイヤーの元画像（由来つき）."""

    layer_type: LayerType
    # external: 外部受注が渡した URL / uploaded: 管理画面から差し替えたファイル
    origin: Literal["external", "uploaded"]
    # external のときのみ入る取得元URL
    url: str | None = None
    # uploaded のときのみ入るアップロード時のファイル名
    filename: str | None = None


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
    # 元画像の差し替え履歴（未差し替えなら None）
    source_images_replaced_at: datetime | None = None
    source_images_replaced_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ManufacturingDataDetailResponse(ManufacturingDataResponse):
    """製造データ詳細レスポンス（元画像レイヤー一覧つき）."""

    source_images: list[SourceImageLayer] = []

    @field_validator("source_images", mode="before")
    @classmethod
    def _with_origin(cls, value: Any) -> Any:
        """DB の保存形式（url または file_path）に由来（origin）を付与する.

        レスポンス変換時に再検証されうるため（FastAPI は response_model で dump →
        validate し直す）、origin 付きの入力はそのまま通す。
        """
        if not isinstance(value, list):
            return value
        return [
            {
                "layer_type": img["layer_type"],
                "origin": "uploaded" if img.get("file_path") else "external",
                "url": img.get("url"),
                "filename": img.get("filename"),
            }
            if isinstance(img, dict) and "origin" not in img
            else img
            for img in value
        ]


class ManufacturingDataListResponse(BaseModel):
    """製造データ一覧レスポンス."""

    items: list[ManufacturingDataResponse]
    total: int
    page: int
    limit: int
