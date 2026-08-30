"""請求書PDF生成サービスの単体テスト。

BUG-0002: `OrderRepository.find_ordered_items_by_manufacturer_detail` が返す行は
8 要素なのに、`InvoiceService._generate_invoice` が 6 要素で展開していたため、
請求書PDFの発行が管理画面・メーカーポータルの双方で 500 になっていた。

ここでは次の 2 つを固定する。

1. リポジトリの SELECT そのもの（`TestOrderedItemRowShape`）
2. その形の行を渡したときにサービスが PDF を返すこと（`TestGenerateInvoiceByItems`）

1 が落ちたら列が変わった合図で、2 が落ちたら展開する側が追随していない合図である。
"""

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.order_repository import OrderRepository
from app.services.invoice_service import InvoiceService
from app.utils.exceptions import NotFoundError, ValidationError
from tests.unit.invoice_helpers import (
    ORDERED_ITEM_COLUMNS,
    freeze_today,
    make_manufacturer,
    make_order_item,
    make_row,
)

UNIT_PRICE = 1200
QUANTITY = 3
EXPECTED_TOTAL = 3960  # 1200 * 3 = 3600 に消費税 10%（切り捨て）360 を足した額


@pytest.fixture
def mock_manufacturer_repo() -> Any:
    repo = AsyncMock()
    repo.find_by_id.return_value = make_manufacturer()
    return repo


@pytest.fixture
def mock_order_repo() -> Any:
    return AsyncMock()


@pytest.fixture
def invoice_service(mock_manufacturer_repo: Any, mock_order_repo: Any) -> InvoiceService:
    return InvoiceService(mock_manufacturer_repo, mock_order_repo)


@pytest.fixture
def stub_pdf(monkeypatch: pytest.MonkeyPatch) -> Any:
    """PDF の中身を見ないテスト向けに、生成そのものを差し替える。

    中身の確認は `test_invoice_pdf.py` が本物の PDF に対して行う。
    """
    stub = MagicMock(return_value=b"%PDF-1.7 stub")
    monkeypatch.setattr("app.services.invoice_service.generate_invoice_pdf", stub)
    return stub


class TestOrderedItemRowShape:
    """リポジトリとその消費側の間にある、暗黙の約束（行の形）を固定する。

    この検索の結果は `InvoiceService` と `ManufacturerOrderService` が位置で展開している。
    BUG-0002 の原因は、列を足したときにその一致が崩れたことだった。
    """

    async def test_select_columns_match_the_documented_row(self) -> None:
        db = MagicMock()
        db.execute = AsyncMock(return_value=MagicMock())
        repo = OrderRepository(db)

        await repo.find_ordered_items_by_manufacturer_detail("mfr-1")

        query = db.execute.await_args_list[0].args[0]
        columns = [
            expr.__name__ if isinstance(expr := column["expr"], type) else str(expr)
            for column in query.column_descriptions
        ]
        assert columns == ORDERED_ITEM_COLUMNS


class TestGenerateInvoiceByItems:
    """BUG-0002 の再現手順（明細を指定して請求書PDFを発行する）を固定する。"""

    async def test_generates_pdf_for_selected_items(
        self, invoice_service: InvoiceService, mock_order_repo: Any
    ) -> None:
        """リポジトリが返す形の行を渡すと、本物の PDF が返る（500 にならない）。"""
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = [
            make_row(make_order_item(quantity=QUANTITY), cost=UNIT_PRICE)
        ]

        pdf_bytes, filename, item_count, total_amount = (
            await invoice_service.generate_invoice_by_items("mfr-1", ["item-1"])
        )

        assert pdf_bytes.startswith(b"%PDF")
        assert filename.endswith(".pdf")
        assert item_count == 1
        assert total_amount == EXPECTED_TOTAL

    @pytest.mark.usefixtures("stub_pdf")
    async def test_filters_rows_by_requested_item_ids(
        self, invoice_service: InvoiceService, mock_order_repo: Any
    ) -> None:
        """指定した明細だけが請求対象になる。"""
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = [
            make_row(make_order_item(item_id="item-1", quantity=2), cost=1000),
            make_row(make_order_item(item_id="item-2", quantity=5), cost=1000),
        ]

        _pdf, _filename, item_count, total_amount = (
            await invoice_service.generate_invoice_by_items("mfr-1", ["item-1"])
        )

        assert item_count == 1
        assert total_amount == 2200

    @pytest.mark.usefixtures("stub_pdf")
    async def test_cost_none_is_treated_as_zero(
        self, invoice_service: InvoiceService, mock_order_repo: Any
    ) -> None:
        """単価が未設定の明細は 0 円として集計する。"""
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = [
            make_row(make_order_item(quantity=4), cost=None)
        ]

        _pdf, _filename, item_count, total_amount = (
            await invoice_service.generate_invoice_by_items("mfr-1", ["item-1"])
        )

        assert item_count == 1
        assert total_amount == 0

    async def test_unknown_manufacturer_raises_not_found(
        self, invoice_service: InvoiceService, mock_manufacturer_repo: Any
    ) -> None:
        mock_manufacturer_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await invoice_service.generate_invoice_by_items("missing", ["item-1"])

    async def test_no_matching_items_raises_validation_error(
        self, invoice_service: InvoiceService, mock_order_repo: Any
    ) -> None:
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = [
            make_row(make_order_item(item_id="item-9"))
        ]

        with pytest.raises(ValidationError):
            await invoice_service.generate_invoice_by_items("mfr-1", ["item-1"])


class TestPaymentDueDate:
    """REQ-0030 受入基準 4: 発行日は当日、支払期日は翌月末。"""

    @pytest.mark.parametrize(
        ("today", "expected_due"),
        [
            (date(2026, 8, 30), date(2026, 9, 30)),
            (date(2026, 1, 31), date(2026, 2, 28)),  # 平年の 2 月
            (date(2028, 1, 15), date(2028, 2, 29)),  # 閏年の 2 月
            (date(2026, 12, 1), date(2027, 1, 31)),  # 年をまたぐ
        ],
    )
    async def test_payment_due_date_is_end_of_next_month(
        self,
        invoice_service: InvoiceService,
        mock_order_repo: Any,
        monkeypatch: pytest.MonkeyPatch,
        stub_pdf: Any,
        today: date,
        expected_due: date,
    ) -> None:
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = [make_row()]
        freeze_today(monkeypatch, today)

        await invoice_service.generate_invoice_by_items("mfr-1", ["item-1"])

        assert stub_pdf.call_args.kwargs["issue_date"] == today
        assert stub_pdf.call_args.kwargs["payment_due_date"] == expected_due
