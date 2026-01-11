"""Order list CSV generation utilities for manufacturer ordering."""

import csv
import io
from datetime import datetime

# Product type to Japanese name mapping
PRODUCT_TYPE_NAMES: dict[str, str] = {
    "acrylic_keychain": "アクリルキーホルダー",
    "acrylic_stand": "アクリルスタンド",
    "sticker": "ステッカー",
    "mug": "マグカップ",
    "tshirt": "Tシャツ",
}


def get_product_type_name(product_type: str) -> str:
    """Get Japanese name for product type."""
    return PRODUCT_TYPE_NAMES.get(product_type, product_type)


class OrderListGenerator:
    """CSV generator for manufacturer order lists (発注リスト)."""

    def generate_order_list_csv(
        self,
        items: list[dict],
    ) -> bytes:
        """Generate order list CSV for a manufacturer.

        CSV Format:
        - 注文日: MM月DD日 形式
        - 注文番号: Order.order_number
        - 製品番号: OrderItem.uid
        - 商品名: OrderItem.product_name
        - 個数: OrderItem.quantity
        - シール用テキスト情報: {商品名}【個数】{個数}個_{注文番号}_{製品番号}_{MMDD}

        Args:
            items: List of dicts containing order item data with keys:
                - ordered_date: datetime
                - order_number: str
                - uid: str
                - product_name: str
                - quantity: int

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

            # Format date as "MM月DD日"
            formatted_date = ordered_date.strftime("%m月%d日") if ordered_date else ""
            mmdd = ordered_date.strftime("%m%d") if ordered_date else ""

            # Build seal text: {商品名}【個数】{個数}個_{注文番号}_{製品番号}_{MMDD}
            seal_text = f"{product_name}【個数】{quantity}個_{order_number}_{uid}_{mmdd}"

            writer.writerow([
                formatted_date,
                order_number,
                uid,
                product_name,
                quantity,
                seal_text,
            ])

        return output.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility
