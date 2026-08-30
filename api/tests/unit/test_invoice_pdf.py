"""発行された請求書PDFそのものを確認するテスト。

BUG-0002 の受入基準は「管理画面・メーカーポータルの双方で PDF が生成される」ことと、
「REQ-0030 の受入基準 3〜5（税率・請求書番号・宛先の書式）が実際の PDF で確認できている」ことである。
PDF が生成できない間はどちらも検証できていなかった。

リポジトリだけをモックし、サービス・テンプレート・PDF 生成は本物を通す。
"""

import re
from collections.abc import Callable, Iterator
from datetime import date
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from pypdf import PdfReader

from app.config import settings
from app.dependencies import (
    get_current_admin,
    get_current_manufacturer,
    get_invoice_service,
)
from app.main import app
from app.models.user import User, UserRole
from app.services.invoice_service import InvoiceService
from app.utils.pdf_generator import generate_invoice_number, get_jinja_env
from tests.unit.invoice_helpers import (
    MANUFACTURER_ID,
    freeze_today,
    make_manufacturer,
    make_order_item,
    make_row,
)

ORDER_ITEM_ID = "item-1"
UNIT_PRICE = 1200
QUANTITY = 3
EXPECTED_SUBTOTAL = 3600
EXPECTED_TAX = 360
EXPECTED_TOTAL = 3960
ISSUE_DATE = date(2026, 8, 30)

# 管理画面とメーカーポータルの 2 経路。どちらも同じ生成処理を通る。
INVOICE_PATHS = [
    f"{settings.API_V1_PREFIX}/manufacturers/{MANUFACTURER_ID}/invoices",
    f"{settings.API_V1_PREFIX}/manufacturer-portal/invoices",
]
INVOICE_PATH_IDS = ["admin", "portal"]

INVOICE_TEMPLATE = get_jinja_env().get_template("invoice.html")


@pytest.fixture
def invoice_endpoints(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """リポジトリと認証だけを差し替え、発行日を固定する。"""
    manufacturer_repo = AsyncMock()
    manufacturer_repo.find_by_id.return_value = make_manufacturer()
    order_repo = AsyncMock()
    order_repo.find_ordered_items_by_manufacturer_detail.return_value = [
        make_row(make_order_item(item_id=ORDER_ITEM_ID, quantity=QUANTITY), cost=UNIT_PRICE)
    ]
    service = InvoiceService(manufacturer_repo, order_repo)

    admin = AsyncMock(spec=User)
    admin.role = UserRole.ADMIN

    freeze_today(monkeypatch, ISSUE_DATE)
    overrides: dict[Callable[..., Any], Callable[..., Any]] = {
        get_invoice_service: lambda: service,
        get_current_admin: lambda: admin,
        get_current_manufacturer: make_manufacturer,
    }
    app.dependency_overrides.update(overrides)
    yield
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def pdf_text(pdf_bytes: bytes) -> str:
    """PDF から抽出したテキストを、空白を落として比較しやすくする。"""
    reader = PdfReader(BytesIO(pdf_bytes))
    return re.sub(r"[\s　]+", "", "".join(page.extract_text() for page in reader.pages))


@pytest.mark.usefixtures("invoice_endpoints")
@pytest.mark.parametrize("path", INVOICE_PATHS, ids=INVOICE_PATH_IDS)
async def test_invoice_pdf_is_generated_and_satisfies_req_0030(
    client: AsyncClient, path: str
) -> None:
    """双方の経路で PDF が返り、その中身が REQ-0030 の受入基準 3〜5 を満たす。"""
    response = await client.post(path, json={"order_item_ids": [ORDER_ITEM_ID]})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response.headers["X-Invoice-Item-Count"] == "1"
    assert response.headers["X-Invoice-Total-Amount"] == str(EXPECTED_TOTAL)

    text = pdf_text(response.content)

    # 受入基準 3: 単価由来の集計 + 消費税 10%（整数切り捨て）
    assert f"¥{EXPECTED_SUBTOTAL:,}" in text
    assert f"¥{EXPECTED_TAX:,}" in text
    assert f"¥{EXPECTED_TOTAL:,}" in text

    # 受入基準 4: 発行日は当日、支払期日は翌月末、請求書番号は INV-YYYYMMDD-{id5}{通番}
    assert "2026年08月30日" in text
    assert "2026年09月30日" in text
    assert generate_invoice_number(MANUFACTURER_ID, ISSUE_DATE) in text
    assert re.search(r"INV-\d{8}-[0-9A-Z]{5}\d{2}", text)

    # 受入基準 5: 宛先は「株式会社TOSYO 御中」固定
    assert "株式会社TOSYO御中" in text


@pytest.mark.parametrize(("item_count", "expected_padding"), [(0, 10), (1, 9), (12, 0)])
def test_detail_table_is_padded_to_ten_rows(item_count: int, expected_padding: int) -> None:
    """REQ-0030 受入基準 5 の後半: 明細は 10 行までパディングして表示される。

    パディング行は空セルなので PDF のテキスト抽出では数えられない。
    PDF の元になる HTML（同じテンプレート）で行数を確認する。
    """
    items: list[dict[str, Any]] = [
        {
            "order_number": f"ORD-{i:04d}",
            "product_name": "オリジナルTシャツ",
            "size": "M",
            "quantity": 1,
            "unit_price": UNIT_PRICE,
            "amount": UNIT_PRICE,
        }
        for i in range(item_count)
    ]

    html = INVOICE_TEMPLATE.render(
        manufacturer=make_manufacturer(),
        items=items,
        invoice_number="INV-20260830-ABCDE01",
        issue_date="2026年08月30日",
        payment_due_date="2026年09月30日",
        subtotal=UNIT_PRICE * item_count,
        tax_amount=int(UNIT_PRICE * item_count * 0.1),
        total_amount=int(UNIT_PRICE * item_count * 1.1),
        total_quantity=item_count,
    )

    assert html.count('<tr class="empty-row">') == expected_padding
    for i in range(item_count):
        assert f"ORD-{i:04d}" in html
