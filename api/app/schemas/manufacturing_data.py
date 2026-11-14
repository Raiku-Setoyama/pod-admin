"""Manufacturing data schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.mfg_product_mapping import LayerType

# DTF 版の白版の種類（生成 app/generator/dtf.py の WhitePlateKind と同じ値。
# あちらは numpy を読み込むので import しない）
WhitePlateKind = Literal["color_only", "white_only", "mixed"]


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
    # 生成の結果の記録（T シャツ・トートの DTF 版だけ。ほかは None。#188）
    # 元画像の実寸解像度（dpi）
    source_dpi: float | None = None
    # 絵柄の幅・高さ（mm。切り抜く前の絵柄の外形）
    art_width_mm: float | None = None
    art_height_mm: float | None = None
    # リブ下から絵柄の最上部まで（mm）
    art_top_below_rib_mm: float | None = None
    # 白版の種類（カラーのみ／ホワイトのみ／混在）
    white_plate: WhitePlateKind | None = None
    created_at: datetime
    updated_at: datetime


class ManufacturingDataOrderItemRef(BaseModel):
    """この製造データを使っている受注明細 1 件（詳細の「使っている注文」）."""

    order_id: str
    order_number: str
    order_status: str
    ordered_at: datetime
    item_id: str
    item_status: str
    product_name: str
    quantity: int


class ManufacturingDataDetailResponse(ManufacturingDataResponse):
    """製造データ詳細レスポンス（元画像レイヤー一覧・使っている明細つき）."""

    source_images: list[SourceImageLayer] = []
    # **製造データは複数の注文で共有される**（受注元 × 商品コード × サイズ × バリアント）。
    # 人気の商品だと件数が膨らむので、新しい注文から上限件数だけ返し、総数を別に返す。
    order_items: list[ManufacturingDataOrderItemRef] = []
    order_items_total: int = 0

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
    # ステータスごとの件数（一覧の絞り込みと同時に全体像を出すため）
    status_counts: dict[str, int] = {}


class ManufacturingDataRetryFailedRequest(BaseModel):
    """失敗した製造データの一括リトライ要求."""

    # 対象の ID。**省略すると failed の全件が対象になる**（生成が止まっていた後の一括復旧）。
    ids: list[str] | None = None


class ManufacturingDataRetryFailedResponse(BaseModel):
    """一括リトライの結果."""

    restored: int
