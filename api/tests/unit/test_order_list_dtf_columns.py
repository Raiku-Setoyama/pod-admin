"""発注リスト（Excel）の DTF の列（印刷方法・印刷位置・白版）のテスト（#189）.

- T シャツ・トートのグループに DTF 版（variant ``dtf``）の明細が 1 件でもあるときだけ、
  「商品種類」の右に 3 列を足す。インクジェット版の明細は空欄。
- 印刷位置は manufacturing_data.art_top_below_rib_mm を 0.1cm 単位に四捨五入（ROUND_HALF_UP）。
- ZIP 内のフォルダ名・ファイル名・シール用テキストは変えない。
"""

import io
import zipfile
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.models.order import OrderItemStatus
from app.services.manufacturer_order_service import ManufacturerOrderService
from app.utils.order_list_generator import (
    OrderListGenerator,
    format_print_position,
    format_white_plate,
)

DTF_HEADERS = [
    "注文日",
    "注文番号",
    "製品番号",
    "商品種類",
    "印刷方法",
    "印刷位置",
    "白版",
    "個数",
    "シール用テキスト情報",
]
INKJET_HEADERS = ["注文日", "注文番号", "製品番号", "商品種類", "個数", "シール用テキスト情報"]


def _sheet(xlsx: bytes) -> Worksheet:
    ws = load_workbook(io.BytesIO(xlsx)).active
    assert isinstance(ws, Worksheet)
    return ws


def _headers(ws: Worksheet) -> list[Any]:
    return [c.value for c in ws[1] if c.value is not None]


def _row(ws: Worksheet, row: int) -> list[Any]:
    return [ws.cell(row=row, column=col).value for col in range(1, ws.max_column + 1)]


def _item(
    *,
    product_type: str = "tshirt",
    size: str = "XL",
    variant: str | None = "dtf",
    top_mm: float | None = 135.5,
    white_plate: str | None = "color_only",
    uid: str = "UID-1",
) -> dict[str, Any]:
    return {
        "ordered_date": datetime(2026, 11, 13, 10, 0, 0),
        "order_number": "ORD-1",
        "uid": uid,
        "product_name": "商品",
        "product_type": product_type,
        "quantity": 2,
        "size": size,
        "position": "正面" if product_type == "tshirt" else None,
        "color": "白",
        "cost": 1000,
        "variant": variant,
        "art_top_below_rib_mm": top_mm,
        "white_plate": white_plate,
    }


class TestFormatPrintPosition:
    @pytest.mark.parametrize(
        ("mm", "expected"),
        [
            (172.4, "リブ下17.2cm"),
            (135.5, "リブ下13.6cm"),  # 偶数丸めなら 13.6 にならないことがある値
            (136.45, "リブ下13.6cm"),
            (116.0, "リブ下11.6cm"),
            (172.25, "リブ下17.2cm"),
            (100.0, "リブ下10.0cm"),
        ],
    )
    def test_rounds_half_up_to_tenth_cm(self, mm: float, expected: str) -> None:
        assert format_print_position("tshirt", mm) == expected

    def test_tote_uses_tote_reference(self) -> None:
        assert format_print_position("tote_bag", 41.0) == "リブ下4.1cm"

    def test_blank_without_value_or_for_non_dtf_product(self) -> None:
        assert format_print_position("tshirt", None) == ""
        assert format_print_position("tshirt", float("nan")) == ""
        assert format_print_position("tshirt", float("inf")) == ""
        assert format_print_position("acrylic_keychain", 50.0) == ""


class TestFormatWhitePlate:
    @pytest.mark.parametrize(
        ("kind", "expected"),
        [
            ("color_only", "カラーのみ（縮小なし）"),
            ("white_only", "ホワイトのみ（縮小なし）"),
            ("mixed", "混在（カラー部分を縮小済み）"),
            (None, ""),
        ],
    )
    def test_labels(self, kind: str | None, expected: str) -> None:
        assert format_white_plate(kind) == expected


class TestGenerateOrderListXlsxDtfColumns:
    @pytest.fixture
    def generator(self) -> OrderListGenerator:
        return OrderListGenerator()

    @pytest.mark.parametrize(
        ("size", "top_mm", "position"),
        [
            ("S", 116.0, "リブ下11.6cm"),
            ("M", 116.4, "リブ下11.6cm"),
            ("L", 136.0, "リブ下13.6cm"),
            ("XL", 135.5, "リブ下13.6cm"),
        ],
    )
    def test_tshirt_dtf_adds_three_columns(
        self, generator: OrderListGenerator, size: str, top_mm: float, position: str
    ) -> None:
        ws = _sheet(
            generator.generate_order_list_xlsx(
                [_item(size=size, top_mm=top_mm, white_plate="mixed")], product_type="tshirt"
            )
        )

        assert _headers(ws) == DTF_HEADERS
        assert _row(ws, 2) == [
            "11月13日",
            "ORD-1",
            "UID-1",
            f"Tシャツ - {size} - 正面 - 白",
            "DTF印刷",
            position,
            "混在（カラー部分を縮小済み）",
            2,
            f"Tシャツ - {size} - 正面 - 白【個数】2個_ORD-1_UID-1_1113",
        ]

    def test_tote_dtf_adds_three_columns(self, generator: OrderListGenerator) -> None:
        ws = _sheet(
            generator.generate_order_list_xlsx(
                [_item(product_type="tote_bag", size="M", top_mm=41.0, white_plate="white_only")],
                product_type="tote_bag",
            )
        )

        assert _headers(ws) == DTF_HEADERS
        assert _row(ws, 2)[3:7] == [
            "トートバッグ - M - 白",
            "DTF印刷",
            "リブ下4.1cm",
            "ホワイトのみ（縮小なし）",
        ]

    def test_mixed_group_leaves_inkjet_rows_blank(self, generator: OrderListGenerator) -> None:
        items = [
            _item(uid="INK-1", variant=None, top_mm=None, white_plate=None),
            _item(uid="DTF-1"),
        ]
        ws = _sheet(generator.generate_order_list_xlsx(items, product_type="tshirt"))

        assert _headers(ws) == DTF_HEADERS
        # 空欄のセルは openpyxl では None として読み戻る
        assert _row(ws, 2)[4:7] == [None, None, None]
        assert _row(ws, 2)[7:] == [2, "Tシャツ - XL - 正面 - 白【個数】2個_ORD-1_INK-1_1113"]
        assert _row(ws, 3)[4:7] == ["DTF印刷", "リブ下13.6cm", "カラーのみ（縮小なし）"]

    def test_inkjet_only_group_keeps_six_columns(self, generator: OrderListGenerator) -> None:
        ws = _sheet(
            generator.generate_order_list_xlsx(
                [_item(variant=None, top_mm=None, white_plate=None)], product_type="tshirt"
            )
        )

        assert _headers(ws) == INKJET_HEADERS
        assert ws.max_column == 6

    def test_non_dtf_product_ignores_dtf_variant(self, generator: OrderListGenerator) -> None:
        """アクリル系は列を増やさない（variant が何であっても）."""
        ws = _sheet(
            generator.generate_order_list_xlsx(
                [_item(product_type="acrylic_keychain", size="50x50 (mm)", variant="dtf")],
                product_type="acrylic_keychain",
            )
        )

        assert _headers(ws) == INKJET_HEADERS

    def test_dtf_columns_share_existing_styles(self, generator: OrderListGenerator) -> None:
        ws = _sheet(generator.generate_order_list_xlsx([_item()], product_type="tshirt"))

        ref_header = ws.cell(row=1, column=1)
        ref_body = ws.cell(row=2, column=2)
        for col in range(1, 10):
            header = ws.cell(row=1, column=col)
            assert header.font.bold == ref_header.font.bold
            assert header.fill.start_color.rgb == ref_header.fill.start_color.rgb
            assert header.alignment.horizontal == "center"
            assert header.border.left.style == "thin"
            assert ws.cell(row=2, column=col).border.bottom.style == ref_body.border.bottom.style
        assert ws.cell(row=2, column=1).number_format == "@"
        widths = [ws.column_dimensions[get_column_letter(col)].width for col in range(1, 10)]
        assert widths == [12, 20, 15, 35, 12, 15, 30, 8, 60]


# ---------------------------------------------------------------------------
# 発注資料 ZIP（ManufacturerOrderService.generate_order_documents）
# ---------------------------------------------------------------------------


def _row_tuple(
    *,
    product_type: str,
    size: str,
    uid: str,
    variant: str | None,
    top_mm: float | None,
    white_plate: str | None,
) -> tuple[Any, ...]:
    """リポジトリの返す行（v2 明細＝生成済みの製造データあり）を作る."""
    md = MagicMock()
    md.file_path = f"mfg/{uid}.pdf"
    md.variant = variant
    md.art_top_below_rib_mm = top_mm
    md.white_plate = white_plate

    order_item = MagicMock()
    order_item.id = str(uuid4())
    order_item.order_id = str(uuid4())
    order_item.uid = uid
    order_item.product_name = "商品"
    order_item.product_type = product_type
    order_item.quantity = 1
    order_item.size = size
    order_item.position = "正面" if product_type == "tshirt" else None
    order_item.color = "白"
    order_item.design_image_url = None
    order_item.thumbnail_image_url = "https://example.com/thumb.png"
    order_item.manufacturing_data_id = str(uuid4())
    order_item.manufacturing_data = md
    order_item.is_manufacturing_ready = True

    status = OrderItemStatus.ORDERED.value
    return (
        order_item,
        "POD-1",
        datetime(2026, 11, 13, 10, 0, 0),
        "顧客名",
        1000,
        status,
        status,
        3,
    )


class TestGenerateOrderDocumentsDtfColumns:
    async def _zip(self, rows: list[tuple[Any, ...]]) -> zipfile.ZipFile:
        order_repo = AsyncMock()
        manufacturer_repo = AsyncMock()
        manufacturer = MagicMock()
        manufacturer.id = "m1"
        manufacturer.name = "テストメーカー"
        manufacturer_repo.find_by_id.return_value = manufacturer
        order_repo.find_ordered_items_by_manufacturer_detail.return_value = rows
        order_repo.update_item_status_by_manufacturer.return_value = ([], set())
        file_storage = AsyncMock()
        file_storage.get.return_value = b"PDF"

        service = ManufacturerOrderService(
            order_repo=order_repo,
            manufacturer_repo=manufacturer_repo,
            shipment_repo=AsyncMock(),
            file_storage=file_storage,
        )
        with (
            patch.object(service, "_download_file", AsyncMock(return_value=(b"PNG", "t.png"))),
            patch("app.services.manufacturer_order_service.datetime") as mock_dt,
        ):
            mock_dt.now.return_value = datetime(2026, 11, 13, 12, 0, 0)
            zip_bytes, _ = await service.generate_order_documents(manufacturer_id="m1")
        return zipfile.ZipFile(io.BytesIO(zip_bytes))

    def _rows(self, *, dtf: bool) -> list[tuple[Any, ...]]:
        variant = "dtf" if dtf else None
        return [
            _row_tuple(
                product_type="tshirt",
                size="L",
                uid="T1",
                variant=variant,
                top_mm=136.0 if dtf else None,
                white_plate="color_only" if dtf else None,
            ),
            _row_tuple(
                product_type="tote_bag",
                size="M",
                uid="B1",
                variant=variant,
                top_mm=41.0 if dtf else None,
                white_plate="mixed" if dtf else None,
            ),
            _row_tuple(
                product_type="acrylic_keychain",
                size="50x50 (mm)",
                uid="K1",
                variant="clear",
                top_mm=None,
                white_plate=None,
            ),
        ]

    @pytest.mark.asyncio
    async def test_order_list_has_dtf_values_from_manufacturing_data(self) -> None:
        zf = await self._zip(self._rows(dtf=True))

        tshirt = _sheet(zf.read("Tシャツ- 正面 -_20261113/Tシャツ- 正面 -_発注リスト_20261113.xlsx"))
        assert _headers(tshirt) == DTF_HEADERS
        assert _row(tshirt, 2)[4:7] == ["DTF印刷", "リブ下13.6cm", "カラーのみ（縮小なし）"]

        tote = _sheet(zf.read("トートバッグ_20261113/トートバッグ_発注リスト_20261113.xlsx"))
        assert _headers(tote) == DTF_HEADERS
        assert _row(tote, 2)[4:7] == ["DTF印刷", "リブ下4.1cm", "混在（カラー部分を縮小済み）"]

        keychain = _sheet(
            zf.read("アクリルキーホルダー_20261113/アクリルキーホルダー_発注リスト_20261113.xlsx")
        )
        assert _headers(keychain) == INKJET_HEADERS

    @pytest.mark.asyncio
    async def test_zip_names_and_seal_text_unchanged_by_dtf(self) -> None:
        dtf = await self._zip(self._rows(dtf=True))
        inkjet = await self._zip(self._rows(dtf=False))

        assert sorted(dtf.namelist()) == sorted(inkjet.namelist())
        path = "Tシャツ- 正面 -_20261113/Tシャツ- 正面 -_発注リスト_20261113.xlsx"
        dtf_ws = _sheet(dtf.read(path))
        inkjet_ws = _sheet(inkjet.read(path))
        # 商品種類・シール用テキストは同じ（DTF は列が 3 つ右にずれる）
        assert _row(dtf_ws, 2)[3] == _row(inkjet_ws, 2)[3]
        assert _row(dtf_ws, 2)[-1] == _row(inkjet_ws, 2)[-1]
