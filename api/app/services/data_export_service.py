"""データ出力（任意項目の CSV 出力）サービス.

REQ-0047 / ADR-0023: 出力の 1 行は受注明細 1 件。その明細が属する受注・顧客・受注元・
配送・発注・商品マスタの項目を、同じ行の列として選べる。

**項目の定義（キー・表示名・値の取り出し方・並べ替えの式）はこのファイルの
``EXPORT_COLUMNS`` だけが持つ。** 画面は ``GET /data-export/columns`` で一覧を受け取り、
自前で項目を持たない。

既存の固定 18 列 CSV（``POST /orders/export-csv`` / ``POST /shipments/export-csv``）は
配送業者向けの取り込みフォーマットであり、ここからは触らない（ADR-0024）。
重なる項目の表示名は既存 CSV のヘッダに揃えてあり、項目を選べば 18 列を再現できる。
"""

import csv
import io
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, func
from sqlalchemy.orm import QueryableAttribute

from app.models.manufacturer import Manufacturer
from app.models.manufacturing_data import ManufacturingData
from app.models.order import Order, OrderItem
from app.models.order_source import OrderSource
from app.models.product import Product
from app.models.shipment import Shipment
from app.repositories.order_repository import OrderRepository
from app.schemas.data_export import (
    DataExportColumnResponse,
    DataExportColumnsResponse,
    DataExportCsvRequest,
    SortDirection,
)
from app.utils.exceptions import ValidationError

JST = ZoneInfo("Asia/Tokyo")

# ---- 値の整形 ----
# CSV には文字列しか書けないので、型ごとに Excel で読みやすい形へ整える。
# NULL はすべて空欄にする。

Formatter = Callable[[Any], str]


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _date(value: Any) -> str:
    return value.isoformat() if isinstance(value, date) else _text(value)


def _datetime(value: Any) -> str:
    # 画面・メールと同じく日本時間で出す
    if isinstance(value, datetime):
        return value.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S")
    return _text(value)


def _bool(value: Any) -> str:
    if value is None:
        return ""
    return "はい" if value else "いいえ"


def _labels(mapping: Mapping[str, str]) -> Formatter:
    """コード値を表示名にする（未知の値はコードのまま出す）."""

    def fmt(value: Any) -> str:
        if value is None:
            return ""
        return mapping.get(str(value), str(value))

    return fmt


# 表示名は管理画面（web/src/constants/status.ts）に揃える
ORDER_STATUS_LABELS = {
    "preparing_order": "発注準備中",
    "ordered": "発注済み",
    "manufacturing": "製造中",
    "delivered": "納品済み",
    "shipped": "発送完了",
    "cancelled": "キャンセル済み",
}
SHIPMENT_STATUS_LABELS = {
    "pending": "配送準備中",
    "ready": "配送準備完了",
    "shipped": "発送完了",
}
MFG_DATA_STATUS_LABELS = {
    "pending": "生成待ち",
    "generating": "生成中",
    "ready": "完成",
    "failed": "生成失敗",
}
# 既存の受注 CSV（OrderService._format_product_type）と同じ表記
PRODUCT_TYPE_LABELS = {
    "acrylic_keychain": "アクリルキーホルダー",
    "acrylic_stand": "アクリルスタンド",
    "sticker": "ステッカー",
    "tote_bag": "トートバッグ",
    "tshirt": "Tシャツ",
}


# ---- 項目の定義 ----

ColumnExpr = QueryableAttribute[Any] | ColumnElement[Any]


@dataclass(frozen=True)
class ExportColumn:
    """列にできる項目 1 つ.

    ``expr`` は SELECT と ORDER BY の両方に使う。並べ替えは DB 上の値で行うので、
    ステータスなど表示名に変換する項目はコード値の順に並ぶ。
    """

    key: str
    label: str
    group: str
    expr: ColumnExpr
    format: Formatter = _text


GROUP_ORDER = "受注"
GROUP_CUSTOMER = "顧客（お届け先）"
GROUP_SOURCE = "受注元（配送元）"
GROUP_ITEM = "受注明細"
GROUP_PURCHASE = "発注"
GROUP_SHIPMENT = "配送"
GROUP_PRODUCT = "商品マスタ"

EXPORT_COLUMNS: tuple[ExportColumn, ...] = (
    # 受注
    ExportColumn("order_id", "受注ID", GROUP_ORDER, Order.id),
    ExportColumn("order_number", "注文番号", GROUP_ORDER, Order.order_number),
    ExportColumn(
        "order_status", "受注ステータス", GROUP_ORDER, Order.status,
        _labels(ORDER_STATUS_LABELS),
    ),
    ExportColumn("ordered_at", "受注日時", GROUP_ORDER, Order.ordered_at, _datetime),
    ExportColumn(
        "estimated_shipping_date", "配送予定日", GROUP_ORDER,
        Order.estimated_shipping_date, _date,
    ),
    ExportColumn("total_price", "合計金額", GROUP_ORDER, Order.total_price),
    # 顧客（お届け先）— 表示名は既存の配送 CSV のヘッダに揃える
    ExportColumn("customer_name", "お客様氏名", GROUP_CUSTOMER, Order.customer_name),
    ExportColumn(
        "customer_email", "お客様メールアドレス", GROUP_CUSTOMER, Order.customer_email
    ),
    ExportColumn("customer_phone", "お届け先電話番号", GROUP_CUSTOMER, Order.customer_phone),
    ExportColumn(
        "customer_postal_code", "お届け先郵便番号", GROUP_CUSTOMER, Order.customer_postal_code
    ),
    ExportColumn(
        "customer_address_prefecture", "お届け先住所1(都道府県)", GROUP_CUSTOMER,
        Order.customer_address_prefecture,
    ),
    ExportColumn(
        "customer_address_city", "お届け先住所2(市区町村番地以下)", GROUP_CUSTOMER,
        Order.customer_address_city,
    ),
    ExportColumn(
        "customer_address_building", "お届け先住所3(建物名等)", GROUP_CUSTOMER,
        Order.customer_address_building,
    ),
    # 受注元（配送元）
    ExportColumn("order_source_code", "受注元コード", GROUP_SOURCE, OrderSource.code),
    ExportColumn("order_source_name", "配送元氏名", GROUP_SOURCE, OrderSource.name),
    ExportColumn("order_source_phone", "配送元電話番号", GROUP_SOURCE, OrderSource.phone),
    ExportColumn(
        "order_source_postal_code", "配送元郵便番号", GROUP_SOURCE, OrderSource.postal_code
    ),
    ExportColumn(
        "order_source_address_prefecture", "配送元住所1(都道府県)", GROUP_SOURCE,
        OrderSource.address_prefecture,
    ),
    ExportColumn(
        "order_source_address_city", "配送元住所2(市区町村番地以下)", GROUP_SOURCE,
        OrderSource.address_city,
    ),
    ExportColumn(
        "order_source_address_building", "配送元住所3(建物名等)", GROUP_SOURCE,
        OrderSource.address_building,
    ),
    # 受注明細
    ExportColumn("item_id", "明細ID", GROUP_ITEM, OrderItem.id),
    ExportColumn("item_uid", "商品番号", GROUP_ITEM, OrderItem.uid),
    ExportColumn("item_product_name", "商品名", GROUP_ITEM, OrderItem.product_name),
    ExportColumn(
        "item_product_type", "商品種類", GROUP_ITEM, OrderItem.product_type,
        _labels(PRODUCT_TYPE_LABELS),
    ),
    ExportColumn("item_size", "サイズ", GROUP_ITEM, OrderItem.size),
    ExportColumn("item_position", "プリント位置", GROUP_ITEM, OrderItem.position),
    ExportColumn("item_color", "カラー", GROUP_ITEM, OrderItem.color),
    ExportColumn("item_price", "単価", GROUP_ITEM, OrderItem.price),
    ExportColumn("item_quantity", "数量", GROUP_ITEM, OrderItem.quantity),
    ExportColumn("item_product_code", "商品コード", GROUP_ITEM, OrderItem.product_code),
    ExportColumn(
        "item_design_image_url", "デザイン画像URL", GROUP_ITEM, OrderItem.design_image_url
    ),
    ExportColumn(
        "item_thumbnail_image_url", "サムネイル画像URL", GROUP_ITEM,
        OrderItem.thumbnail_image_url,
    ),
    # 既存 CSV の 18 列目と同じ値（{注文番号}_{商品番号}）。ADR-0024 により隠さない。
    ExportColumn(
        "item_processing_name", "商品名（処理用）", GROUP_ITEM,
        func.concat(Order.order_number, "_", func.coalesce(OrderItem.uid, "")),
    ),
    # 発注（メーカーは明細 → 商品マスタ → メーカーで引く）
    ExportColumn(
        "item_status", "発注ステータス", GROUP_PURCHASE, OrderItem.status,
        _labels(ORDER_STATUS_LABELS),
    ),
    ExportColumn("manufacturer_name", "メーカー名", GROUP_PURCHASE, Manufacturer.name),
    ExportColumn(
        "manufacturer_email", "メーカーメールアドレス", GROUP_PURCHASE, Manufacturer.email
    ),
    ExportColumn("manufacturer_phone", "メーカー電話番号", GROUP_PURCHASE, Manufacturer.phone),
    ExportColumn(
        "expected_delivery_date", "納品予定日", GROUP_PURCHASE,
        OrderItem.expected_delivery_date, _date,
    ),
    ExportColumn(
        "manufacturer_notified_at", "発注通知日時", GROUP_PURCHASE,
        OrderItem.manufacturer_notified_at, _datetime,
    ),
    ExportColumn(
        "manufacturing_data_status", "製造データステータス", GROUP_PURCHASE,
        ManufacturingData.status, _labels(MFG_DATA_STATUS_LABELS),
    ),
    ExportColumn(
        "manufacturing_data_filename", "製造データファイル名", GROUP_PURCHASE,
        ManufacturingData.output_filename,
    ),
    # 配送（配送は受注単位。同じ受注の明細には同じ値が並ぶ）
    ExportColumn(
        "shipment_status", "配送ステータス", GROUP_SHIPMENT, Shipment.status,
        _labels(SHIPMENT_STATUS_LABELS),
    ),
    ExportColumn("shipment_carrier", "配送業者", GROUP_SHIPMENT, Shipment.carrier),
    ExportColumn(
        "shipment_tracking_number", "追跡番号", GROUP_SHIPMENT, Shipment.tracking_number
    ),
    ExportColumn(
        "shipment_shipped_at", "発送日時", GROUP_SHIPMENT, Shipment.shipped_at, _datetime
    ),
    ExportColumn(
        "shipment_delivered_at", "配達完了日時", GROUP_SHIPMENT, Shipment.delivered_at,
        _datetime,
    ),
    ExportColumn(
        "shipment_email_sent", "発送通知メール送信済み", GROUP_SHIPMENT,
        Shipment.shipping_email_sent, _bool,
    ),
    ExportColumn("shipment_note", "配送メモ", GROUP_SHIPMENT, Shipment.note),
    # 商品マスタ
    ExportColumn("product_cost", "原価", GROUP_PRODUCT, Product.cost),
    ExportColumn(
        "product_lead_time_days", "リードタイム（日）", GROUP_PRODUCT, Product.lead_time_days
    ),
    ExportColumn("product_order_limit", "発注上限", GROUP_PRODUCT, Product.order_limit),
    ExportColumn(
        "product_is_active", "商品マスタ有効", GROUP_PRODUCT, Product.is_active, _bool
    ),
)

COLUMNS_BY_KEY: dict[str, ExportColumn] = {c.key: c for c in EXPORT_COLUMNS}


class DataExportService:
    """データ出力タブの CSV を組み立てる."""

    def __init__(self, order_repo: OrderRepository):
        self._order_repo = order_repo

    def list_columns(self) -> DataExportColumnsResponse:
        """列にできる項目の一覧を返す."""
        return DataExportColumnsResponse(
            columns=[
                DataExportColumnResponse(key=c.key, label=c.label, group=c.group)
                for c in EXPORT_COLUMNS
            ]
        )

    async def export_csv(self, request: DataExportCsvRequest) -> tuple[bytes, str]:
        """選ばれた項目だけを列にした CSV（UTF-8 BOM 付き）とファイル名を返す.

        0 件のときはヘッダ行だけを返す（エラーにしない）。

        Raises:
            ValidationError: 未知の項目キー・重複した項目・未知の並べ替えキーが含まれる場合。
        """
        columns = self._resolve_columns(request.columns)

        sort_expr: ColumnExpr | None = None
        descending = False
        if request.sort is not None:
            sort_column = COLUMNS_BY_KEY.get(request.sort.column)
            if sort_column is None:
                raise ValidationError(
                    "並べ替えの項目が不正です",
                    {"sort.column": [request.sort.column]},
                )
            sort_expr = sort_column.expr
            descending = request.sort.direction == SortDirection.DESC

        filters = request.filters
        rows = await self._order_repo.find_item_rows_for_export(
            [c.expr for c in columns],
            status=filters.status,
            product_type=filters.product_type,
            ordered_from=filters.ordered_from,
            ordered_to=filters.ordered_to,
            search=filters.search,
            shipping_from=filters.shipping_from,
            shipping_to=filters.shipping_to,
            sort=sort_expr,
            descending=descending,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([c.label for c in columns])
        for row in rows:
            writer.writerow([c.format(value) for c, value in zip(columns, row, strict=True)])

        # Excel で文字化けしないよう BOM を付ける（既存の CSV 出力と同じ扱い）
        csv_bytes = output.getvalue().encode("utf-8-sig")
        timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        return csv_bytes, f"データ出力_{timestamp}.csv"

    @staticmethod
    def _resolve_columns(keys: list[str]) -> list[ExportColumn]:
        # 0 個はスキーマ（min_length=1）で 422 にしている
        unknown = [k for k in keys if k not in COLUMNS_BY_KEY]
        if unknown:
            raise ValidationError("出力する項目に不正なキーが含まれています", {"columns": unknown})
        duplicated = sorted(k for k, n in Counter(keys).items() if n > 1)
        if duplicated:
            raise ValidationError("出力する項目が重複しています", {"columns": duplicated})
        return [COLUMNS_BY_KEY[k] for k in keys]
