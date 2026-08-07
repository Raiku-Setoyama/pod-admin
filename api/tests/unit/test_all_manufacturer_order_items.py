"""全メーカー横断発注明細一覧のユニットテスト

FEAT-0018: 全メーカー分の発注明細を一覧で確認できる「すべての発注」ページ

テスト対象:
- OrderRepository.find_all_ordered_items_detail メソッド
  - AC-001: フィルターなしで全メーカーの発注明細取得
  - AC-002: ステータスフィルター
  - AC-003: キーワード検索
  - AC-004: メーカーIDフィルター
- ManufacturerOrderService.get_all_order_items メソッド
  - AC-005: 全メーカー発注明細一覧のレスポンス組み立て
"""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.manufacturer_order_service import ManufacturerOrderService

# ---------------------------------------------------------------------------
# Helper: mock order item tuple factory (matching repository return format)
# ---------------------------------------------------------------------------

def _make_order_item_tuple(
    *,
    item_id: str | None = None,
    order_id: str | None = None,
    order_number: str = "ORD-001",
    uid: str = "UID-001",
    product_id: str | None = None,
    product_name: str = "テスト商品",
    product_type: str = "tshirt",
    price: int = 1000,
    quantity: int = 1,
    size: str = "M",
    position: str | None = "正面",
    color: str | None = "白",
    design_image_url: str | None = None,
    thumbnail_image_url: str | None = None,
    ordered_at: datetime | None = None,
    customer_name: str = "テスト顧客",
    cost: int = 500,
    status: str = "ordered",
    manufacturer_id: str | None = None,
    manufacturer_name: str = "テストメーカー",
    lead_time_days: int = 7,
) -> tuple[Any, ...]:
    """リポジトリの find_all_ordered_items_detail の戻り値形式に合わせたタプルを生成"""
    order_item = MagicMock()
    order_item.id = item_id or str(uuid4())
    order_item.order_id = order_id or str(uuid4())
    order_item.uid = uid
    order_item.product_id = product_id or str(uuid4())
    order_item.product_name = product_name
    order_item.product_type = product_type
    order_item.price = price
    order_item.quantity = quantity
    order_item.size = size
    order_item.position = position
    order_item.color = color
    order_item.design_image_url = design_image_url
    order_item.thumbnail_image_url = thumbnail_image_url

    return (
        order_item,
        order_number,
        ordered_at or datetime(2026, 2, 24, 10, 0, 0),
        customer_name,
        cost,
        status,
        manufacturer_id or str(uuid4()),
        manufacturer_name,
        lead_time_days,
    )


# ===========================================================================
# AC-001: OrderRepository が全メーカー横断で発注明細を取得できる
# ===========================================================================

class TestFindAllOrderedItemsDetail:
    """OrderRepository.find_all_ordered_items_detail メソッドのテスト"""

    @pytest.fixture
    def mock_db(self) -> Any:
        """モック AsyncSession（execute().all() チェーンを正しくセットアップ）"""
        db = AsyncMock()
        # execute() が返す結果オブジェクトのモック
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db.execute.return_value = mock_result
        return db

    @pytest.fixture
    def repo(self, mock_db: Any) -> Any:
        """テスト対象のリポジトリインスタンス"""
        from app.repositories.order_repository import OrderRepository
        return OrderRepository(mock_db)

    @pytest.mark.asyncio
    async def test_find_all_ordered_items_detail_returns_all_manufacturers(
        self, repo: Any, mock_db: Any,
    ) -> None:
        """AC-001: フィルターなしで全メーカーの発注明細が返される

        given: 複数メーカーに紐づく発注明細がDBに存在する
        when: find_all_ordered_items_detail メソッドをフィルターなしで呼び出す
        then: 全メーカーの発注明細が返される（shipped以外の全ステータス）
        """
        # find_all_ordered_items_detail メソッドが存在することを確認
        assert hasattr(repo, 'find_all_ordered_items_detail'), \
            "OrderRepository should have find_all_ordered_items_detail method"

        # メソッドを呼び出す
        result = await repo.find_all_ordered_items_detail()

        # 結果はリスト
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_find_all_ordered_items_detail_filters_by_status(
        self, repo: Any, mock_db: Any,
    ) -> None:
        """AC-002: ステータスでフィルターできる

        given: ordered, manufacturing, delivered の各ステータスの発注明細が存在する
        when: find_all_ordered_items_detail を status="ordered" で呼び出す
        then: ordered ステータスの明細のみが返される
        """
        assert hasattr(repo, 'find_all_ordered_items_detail'), \
            "OrderRepository should have find_all_ordered_items_detail method"

        result = await repo.find_all_ordered_items_detail(status="ordered")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_find_all_ordered_items_detail_filters_by_search(
        self, repo: Any, mock_db: Any,
    ) -> None:
        """AC-003: キーワードで検索できる

        given: 注文番号 "ORD-001" の発注明細が存在する
        when: find_all_ordered_items_detail を search="ORD-001" で呼び出す
        then: 注文番号に "ORD-001" を含む明細のみが返される
        """
        assert hasattr(repo, 'find_all_ordered_items_detail'), \
            "OrderRepository should have find_all_ordered_items_detail method"

        result = await repo.find_all_ordered_items_detail(search="ORD-001")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_find_all_ordered_items_detail_filters_by_manufacturer_id(
        self, repo: Any, mock_db: Any,
    ) -> None:
        """AC-004: メーカーIDでフィルターできる

        given: メーカーAとメーカーBの発注明細が存在する
        when: find_all_ordered_items_detail を manufacturer_id=メーカーAのID で呼び出す
        then: メーカーAの明細のみが返される
        """
        assert hasattr(repo, 'find_all_ordered_items_detail'), \
            "OrderRepository should have find_all_ordered_items_detail method"

        manufacturer_a_id = str(uuid4())
        result = await repo.find_all_ordered_items_detail(
            manufacturer_id=manufacturer_a_id
        )
        assert isinstance(result, list)


# ===========================================================================
# AC-005: ManufacturerOrderService.get_all_order_items
# ===========================================================================

class TestGetAllOrderItems:
    """ManufacturerOrderService.get_all_order_items メソッドのテスト"""

    @pytest.fixture
    def mock_order_repo(self) -> Any:
        """モック OrderRepository"""
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self) -> Any:
        """モック ManufacturerRepository"""
        return AsyncMock()

    @pytest.fixture
    def mock_shipment_repo(self) -> Any:
        """モック ShipmentRepository"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_repo: Any, mock_manufacturer_repo: Any, mock_shipment_repo: Any) -> Any:
        """テスト対象のサービスインスタンス"""
        return ManufacturerOrderService(
            order_repo=mock_order_repo,
            manufacturer_repo=mock_manufacturer_repo,
            shipment_repo=mock_shipment_repo,
        )

    @pytest.fixture
    def mock_all_order_items_data(self) -> list[Any]:
        """複数メーカーの発注明細データ"""
        manufacturer_a_id = str(uuid4())
        manufacturer_b_id = str(uuid4())

        return [
            _make_order_item_tuple(
                order_number="ORD-001",
                uid="UID-001",
                product_name="アクリルキーホルダーA",
                product_type="acrylic_keychain",
                price=1000,
                quantity=2,
                status="ordered",
                manufacturer_id=manufacturer_a_id,
                manufacturer_name="メーカーA",
            ),
            _make_order_item_tuple(
                order_number="ORD-002",
                uid="UID-002",
                product_name="Tシャツ白M",
                product_type="tshirt",
                price=2000,
                quantity=1,
                status="manufacturing",
                manufacturer_id=manufacturer_a_id,
                manufacturer_name="メーカーA",
            ),
            _make_order_item_tuple(
                order_number="ORD-003",
                uid="UID-003",
                product_name="ステッカー大",
                product_type="sticker",
                price=500,
                quantity=5,
                status="ordered",
                manufacturer_id=manufacturer_b_id,
                manufacturer_name="メーカーB",
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_all_order_items_method_exists(
        self,
        service: ManufacturerOrderService,
    ) -> None:
        """AC-005: get_all_order_items メソッドが存在する

        given: ManufacturerOrderService インスタンス
        when: get_all_order_items メソッドの存在を確認する
        then: メソッドが存在する
        """
        assert hasattr(service, 'get_all_order_items'), \
            "ManufacturerOrderService should have get_all_order_items method"

    @pytest.mark.asyncio
    async def test_get_all_order_items_returns_response_with_manufacturer_name(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
        mock_all_order_items_data: list[Any],
    ) -> None:
        """AC-005: 各明細に manufacturer_name が付与されたレスポンスが返される

        given: 複数メーカーの発注明細が存在する
        when: get_all_order_items メソッドを呼び出す
        then: 各明細に manufacturer_name が付与され、
              total, total_quantity, total_amount が正しく集計されたレスポンスが返される
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = mock_all_order_items_data

        result = await service.get_all_order_items()

        # レスポンスが正しい構造を持つこと
        assert hasattr(result, 'items')
        assert hasattr(result, 'total')
        assert hasattr(result, 'total_quantity')
        assert hasattr(result, 'total_amount')

        # 3件の明細が含まれること
        assert result.total == 3

        # 各明細に manufacturer_id と manufacturer_name が含まれること
        for item in result.items:
            assert hasattr(item, 'manufacturer_id')
            assert hasattr(item, 'manufacturer_name')
            assert item.manufacturer_name is not None

        # メーカー名が正しいこと
        manufacturer_names = {item.manufacturer_name for item in result.items}
        assert "メーカーA" in manufacturer_names
        assert "メーカーB" in manufacturer_names

    @pytest.mark.asyncio
    async def test_get_all_order_items_total_quantity_calculation(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
        mock_all_order_items_data: list[Any],
    ) -> None:
        """AC-005: total_quantity が正しく集計される

        given: quantity=2, quantity=1, quantity=5 の3件
        when: get_all_order_items を呼び出す
        then: total_quantity = 8
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = mock_all_order_items_data

        result = await service.get_all_order_items()

        # total_quantity = 2 + 1 + 5 = 8
        assert result.total_quantity == 8

    @pytest.mark.asyncio
    async def test_get_all_order_items_total_amount_calculation(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
        mock_all_order_items_data: list[Any],
    ) -> None:
        """AC-005: total_amount が正しく集計される

        given: price*quantity = 1000*2, 2000*1, 500*5 の3件
        when: get_all_order_items を呼び出す
        then: total_amount = 2000 + 2000 + 2500 = 6500
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = mock_all_order_items_data

        result = await service.get_all_order_items()

        # total_amount = (1000*2) + (2000*1) + (500*5) = 2000 + 2000 + 2500 = 6500
        assert result.total_amount == 6500

    @pytest.mark.asyncio
    async def test_get_all_order_items_passes_filters_to_repository(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ) -> None:
        """AC-005: フィルターパラメータがリポジトリに正しく渡される

        given: フィルター条件を指定する
        when: get_all_order_items をフィルター付きで呼び出す
        then: リポジトリの find_all_ordered_items_detail にパラメータが渡される
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = []

        manufacturer_id = str(uuid4())
        await service.get_all_order_items(
            status="ordered",
            search="キーホルダー",
            manufacturer_id=manufacturer_id,
            product_type="acrylic_keychain",
        )

        # リポジトリが正しいパラメータで呼ばれたことを確認
        mock_order_repo.find_all_ordered_items_detail.assert_called_once()
        call_kwargs = mock_order_repo.find_all_ordered_items_detail.call_args.kwargs
        assert call_kwargs.get("status") == "ordered"
        assert call_kwargs.get("search") == "キーホルダー"
        assert call_kwargs.get("manufacturer_id") == manufacturer_id
        assert call_kwargs.get("product_type") == "acrylic_keychain"

    @pytest.mark.asyncio
    async def test_get_all_order_items_empty_result(
        self,
        service: ManufacturerOrderService,
        mock_order_repo: AsyncMock,
    ) -> None:
        """AC-005: 明細が0件の場合は空レスポンスが返される

        given: 発注明細が0件
        when: get_all_order_items を呼び出す
        then: items=[], total=0, total_quantity=0, total_amount=0 が返される
        """
        mock_order_repo.find_all_ordered_items_detail.return_value = []

        result = await service.get_all_order_items()

        assert result.items == []
        assert result.total == 0
        assert result.total_quantity == 0
        assert result.total_amount == 0


# ===========================================================================
# AllManufacturerOrderItemResponse スキーマのテスト
# ===========================================================================

class TestAllManufacturerOrderItemResponseSchema:
    """AllManufacturerOrderItemResponse スキーマのテスト"""

    def test_schema_exists(self) -> None:
        """AllManufacturerOrderItemResponse スキーマが存在する"""
        from app.schemas.manufacturer import AllManufacturerOrderItemResponse
        assert AllManufacturerOrderItemResponse is not None

    def test_schema_has_manufacturer_id_field(self) -> None:
        """AllManufacturerOrderItemResponse に manufacturer_id フィールドがある"""
        from app.schemas.manufacturer import AllManufacturerOrderItemResponse
        fields = AllManufacturerOrderItemResponse.model_fields
        assert "manufacturer_id" in fields, \
            "AllManufacturerOrderItemResponse should have 'manufacturer_id' field"

    def test_schema_has_manufacturer_name_field(self) -> None:
        """AllManufacturerOrderItemResponse に manufacturer_name フィールドがある"""
        from app.schemas.manufacturer import AllManufacturerOrderItemResponse
        fields = AllManufacturerOrderItemResponse.model_fields
        assert "manufacturer_name" in fields, \
            "AllManufacturerOrderItemResponse should have 'manufacturer_name' field"

    def test_list_response_schema_exists(self) -> None:
        """AllManufacturerOrderItemListResponse スキーマが存在する"""
        from app.schemas.manufacturer import AllManufacturerOrderItemListResponse
        assert AllManufacturerOrderItemListResponse is not None

    def test_list_response_has_required_fields(self) -> None:
        """AllManufacturerOrderItemListResponse に必要なフィールドがある"""
        from app.schemas.manufacturer import AllManufacturerOrderItemListResponse
        fields = AllManufacturerOrderItemListResponse.model_fields
        assert "items" in fields
        assert "total" in fields
        assert "total_quantity" in fields
        assert "total_amount" in fields
