"""CSV generation utilities."""

import csv
import io
from datetime import datetime
from typing import Any


class CSVGenerator:
    """CSV file generator."""

    def generate_purchase_order_csv(
        self,
        manufacturer_name: str,
        order_date: datetime,
        items: list[dict[str, Any]],
    ) -> bytes:
        """Generate purchase order CSV file."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["発注先", manufacturer_name])
        writer.writerow(["発注日", order_date.strftime("%Y/%m/%d")])
        writer.writerow([])

        # Column headers
        writer.writerow(["注文番号", "商品名", "サイズ", "数量", "単価"])

        # Data rows
        for item in items:
            writer.writerow([
                item.get("order_number", ""),
                item.get("product_name", ""),
                item.get("size", ""),
                item.get("quantity", 1),
                item.get("price", 0),
            ])

        return output.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility

    def generate_shipping_csv(
        self,
        carrier: str,
        shipments: list[dict[str, Any]],
    ) -> bytes:
        """Generate shipping label CSV for carrier."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Common format for shipping labels
        writer.writerow([
            "お届け先郵便番号",
            "お届け先住所",
            "お届け先名前",
            "お届け先電話番号",
            "品名",
            "個数",
        ])

        for shipment in shipments:
            writer.writerow([
                shipment.get("postal_code", ""),
                shipment.get("address", ""),
                shipment.get("name", ""),
                shipment.get("phone", ""),
                shipment.get("product_name", "グッズ"),
                shipment.get("quantity", 1),
            ])

        return output.getvalue().encode("utf-8-sig")

    def generate_packing_list_csv(
        self,
        order_number: str,
        items: list[dict[str, Any]],
    ) -> bytes:
        """Generate packing list CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["注文番号", order_number])
        writer.writerow([])
        writer.writerow(["商品名", "サイズ", "数量"])

        for item in items:
            writer.writerow([
                item.get("product_name", ""),
                item.get("size", ""),
                item.get("quantity", 1),
            ])

        return output.getvalue().encode("utf-8-sig")
