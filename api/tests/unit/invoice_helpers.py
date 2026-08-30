"""請求書まわりのテストで共有するダミーデータ。

BUG-0002 は「リポジトリが返す行の形」と「それを展開する側」がずれた不具合だった。
行の形をテストごとに書き写すと同じずれがテストの中で再発するので、
組み立てはここ 1 か所に置く。
"""

from datetime import date
from typing import Any, Self
from unittest.mock import MagicMock

import pytest

from app.models.manufacturer import Manufacturer
from app.models.order import OrderItem

MANUFACTURER_ID = "abcde123-4567-89ab-cdef-000000000000"

# find_ordered_items_by_manufacturer_detail の SELECT。順番に意味がある（位置で展開するため）。
ORDERED_ITEM_COLUMNS = [
    "OrderItem",
    "Order.order_number",
    "Order.ordered_at",
    "Order.customer_name",
    "Product.cost",
    "OrderItem.status",
    "Order.status",
    "Manufacturer.lead_time_days",
]


def make_order_item(
    item_id: str = "item-1",
    product_name: str = "オリジナルTシャツ",
    size: str | None = "M",
    quantity: int = 3,
) -> Any:
    """OrderItem のモック。"""
    item = MagicMock(spec=OrderItem)
    item.id = item_id
    item.product_name = product_name
    item.size = size
    item.quantity = quantity
    return item


def make_row(
    order_item: Any | None = None,
    order_number: str = "ORD-0001",
    cost: int | None = 1200,
) -> tuple[Any, ...]:
    """`find_ordered_items_by_manufacturer_detail` が返す 1 行と同じ形のタプル。

    要素の順番は `ORDERED_ITEM_COLUMNS` と対応している。
    """
    return (
        order_item if order_item is not None else make_order_item(),
        order_number,
        date(2026, 8, 1),  # ordered_at
        "山田太郎",  # customer_name
        cost,
        "ordered",  # OrderItem.status
        "ordered",  # Order.status
        7,  # lead_time_days
    )


def make_manufacturer() -> Any:
    """請求書に必要な項目を埋めた Manufacturer のモック。"""
    manufacturer = MagicMock(spec=Manufacturer)
    manufacturer.id = MANUFACTURER_ID
    manufacturer.name = "テスト製造株式会社"
    manufacturer.email = "factory@example.com"
    manufacturer.phone = "03-1234-5678"
    manufacturer.postal_code = "100-0001"
    manufacturer.address = "東京都千代田区1-1-1"
    manufacturer.bank_name = "テスト銀行"
    manufacturer.bank_branch = "本店"
    manufacturer.bank_account_type = "普通"
    manufacturer.bank_account_number = "1234567"
    manufacturer.bank_account_holder = "テストセイゾウ"
    manufacturer.representative_name = "代表 太郎"
    manufacturer.invoice_notes = None
    return manufacturer


def freeze_today(monkeypatch: pytest.MonkeyPatch, frozen: date) -> None:
    """請求書サービスから見える `date.today()` を固定する。

    サービスは支払期日の組み立てにも `date(...)` を使うので、`today()` だけを
    差し替えた date のサブクラスを名前ごと置き換える。
    """

    class FixedDate(date):
        @classmethod
        def today(cls) -> Self:
            return cls(frozen.year, frozen.month, frozen.day)

    monkeypatch.setattr("app.services.invoice_service.date", FixedDate)
