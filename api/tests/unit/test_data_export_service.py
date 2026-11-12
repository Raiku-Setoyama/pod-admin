"""DataExportService（データ出力タブの CSV）の単体テスト（REQ-0047 / Issue #172）."""

import csv
import io
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.models.order import OrderStatus
from app.models.product import ProductType
from app.schemas.data_export import DataExportCsvRequest, DataExportPreviewRequest
from app.services.data_export_service import (
    COLUMNS_BY_KEY,
    EXPORT_COLUMNS,
    DataExportService,
)
from app.utils.exceptions import ValidationError

# 既存の配送 CSV（POST /shipments/export-csv）の 18 列のヘッダ
EXISTING_18_HEADERS = [
    "注文番号",
    "お客様氏名",
    "商品名",
    "商品種類",
    "数量",
    "商品番号",
    "お届け先電話番号",
    "お届け先郵便番号",
    "お届け先住所1(都道府県)",
    "お届け先住所2(市区町村番地以下)",
    "お届け先住所3(建物名等)",
    "配送元電話番号",
    "配送元郵便番号",
    "配送元住所1(都道府県)",
    "配送元住所2(市区町村番地以下)",
    "配送元住所3(建物名等)",
    "配送元氏名",
    "商品名（処理用）",
]

PERSONAL_INFO_KEYS = [
    "customer_name",
    "customer_email",
    "customer_phone",
    "customer_postal_code",
    "customer_address_prefecture",
    "customer_address_city",
    "customer_address_building",
]


@pytest.fixture
def order_repo() -> Any:
    repo = AsyncMock()
    repo.find_item_rows_for_export.return_value = []
    repo.count_item_rows_for_export.return_value = 0
    return repo


@pytest.fixture
def service(order_repo: Any) -> DataExportService:
    return DataExportService(order_repo)


def _parse(csv_bytes: bytes) -> list[list[str]]:
    assert csv_bytes.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM が付いていない"
    return list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))


class TestColumnCatalog:
    def test_keys_are_unique(self) -> None:
        keys = [c.key for c in EXPORT_COLUMNS]
        assert len(keys) == len(set(keys))

    def test_covers_all_related_areas(self) -> None:
        """受注・顧客・受注元・受注明細・発注・配送・商品マスタの項目が並ぶ（ADR-0023）."""
        groups = {c.group for c in EXPORT_COLUMNS}
        assert groups == {
            "受注",
            "顧客（お届け先）",
            "受注元（配送元）",
            "受注明細",
            "発注",
            "配送",
            "商品マスタ",
        }

    def test_list_columns_returns_catalog_in_order(self, service: DataExportService) -> None:
        response = service.list_columns()
        assert [c.key for c in response.columns] == [c.key for c in EXPORT_COLUMNS]
        assert response.columns[0].label == EXPORT_COLUMNS[0].label

    def test_existing_18_columns_can_be_reproduced(self) -> None:
        """既存 CSV の 18 列は、項目を選べば同じヘッダで再現できる（ADR-0023 / ADR-0024）."""
        labels = {c.label for c in EXPORT_COLUMNS}
        assert set(EXISTING_18_HEADERS) <= labels


class TestExportCsv:
    async def test_only_selected_columns_appear(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        order_repo.find_item_rows_for_export.return_value = [("A-001", 2)]
        request = DataExportCsvRequest(columns=["order_number", "item_quantity"])

        csv_bytes, filename = await service.export_csv(request)

        rows = _parse(csv_bytes)
        assert rows == [["注文番号", "数量"], ["A-001", "2"]]
        assert filename.startswith("データ出力_") and filename.endswith(".csv")
        for key in PERSONAL_INFO_KEYS:
            assert COLUMNS_BY_KEY[key].label not in rows[0]
        # 選んだ項目の式だけを、選んだ順でリポジトリに渡す
        exprs = order_repo.find_item_rows_for_export.call_args.args[0]
        assert exprs == [COLUMNS_BY_KEY["order_number"].expr, COLUMNS_BY_KEY["item_quantity"].expr]

    async def test_column_order_follows_request(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        order_repo.find_item_rows_for_export.return_value = [(2, "A-001")]
        request = DataExportCsvRequest(columns=["item_quantity", "order_number"])

        csv_bytes, _ = await service.export_csv(request)

        assert _parse(csv_bytes) == [["数量", "注文番号"], ["2", "A-001"]]

    async def test_zero_rows_returns_header_only(self, service: DataExportService) -> None:
        request = DataExportCsvRequest(columns=["order_number", "customer_name"])

        csv_bytes, _ = await service.export_csv(request)

        assert _parse(csv_bytes) == [["注文番号", "お客様氏名"]]

    async def test_values_are_formatted(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        order_repo.find_item_rows_for_export.return_value = [
            (
                "manufacturing",
                "tshirt",
                datetime(2026, 11, 1, 15, 30, tzinfo=UTC),
                date(2026, 11, 20),
                True,
                None,
                "pending",
                "unknown_status",
            ),
        ]
        request = DataExportCsvRequest(
            columns=[
                "order_status",
                "item_product_type",
                "ordered_at",
                "estimated_shipping_date",
                "shipment_email_sent",
                "customer_address_building",
                "shipment_status",
                "item_status",
            ]
        )

        csv_bytes, _ = await service.export_csv(request)

        assert _parse(csv_bytes)[1] == [
            "製造中",
            "Tシャツ",
            "2026-11-02 00:30:00",  # 日本時間
            "2026-11-20",
            "はい",
            "",  # NULL は空欄
            "配送準備中",
            "unknown_status",  # 未知のコードはそのまま
        ]

    async def test_passes_filters_and_sort_to_repository(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        request = DataExportCsvRequest.model_validate(
            {
                "columns": ["order_number"],
                "filters": {
                    "status": "ordered",
                    "product_type": "sticker",
                    "ordered_from": "2026-11-01",
                    "ordered_to": "2026-11-30",
                    "shipping_from": "2026-12-01",
                    "shipping_to": "2026-12-31",
                    "search": "山田",
                },
                "sort": {"column": "item_quantity", "direction": "desc"},
            }
        )

        await service.export_csv(request)

        kwargs = order_repo.find_item_rows_for_export.call_args.kwargs
        assert kwargs["status"] == OrderStatus.ORDERED
        assert kwargs["product_type"] == ProductType.STICKER
        assert kwargs["ordered_from"] == date(2026, 11, 1)
        assert kwargs["ordered_to"] == date(2026, 11, 30)
        assert kwargs["shipping_from"] == date(2026, 12, 1)
        assert kwargs["shipping_to"] == date(2026, 12, 31)
        assert kwargs["search"] == "山田"
        assert kwargs["sort"] is COLUMNS_BY_KEY["item_quantity"].expr
        assert kwargs["descending"] is True

    async def test_sort_defaults(self, service: DataExportService, order_repo: Any) -> None:
        await service.export_csv(DataExportCsvRequest(columns=["order_number"]))

        kwargs = order_repo.find_item_rows_for_export.call_args.kwargs
        assert kwargs["sort"] is None
        assert kwargs["descending"] is False

    async def test_sort_by_unselected_column_is_allowed(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        request = DataExportCsvRequest.model_validate(
            {"columns": ["order_number"], "sort": {"column": "ordered_at"}}
        )

        await service.export_csv(request)

        kwargs = order_repo.find_item_rows_for_export.call_args.kwargs
        assert kwargs["sort"] is COLUMNS_BY_KEY["ordered_at"].expr
        assert kwargs["descending"] is False


class TestPreview:
    async def test_returns_formatted_rows_and_total(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        order_repo.find_item_rows_for_export.return_value = [
            ("A-001", "ordered", None),
            ("A-002", "shipped", 3),
        ]
        order_repo.count_item_rows_for_export.return_value = 42
        request = DataExportPreviewRequest(
            columns=["order_number", "order_status", "item_quantity"]
        )

        preview = await service.preview(request)

        assert preview.headers == ["注文番号", "受注ステータス", "数量"]
        # CSV と同じ整形（表示名・NULL は空欄）
        assert preview.rows == [["A-001", "発注済み", ""], ["A-002", "発送完了", "3"]]
        assert preview.total_count == 42
        # 絞り込みなしなら絞り込み前の件数も同じ（数え直さない）
        assert preview.unfiltered_count == 42
        assert order_repo.count_item_rows_for_export.call_count == 1
        # ページ未指定なら 1 ページ目・20 行
        assert (preview.page, preview.limit) == (1, 20)
        find_kwargs = order_repo.find_item_rows_for_export.call_args.kwargs
        assert (find_kwargs["limit"], find_kwargs["offset"]) == (20, 0)

    async def test_pages_rows_and_counts_with_same_filters(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        request = DataExportPreviewRequest.model_validate(
            {
                "columns": ["order_number"],
                "filters": {"status": "ordered", "product_type": "sticker", "search": "山田"},
                "sort": {"column": "item_quantity", "direction": "desc"},
                "page": 3,
                "limit": 5,
            }
        )

        preview = await service.preview(request)

        assert (preview.page, preview.limit) == (3, 5)
        find_kwargs = order_repo.find_item_rows_for_export.call_args.kwargs
        assert find_kwargs["limit"] == 5
        # 3 ページ目は 11 行目から
        assert find_kwargs["offset"] == 10
        assert find_kwargs["sort"] is COLUMNS_BY_KEY["item_quantity"].expr
        assert find_kwargs["descending"] is True
        filtered_call, unfiltered_call = order_repo.count_item_rows_for_export.call_args_list
        assert unfiltered_call.kwargs == {}
        count_kwargs = filtered_call.kwargs
        assert count_kwargs == {
            "status": OrderStatus.ORDERED,
            "product_type": ProductType.STICKER,
            "ordered_from": None,
            "ordered_to": None,
            "search": "山田",
            "shipping_from": None,
            "shipping_to": None,
        }

    async def test_export_csv_is_not_limited(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        await service.export_csv(DataExportCsvRequest(columns=["order_number"]))

        assert "limit" not in order_repo.find_item_rows_for_export.call_args.kwargs

    async def test_unknown_column_rejected(self, service: DataExportService) -> None:
        with pytest.raises(ValidationError):
            await service.preview(DataExportPreviewRequest(columns=["nope"]))

    @pytest.mark.parametrize("page_spec", [{"page": 0}, {"limit": 0}, {"limit": 101}])
    def test_page_out_of_range_rejected_by_schema(self, page_spec: dict[str, int]) -> None:
        with pytest.raises(PydanticValidationError):
            DataExportPreviewRequest.model_validate({"columns": ["order_number"], **page_spec})


class TestValidation:
    def test_empty_columns_rejected_by_schema(self) -> None:
        with pytest.raises(PydanticValidationError):
            DataExportCsvRequest(columns=[])

    async def test_unknown_column_rejected(
        self, service: DataExportService, order_repo: Any
    ) -> None:
        with pytest.raises(ValidationError) as exc:
            await service.export_csv(DataExportCsvRequest(columns=["order_number", "nope"]))
        assert exc.value.errors == {"columns": ["nope"]}
        order_repo.find_item_rows_for_export.assert_not_called()

    async def test_duplicated_column_rejected(self, service: DataExportService) -> None:
        with pytest.raises(ValidationError) as exc:
            await service.export_csv(
                DataExportCsvRequest(columns=["order_number", "order_number"])
            )
        assert exc.value.errors == {"columns": ["order_number"]}

    async def test_unknown_sort_column_rejected(self, service: DataExportService) -> None:
        request = DataExportCsvRequest.model_validate(
            {"columns": ["order_number"], "sort": {"column": "nope"}}
        )
        with pytest.raises(ValidationError):
            await service.export_csv(request)

    def test_unknown_filter_value_rejected_by_schema(self) -> None:
        with pytest.raises(PydanticValidationError):
            DataExportCsvRequest.model_validate(
                {"columns": ["order_number"], "filters": {"status": "pending"}}
            )
