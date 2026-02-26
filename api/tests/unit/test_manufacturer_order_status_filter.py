"""ManufacturerOrderService のステータス/検索フィルター機能ユニットテスト

FEAT-0012: 発注詳細画面にステータスフィルター・キーワード検索機能を追加

テスト対象: ManufacturerOrderService.get_order_items_by_manufacturer メソッド
- statusパラメータでステータスフィルタリング
- searchパラメータでキーワード検索（注文番号・製品番号・商品名）
- デフォルトで全ステータス（shipped除く）を返す
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.manufacturer_order_service import ManufacturerOrderService
from app.models.order import OrderStatus
from app.utils.exceptions import NotFoundError


class TestGetOrderItemsByManufacturerStatusFilter:
    """ステータスフィルター機能のユニットテスト"""

    @pytest.fixture
    def mock_order_repo(self):
        """モック OrderRepository"""
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self):
        """モック ManufacturerRepository"""
        return AsyncMock()

    @pytest.fixture
    def mock_shipment_repo(self):
        """モック ShipmentRepository"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_repo, mock_manufacturer_repo, mock_shipment_repo):
        """テスト対象のサービスインスタンス"""
        return ManufacturerOrderService(
            order_repo=mock_order_repo,
            manufacturer_repo=mock_manufacturer_repo,
            shipment_repo=mock_shipment_repo,
        )

    @pytest.fixture
    def mock_manufacturer(self):
        """モックメーカー"""
        manufacturer = MagicMock()
        manufacturer.id = str(uuid4())
        manufacturer.name = "テストメーカー"
        return manufacturer

    @pytest.fixture
    def mock_order_items_multi_status(self):
        """複数ステータスの受注明細

        タプル構造: (OrderItem, order_number, ordered_at, customer_name, cost, item_status, order_status)
        """
        items = []
        statuses = [
            OrderStatus.ORDERED,
            OrderStatus.MANUFACTURING,
            OrderStatus.DELIVERED,
        ]
        for i, status in enumerate(statuses):
            order_item = MagicMock()
            order_item.id = str(uuid4())
            order_item.order_id = str(uuid4())
            order_item.uid = f"UID-{i+1:03d}"
            order_item.product_id = str(uuid4())
            order_item.product_name = f"商品{i+1}"
            order_item.product_type = "tshirt"
            order_item.price = 1000
            order_item.quantity = 1
            order_item.size = "M"
            order_item.position = "正面"
            order_item.color = "白"
            order_item.design_image_url = None
            order_item.thumbnail_image_url = None
            order_item.status = status.value

            items.append((
                order_item,
                f"ORD-{i+1:04d}",  # order_number
                datetime.now(),  # ordered_at
                "顧客名",  # customer_name
                500,  # cost
                status.value,  # item_status (OrderItem.status)
                status.value,  # order_status (Order.status)
            ))
        return items

    @pytest.mark.asyncio
    async def test_get_order_items_passes_status_parameter_to_repository(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
    ):
        """AC-006/AC-014: statusパラメータがリポジトリに渡される

        given: メーカーが存在する
        when: status='manufacturing' で get_order_items_by_manufacturer を呼び出す
        then: リポジトリの find_ordered_items_by_manufacturer_detail に status が渡される
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = []

        await service.get_order_items_by_manufacturer(
            manufacturer_id,
            status="manufacturing",
        )

        # リポジトリが status パラメータ付きで呼ばれたことを確認
        mock_order_repo.find_ordered_items_by_manufacturer_detail.assert_called_once()
        call_kwargs = mock_order_repo.find_ordered_items_by_manufacturer_detail.call_args.kwargs
        assert call_kwargs.get("status") == "manufacturing"

    @pytest.mark.asyncio
    async def test_get_order_items_passes_search_parameter_to_repository(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
    ):
        """AC-002/AC-003/AC-004/AC-013: searchパラメータがリポジトリに渡される

        given: メーカーが存在する
        when: search='ABC' で get_order_items_by_manufacturer を呼び出す
        then: リポジトリの find_ordered_items_by_manufacturer_detail に search が渡される
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = []

        await service.get_order_items_by_manufacturer(
            manufacturer_id,
            search="ABC",
        )

        # リポジトリが search パラメータ付きで呼ばれたことを確認
        mock_order_repo.find_ordered_items_by_manufacturer_detail.assert_called_once()
        call_kwargs = mock_order_repo.find_ordered_items_by_manufacturer_detail.call_args.kwargs
        assert call_kwargs.get("search") == "ABC"

    @pytest.mark.asyncio
    async def test_get_order_items_default_returns_all_statuses_except_shipped(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
    ):
        """AC-007/AC-015: デフォルトでは全ステータス（shipped除く）のアイテムが返される

        given: メーカーが存在する
        when: status パラメータなしで get_order_items_by_manufacturer を呼び出す
        then: リポジトリに status=None が渡される（全ステータス取得）
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = []

        await service.get_order_items_by_manufacturer(manufacturer_id)

        # リポジトリが status=None で呼ばれたことを確認（デフォルト全取得）
        mock_order_repo.find_ordered_items_by_manufacturer_detail.assert_called_once()
        call_kwargs = mock_order_repo.find_ordered_items_by_manufacturer_detail.call_args.kwargs
        # デフォルトでは status を指定しない（None または渡さない）
        assert call_kwargs.get("status") is None

    @pytest.mark.asyncio
    async def test_get_order_items_combines_status_and_search(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
    ):
        """AC-011: 検索とステータスフィルターを組み合わせて使用できる

        given: メーカーが存在する
        when: status='manufacturing' と search='キーホルダー' で呼び出す
        then: 両方のパラメータがリポジトリに渡される
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = []

        await service.get_order_items_by_manufacturer(
            manufacturer_id,
            status="manufacturing",
            search="キーホルダー",
        )

        # リポジトリが両方のパラメータ付きで呼ばれたことを確認
        mock_order_repo.find_ordered_items_by_manufacturer_detail.assert_called_once()
        call_kwargs = mock_order_repo.find_ordered_items_by_manufacturer_detail.call_args.kwargs
        assert call_kwargs.get("status") == "manufacturing"
        assert call_kwargs.get("search") == "キーホルダー"

    @pytest.mark.asyncio
    async def test_get_order_items_response_includes_status_field(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
        mock_order_items_multi_status,
    ):
        """AC-008/AC-016: レスポンスの各アイテムにステータスフィールドが含まれる

        given: 複数ステータスの明細が存在する
        when: get_order_items_by_manufacturer を呼び出す
        then: 各アイテムのレスポンスに status フィールドが含まれる
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = mock_order_items_multi_status

        result = await service.get_order_items_by_manufacturer(manufacturer_id)

        # 各アイテムに status フィールドが含まれることを確認
        assert len(result.items) == 3
        for item in result.items:
            assert hasattr(item, "status")
            assert item.status in ["ordered", "manufacturing", "delivered"]


class TestManufacturerOrderItemResponseSchema:
    """ManufacturerOrderItemResponse スキーマのテスト"""

    def test_schema_has_status_field(self):
        """AC-016: ManufacturerOrderItemResponse に status フィールドがある

        given: ManufacturerOrderItemResponse スキーマ
        when: フィールドを確認する
        then: status フィールドが定義されている
        """
        from app.schemas.manufacturer import ManufacturerOrderItemResponse

        # スキーマのフィールド一覧を取得
        fields = ManufacturerOrderItemResponse.model_fields
        assert "status" in fields, "ManufacturerOrderItemResponse should have 'status' field"

    def test_schema_status_field_type(self):
        """AC-016: status フィールドの型が文字列である

        given: ManufacturerOrderItemResponse スキーマ
        when: status フィールドの型を確認する
        then: str 型として定義されている
        """
        from app.schemas.manufacturer import ManufacturerOrderItemResponse

        fields = ManufacturerOrderItemResponse.model_fields
        status_field = fields.get("status")
        assert status_field is not None
        # フィールドの annotation が str であることを確認
        assert status_field.annotation == str or "str" in str(status_field.annotation)
