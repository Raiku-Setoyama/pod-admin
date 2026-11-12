"""データ出力（任意項目の CSV 出力）のスキーマ.

出力の 1 行は受注明細 1 件（ADR-0023）。列にできる項目の一覧は
``GET /data-export/columns`` が返し、``POST /data-export/csv`` は
その中から選んだ項目のキーを受け取る。
"""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

from app.models.order import OrderStatus
from app.models.product import ProductType


class DataExportColumnResponse(BaseModel):
    """列にできる項目 1 つ."""

    key: str = Field(..., description="項目のキー（出力リクエストで指定する値）")
    label: str = Field(..., description="CSV のヘッダに出す表示名")
    group: str = Field(..., description="項目の分類（受注・顧客・配送など）")


class DataExportColumnsResponse(BaseModel):
    """列にできる項目の一覧（画面に並べる順）."""

    columns: list[DataExportColumnResponse]


class DataExportFilters(BaseModel):
    """出力対象の絞り込み条件（受注一覧の絞り込みに揃える）."""

    status: OrderStatus | None = Field(None, description="受注ステータス")
    product_type: ProductType | None = Field(None, description="明細の商品種別")
    ordered_from: date | None = Field(None, description="受注日（開始）")
    ordered_to: date | None = Field(None, description="受注日（終了）")
    shipping_from: date | None = Field(None, description="配送予定日（開始）")
    shipping_to: date | None = Field(None, description="配送予定日（終了）")
    search: str | None = Field(None, description="キーワード（注文番号／顧客名の部分一致）")


class SortDirection(str, Enum):
    """並べ替えの向き."""

    ASC = "asc"
    DESC = "desc"


class DataExportSort(BaseModel):
    """並べ替えの指定."""

    column: str = Field(..., description="並べ替えに使う項目のキー")
    direction: SortDirection = SortDirection.ASC


class DataExportCsvRequest(BaseModel):
    """データ出力（CSV）のリクエスト."""

    columns: list[str] = Field(
        ...,
        min_length=1,
        description="出力する項目のキー（この順で列になる）。1 つ以上必須",
    )
    filters: DataExportFilters = Field(default_factory=DataExportFilters)
    sort: DataExportSort | None = Field(
        None, description="並べ替え。省略時は受注日時の新しい順"
    )


class DataExportPreviewResponse(BaseModel):
    """出力内容のプレビュー（CSV と同じ列・同じ整形で先頭の数行）."""

    headers: list[str] = Field(..., description="列の表示名（CSV のヘッダ行と同じ）")
    rows: list[list[str]] = Field(..., description="先頭から最大 limit 行の値（CSV と同じ整形）")
    total_count: int = Field(..., description="絞り込みに当てはまる行（受注明細）の総数")
    unfiltered_count: int = Field(
        ..., description="絞り込みをかけない場合の行（受注明細）の総数"
    )
