"""Order list CSV/Excel generation utilities for manufacturer ordering."""

import csv
import io
import math
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.utils.mfg_product_mapping import DTF_PRODUCT_TYPES, VARIANT_DTF

# Product type to Japanese name mapping
PRODUCT_TYPE_NAMES: dict[str, str] = {
    "acrylic_keychain": "アクリルキーホルダー",
    "acrylic_stand": "アクリルフィギュア",
    "sticker": "ステッカー",
    "tote_bag": "トートバッグ",
    "mug": "マグカップ",
    "tshirt": "Tシャツ",
}


# DTF 版（T シャツ・トート）の発注リストに足す列の値（#189）。
# メーカーは発注リストに書かれた位置をもとに製造側で位置合わせをする。
PRINT_METHOD_DTF = "DTF印刷"
# 印刷位置の基準の呼び方（「{基準}{n}cm」の {基準}）。
# トートは取引先が呼び方を確認中（当社案＝メーカー回答と同じ「リブ下」）。確定したらここを変える。
PRINT_POSITION_REFERENCE: dict[str, str] = {
    "tshirt": "リブ下",
    "tote_bag": "リブ下",
}
# 白版の種類（manufacturing_data.white_plate。値は生成 app/generator/dtf.py の WhitePlateKind）
WHITE_PLATE_LABELS: dict[str, str] = {
    "color_only": "カラーのみ（縮小なし）",
    "white_only": "ホワイトのみ（縮小なし）",
    "mixed": "混在（カラー部分を縮小済み）",
}


def get_product_type_name(product_type: str) -> str:
    """Get Japanese name for product type."""
    return PRODUCT_TYPE_NAMES.get(product_type, product_type)


def format_product_detail(
    product_type: str,
    size: str | None = None,
    position: str | None = None,
    color: str | None = None,
) -> str:
    """Build the product detail string: {商品種類} - {サイズ} - {位置} - {色}.

    Elements without a value (size / position / color が null/空) are skipped so
    no extra separators appear. The product type name is resolved via
    get_product_type_name (e.g. acrylic_stand -> アクリルフィギュア).

    Examples:
        Tシャツ - L - 正面 - 白
        ステッカー - 100x100mm - ホワイト  (position 無し)
    """
    detail_parts = [get_product_type_name(product_type)]
    if size:
        detail_parts.append(size)
    if position:
        detail_parts.append(position)
    if color:
        detail_parts.append(color)
    return " - ".join(detail_parts)


def format_print_position(product_type: str, top_below_rib_mm: float | None) -> str:
    """リブ下から絵柄の最上部まで（mm）を発注リストの印刷位置（例: ``リブ下13.6cm``）にする.

    0.1cm 単位に四捨五入する（組み込みの ``round`` は偶数丸めで 13.55 が 13.6 にならないことが
    あるので ``Decimal`` の ``ROUND_HALF_UP``）。値が無いとき・DTF 版の無い商品は空文字。
    """
    reference = PRINT_POSITION_REFERENCE.get(product_type)
    if top_below_rib_mm is None or reference is None or not math.isfinite(top_below_rib_mm):
        return ""
    # float の 2 進誤差を持ち込まないよう、10 進の文字列を経由する
    cm = (Decimal(str(top_below_rib_mm)) / 10).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{reference}{cm}cm"


def format_white_plate(white_plate: str | None) -> str:
    """白版の種類（color_only / white_only / mixed）を発注リストの表示にする。値が無ければ空文字."""
    if not white_plate:
        return ""
    return WHITE_PLATE_LABELS.get(white_plate, white_plate)


def is_dtf_item(item: dict[str, Any], product_type: str | None = None) -> bool:
    """発注リストの明細が T シャツ・トートの DTF 版の製造データを持つか."""
    item_product_type = product_type or item.get("product_type", "")
    return item_product_type in DTF_PRODUCT_TYPES and item.get("variant") == VARIANT_DTF


class OrderListGenerator:
    """CSV generator for manufacturer order lists (発注リスト)."""

    def generate_order_list_csv(
        self,
        items: list[dict[str, Any]],
        product_type: str | None = None,
    ) -> bytes:
        """Generate order list CSV for a manufacturer.

        CSV Format:
        - 注文日: MM月DD日 形式
        - 注文番号: Order.order_number
        - 製品番号: OrderItem.uid
        - 商品名: OrderItem.product_name
        - 商品種類: {商品種類} - {サイズ} - {位置} - {色} (ex. Tシャツ - XL - 正面 - 白)
        - 原価: Product.cost
        - 個数: OrderItem.quantity
        - シール用テキスト情報: {商品名}【個数】{個数}個_{注文番号}_{製品番号}_{MMDD}

        Args:
            items: List of dicts containing order item data with keys:
                - ordered_date: datetime
                - order_number: str
                - uid: str
                - product_name: str
                - product_type: str (optional, used if product_type arg is None)
                - quantity: int
                - size: str | None
                - position: str | None
                - color: str | None
                - cost: int
            product_type: Product type code (e.g., "tshirt"). If None, uses
                          each item's product_type field.

        Returns:
            CSV content as bytes (UTF-8 with BOM for Excel compatibility).
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Column headers
        writer.writerow([
            "注文日",
            "注文番号",
            "製品番号",
            "商品名",
            "商品種類",
            "原価",
            "個数",
            "シール用テキスト情報",
        ])

        # Data rows
        for item in items:
            ordered_date: datetime | None = item.get("ordered_date")
            order_number = item.get("order_number", "")
            uid = item.get("uid", "")
            product_name = item.get("product_name", "")
            quantity = item.get("quantity", 1)
            size = item.get("size", "")
            position = item.get("position", "")
            color = item.get("color", "")
            cost = item.get("cost", 0)

            # Get product type (use argument if provided, else from item)
            item_product_type = product_type or item.get("product_type", "")

            # Format date as "MM月DD日"
            formatted_date = ordered_date.strftime("%m月%d日") if ordered_date else ""
            mmdd = ordered_date.strftime("%m%d") if ordered_date else ""

            # Build product detail: {商品種類} - {サイズ} - {位置} - {色}
            product_detail = format_product_detail(
                item_product_type, size, position, color
            )

            # Build seal text: {商品種類}【個数】{個数}個_{注文番号}_{製品番号}_{MMDD}
            seal_text = f"{product_detail}【個数】{quantity}個_{order_number}_{uid}_{mmdd}"

            writer.writerow([
                formatted_date,
                order_number,
                uid,
                product_name,
                product_detail,
                cost,
                quantity,
                seal_text,
            ])

        return output.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility

    def generate_order_list_xlsx(
        self,
        items: list[dict[str, Any]],
        product_type: str | None = None,
    ) -> bytes:
        """Generate order list Excel file for a manufacturer.

        Excel Format (6 columns, excludes 商品名 and 原価):
        - 注文日: M月D日 形式（ゼロ詰めなし、文字列形式）
        - 注文番号: Order.order_number
        - 製品番号: OrderItem.uid
        - 商品種類: {商品種類} - {サイズ} - {位置} - {色}
        - 個数: OrderItem.quantity
        - シール用テキスト情報: {商品名}【個数】{個数}個_{注文番号}_{製品番号}_{MMDD}

        T シャツ・トートで DTF 版の製造データ（variant ``dtf``）の明細が 1 件でもあるときだけ、
        「商品種類」の右に 3 列を足す（#189。インクジェット版の明細は 3 列とも空欄）:
        - 印刷方法: ``DTF印刷``
        - 印刷位置: ``リブ下13.6cm``（manufacturing_data.art_top_below_rib_mm を 0.1cm 単位に四捨五入）
        - 白版: ``カラーのみ（縮小なし）`` など（manufacturing_data.white_plate）

        Args:
            items: List of dicts containing order item data. DTF の列には次のキーを使う
                （無ければインクジェット版として扱う）:
                - variant: str | None（manufacturing_data.variant）
                - art_top_below_rib_mm: float | None
                - white_plate: str | None
            product_type: Product type code (e.g., "tshirt")

        Returns:
            Excel file content as bytes (.xlsx format).
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "発注リスト"

        # Styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(
            start_color="4472C4", end_color="4472C4", fill_type="solid"
        )
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        dtf_flags = [is_dtf_item(item, product_type) for item in items]
        with_dtf_columns = any(dtf_flags)

        # Column headers (6 columns, excluding 商品名 and 原価; DTF のときは 9 列)
        headers = ["注文日", "注文番号", "製品番号", "商品種類"]
        column_widths = [12, 20, 15, 35]
        if with_dtf_columns:
            headers += ["印刷方法", "印刷位置", "白版"]
            column_widths += [12, 15, 30]
        headers += ["個数", "シール用テキスト情報"]
        column_widths += [8, 60]

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center")

        # Data rows
        for row_idx, (item, is_dtf) in enumerate(zip(items, dtf_flags, strict=True), 2):
            ordered_date: datetime | None = item.get("ordered_date")
            order_number = item.get("order_number", "")
            uid = item.get("uid", "")
            quantity = item.get("quantity", 1)
            size = item.get("size", "")
            position = item.get("position", "")
            color = item.get("color", "")

            # Get product type (use argument if provided, else from item)
            item_product_type = product_type or item.get("product_type", "")

            # Format date as "M月D日" (no zero-padding)
            if ordered_date:
                formatted_date = f"{ordered_date.month}月{ordered_date.day}日"
                mmdd = ordered_date.strftime("%m%d")
            else:
                formatted_date = ""
                mmdd = ""

            # Build product detail: {商品種類} - {サイズ} - {位置} - {色}
            product_detail = format_product_detail(
                item_product_type, size, position, color
            )

            # Build seal text: {商品種類}【個数】{個数}個_{注文番号}_{製品番号}_{MMDD}
            seal_text = f"{product_detail}【個数】{quantity}個_{order_number}_{uid}_{mmdd}"

            values: list[Any] = [formatted_date, order_number, uid, product_detail]
            if with_dtf_columns:
                if is_dtf:
                    values += [
                        PRINT_METHOD_DTF,
                        format_print_position(
                            item_product_type, item.get("art_top_below_rib_mm")
                        ),
                        format_white_plate(item.get("white_plate")),
                    ]
                else:
                    # 同じグループのインクジェット版の明細は空欄
                    values += ["", "", ""]
            values += [quantity, seal_text]

            for col, value in enumerate(values, 1):
                ws.cell(row=row_idx, column=col, value=value).border = thin_border

            # Column 1: 注文日 (as text string)
            ws.cell(row=row_idx, column=1).number_format = "@"  # Text format

        # Adjust column widths
        for col, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width

        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()
