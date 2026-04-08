"""ManufacturerOrderService.get_all_order_items のユニットテスト

FEAT-0018: 全メーカー横断発注明細一覧

テスト対象: get_all_order_items メソッド
- 全メーカーの発注明細を横断的に取得
- manufacturer_id, manufacturer_name が各明細に含まれる
- total, total_quantity, total_amount が正しく集計される
- フィルター（status, search, manufacturer_id）が正しく渡される
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.manufacturer_order_service import ManufacturerOrderService
from app.models.order import OrderStatus


# ---------------------------------------------------------------------------
# Helper: mock order item factory for all-manufacturer queries
# ---------------------------------------------------------------------------

def _make_all_order_item(
    *,
    order_number: str = "POD-20260101-0001",
    uid: str = "abc123",
    product_name: str = "Tシャツ - M - 正面 - 白",
    product_type: str = "tshirt",
    quantity: int = 1,
    price: int = 1000,
    size: str = "M",
    position: str = "正面",
    color: str = "白",
    design_image_url: str | None = None,
    thumbnail_image_url: str | None = None,
    status: str = "ordered",
    cost: int = 500,
    ordered_at: datetime | None = None,
    customer_name: str = "顧客名",
    manufacturer_id: str | None = None,
    manufacturer_name: str = "テストメーカー",
    lead_time_days: int = 7,
) -> tuple:
    """Create a mock order item tuple matching the repository return format
    for find_all_ordered_items_detail."""
    effective_ordered_at = ordered_at or datetime(2026, 2, 24, 10, 0, 0)

    order_item = MagicMock()
    order_item.id = str(uuid4())
    order_item.order_id = str(uuid4())
    order_item.uid = uid
    order_item.product_id = str(uuid4())
    order_item.product_name = product_name
    order_item.product_type = product_type
    order_item.quantity = quantity
    order_item.price = price
    order_item.size = size
    order_item.position = position
    order_item.color = color
    order_item.design_image_url = design_image_url
    order_item.thumbnail_image_url = thumbnail_image_url
    order_item.expected_delivery_date = effective_ordered_at.date() + timedelta(days=lead_time_days)

    mfr_id = manufacturer_id or str(uuid4())

    return (
        order_item,
        order_number,
        effective_ordered_at,
        customer_name,
        cost,
        status,
        mfr_id,
        manufacturer_name,
        lead_time_days,
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestGetAllOrderItems:
    """get_all_order_items メソッドのユニットテスト"""

    @pytest.fixture
    def mock_order_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_shipment_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_repo, mock_manufacturer_repo, mock_shipment_repo):
        return ManufacturerOrderService(
            order_repo=mock_order_repo,
            manufacturer_repo=mock_manufacturer_repo,
            shipment_repo=mock_shipment_repo,
        )

    @pytest.mark.asyncio
    async def test_returns_items_from_multiple_manufacturers(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ):
        """AC-001/AC-005: 複数メーカーの発注明細が全て返される

        given: メーカーAとメーカーBに紐づく発注明細がある
        when: get_all_order_items をフィルターなしで呼び出す
        then: 全メーカーの発注明細が返され、各明細に manufacturer_name が付与される
        """
        mfr_a_id = str(uuid4())
        mfr_b_id = str(uuid4())

        mock_order_repo.find_all_ordered_items_detail.return_value = [
            _make_all_order_item(
                order_number="ORD-001",
                manufacturer_id=mfr_a_id,
                manufacturer_name="メーカーA",
                quantity=2,
                price=1000,
            ),
            _make_all_order_item(
                order_number="ORD-002",
                manufacturer_id=mfr_a_id,
                manufacturer_name="メーカーA",
                quantity=1,
                price=2000,
            ),
            _make_all_order_item(
                order_number="ORD-003",
                manufacturer_id=mfr_b_id,
                manufacturer_name="メーカーB",
                quantity=5,
                price=500,
            ),
        ]

        result = await service.get_all_order_items()

        assert result.total == 3
        assert len(result.items) == 3

        # 各明細に manufacturer_name が含まれる
        names = [item.manufacturer_name for item in result.items]
        assert "メーカーA" in names
        assert "メーカーB" in names

        # 各明細に manufacturer_id が含まれる
        ids = [item.manufacturer_id for item in result.items]
        assert mfr_a_id in ids
        assert mfr_b_id in ids

    @pytest.mark.asyncio
    async def test_correct_total_quantity_and_amount(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ):
        """AC-005: total, total_quantity, total_amount が正しく集計される

        given: 明細3件（数量2*1000, 1*2000, 5*500）
        when: get_all_order_items を呼び出す
        then: total=3, total_quantity=8, total_amount=6500
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = [
            _make_all_order_item(quantity=2, price=1000),
            _make_all_order_item(quantity=1, price=2000),
            _make_all_order_item(quantity=5, price=500),
        ]

        result = await service.get_all_order_items()

        assert result.total == 3
        assert result.total_quantity == 8
        assert result.total_amount == 2000 + 2000 + 2500  # 6500

    @pytest.mark.asyncio
    async def test_empty_result(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ):
        """AC-011: 発注明細が0件の場合、空配列とtotal=0が返される

        given: 発注明細が存在しない
        when: get_all_order_items を呼び出す
        then: items=[], total=0, total_quantity=0, total_amount=0
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = []

        result = await service.get_all_order_items()

        assert result.total == 0
        assert result.items == []
        assert result.total_quantity == 0
        assert result.total_amount == 0

    @pytest.mark.asyncio
    async def test_passes_status_filter_to_repository(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ):
        """AC-002: ステータスフィルターが正しくリポジトリに渡される

        given: status="ordered" でフィルターする
        when: get_all_order_items を status="ordered" で呼び出す
        then: リポジトリに status="ordered" が渡される
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = []

        await service.get_all_order_items(status="ordered")

        mock_order_repo.find_all_ordered_items_detail.assert_called_once_with(
            ordered_from=None,
            ordered_to=None,
            product_type=None,
            status="ordered",
            search=None,
            manufacturer_id=None,
            expected_delivery_from=None,
            expected_delivery_to=None,
        )

    @pytest.mark.asyncio
    async def test_passes_search_filter_to_repository(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ):
        """AC-003: キーワード検索が正しくリポジトリに渡される

        given: search="ORD-001" で検索する
        when: get_all_order_items を search="ORD-001" で呼び出す
        then: リポジトリに search="ORD-001" が渡される
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = []

        await service.get_all_order_items(search="ORD-001")

        mock_order_repo.find_all_ordered_items_detail.assert_called_once_with(
            ordered_from=None,
            ordered_to=None,
            product_type=None,
            status=None,
            search="ORD-001",
            manufacturer_id=None,
            expected_delivery_from=None,
            expected_delivery_to=None,
        )

    @pytest.mark.asyncio
    async def test_passes_manufacturer_id_filter_to_repository(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ):
        """AC-004: メーカーIDフィルターが正しくリポジトリに渡される

        given: manufacturer_id="mfr-001" でフィルターする
        when: get_all_order_items を manufacturer_id="mfr-001" で呼び出す
        then: リポジトリに manufacturer_id="mfr-001" が渡される
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = []

        await service.get_all_order_items(manufacturer_id="mfr-001")

        mock_order_repo.find_all_ordered_items_detail.assert_called_once_with(
            ordered_from=None,
            ordered_to=None,
            product_type=None,
            status=None,
            search=None,
            manufacturer_id="mfr-001",
            expected_delivery_from=None,
            expected_delivery_to=None,
        )

    @pytest.mark.asyncio
    async def test_item_fields_are_correctly_mapped(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ):
        """レスポンスの各フィールドが正しくマッピングされる"""
        mfr_id = str(uuid4())
        mock_order_repo.find_all_ordered_items_detail.return_value = [
            _make_all_order_item(
                order_number="ORD-TEST",
                uid="UID-TEST",
                product_name="テスト商品",
                product_type="acrylic_keychain",
                quantity=3,
                price=800,
                status="manufacturing",
                customer_name="テスト顧客",
                manufacturer_id=mfr_id,
                manufacturer_name="テストメーカー",
            ),
        ]

        result = await service.get_all_order_items()

        assert len(result.items) == 1
        item = result.items[0]
        assert item.order_number == "ORD-TEST"
        assert item.uid == "UID-TEST"
        assert item.product_name == "テスト商品"
        assert item.product_type == "acrylic_keychain"
        assert item.quantity == 3
        assert item.price == 800
        assert item.status == "manufacturing"
        assert item.customer_name == "テスト顧客"
        assert item.manufacturer_id == mfr_id
        assert item.manufacturer_name == "テストメーカー"
