"""ManufacturerOrderService のユニットテスト

FEAT-0004: 発注資料ダウンロード時のステータス自動切り替え

テスト対象: generate_order_documents メソッド
- 「発注中」の明細のみをZIPに含める
- ダウンロード成功時に「発注中」→「製造中」にステータス更新
- 発注中の明細が0件の場合は NoOrderedItemsError を発生
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.manufacturer_order_service import ManufacturerOrderService
from app.models.order import OrderStatus
from app.utils.exceptions import NoOrderedItemsError, NotFoundError


class TestGenerateOrderDocumentsStatusUpdate:
    """発注資料ダウンロード時のステータス自動更新テスト"""

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
    def mock_order_items_ordered(self):
        """発注中ステータスの受注明細3件"""
        items = []
        for i in range(3):
            order_item = MagicMock()
            order_item.id = str(uuid4())
            order_item.order_id = str(uuid4())
            order_item.uid = f"UID-{i+1}"
            order_item.product_name = f"商品{i+1}"
            order_item.product_type = "tshirt"
            order_item.quantity = 1
            order_item.size = "M"
            order_item.position = "正面"
            order_item.color = "白"
            order_item.design_image_url = None
            order_item.thumbnail_image_url = None

            order = MagicMock()
            order.id = order_item.order_id
            order.order_number = f"ORD-{i+1}"
            order.status = OrderStatus.ORDERED.value
            order_item.order = order

            items.append((
                order_item,
                f"ORD-{i+1}",  # order_number
                datetime.now(),  # ordered_at
                "顧客名",  # customer_name
                1000,  # cost
                OrderStatus.ORDERED.value,  # order_status
            ))
        return items

    @pytest.fixture
    def mock_order_items_mixed(self):
        """発注中2件、製造中1件のミックス明細"""
        items = []
        statuses = [OrderStatus.ORDERED, OrderStatus.ORDERED, OrderStatus.MANUFACTURING]
        for i, status in enumerate(statuses):
            order_item = MagicMock()
            order_item.id = str(uuid4())
            order_item.order_id = str(uuid4())
            order_item.uid = f"UID-{i+1}"
            order_item.product_name = f"商品{i+1}"
            order_item.product_type = "tshirt"
            order_item.quantity = 1
            order_item.size = "M"
            order_item.position = "正面"
            order_item.color = "白"
            order_item.design_image_url = None
            order_item.thumbnail_image_url = None

            order = MagicMock()
            order.id = order_item.order_id
            order.order_number = f"ORD-{i+1}"
            order.status = status.value
            order_item.order = order

            items.append((
                order_item,
                f"ORD-{i+1}",  # order_number
                datetime.now(),  # ordered_at
                "顧客名",  # customer_name
                1000,  # cost
                status.value,  # order_status
            ))
        return items

    @pytest.mark.asyncio
    async def test_generate_order_documents_updates_status_to_manufacturing(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
        mock_order_items_ordered,
    ):
        """AC-001: 発注資料ダウンロード時に「発注中」の明細が「製造中」に更新される

        given: メーカーAに「発注中」ステータスの受注明細が3件ある
        when: 管理者がその3件を選択して発注資料をダウンロードする
        then:
          - ZIPファイルが正常にダウンロードされる
          - 3件の受注明細のステータスが「製造中」に更新される
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = mock_order_items_ordered

        # ZIPを生成（モックはしない - 実際の生成をテスト）
        with patch.object(service, '_download_file', return_value=(None, "")):
            zip_bytes, filename = await service.generate_order_documents(
                manufacturer_id=manufacturer_id,
            )

        # ZIPが生成されたことを確認
        assert zip_bytes is not None
        assert len(zip_bytes) > 0
        assert filename.endswith(".zip")

        # ステータス更新が呼ばれたことを確認
        mock_order_repo.update_status_by_manufacturer.assert_called_once()
        call_args = mock_order_repo.update_status_by_manufacturer.call_args
        assert call_args.kwargs["manufacturer_id"] == manufacturer_id
        assert call_args.kwargs["new_status"] == OrderStatus.MANUFACTURING
        # 3件のorder_item_idsが渡されること
        order_item_ids = call_args.kwargs["order_item_ids"]
        assert len(order_item_ids) == 3

    @pytest.mark.asyncio
    async def test_generate_order_documents_only_includes_ordered_status(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
        mock_order_items_mixed,
    ):
        """AC-002: 「発注中」以外のステータスはダウンロード対象外

        given: メーカーAに「発注中」2件、「製造中」1件の受注明細がある
        when: 管理者がダウンロードを実行する
        then:
          - 「発注中」の2件のみがZIPに含まれる
          - 「発注中」の2件のステータスが「製造中」に更新される
          - 「製造中」の1件はステータス変更されない
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer

        # find_ordered_items_by_manufacturer_detail は status=ORDERED でフィルタされるので
        # 発注中の2件のみ返す
        ordered_items = [
            item for item in mock_order_items_mixed
            if item[0].order.status == OrderStatus.ORDERED.value
        ]
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = ordered_items

        with patch.object(service, '_download_file', return_value=(None, "")):
            zip_bytes, filename = await service.generate_order_documents(
                manufacturer_id=manufacturer_id,
            )

        # ZIPが生成されたことを確認
        assert zip_bytes is not None

        # ステータス更新が呼ばれたことを確認
        mock_order_repo.update_status_by_manufacturer.assert_called_once()
        call_args = mock_order_repo.update_status_by_manufacturer.call_args
        # 2件のorder_item_idsのみが渡されること
        order_item_ids = call_args.kwargs["order_item_ids"]
        assert len(order_item_ids) == 2

    @pytest.mark.asyncio
    async def test_generate_order_documents_raises_error_when_no_ordered_items(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
    ):
        """AC-003: 発注中の明細が0件の場合は400エラー

        given: メーカーAに「製造中」の受注明細のみがある（発注中が0件）
        when: 管理者がダウンロードを実行する
        then: NoOrderedItemsError（400エラー）「ダウンロード対象の発注中明細がありません」が返る
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        # 発注中の明細が0件
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = []

        with pytest.raises(NoOrderedItemsError) as exc_info:
            await service.generate_order_documents(
                manufacturer_id=manufacturer_id,
            )

        assert exc_info.value.status_code == 400
        assert "ダウンロード対象の発注中明細がありません" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_generate_order_documents_with_order_item_ids_filter(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
        mock_order_items_ordered,
    ):
        """order_item_ids指定時は指定されたもののみダウンロード対象

        given: メーカーAに「発注中」ステータスの受注明細が3件ある
        when: 管理者が2件を指定してダウンロードする
        then:
          - 指定された2件のみがZIPに含まれる
          - 指定された2件のみステータスが「製造中」に更新される
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = mock_order_items_ordered

        # 最初の2件のみを指定
        target_item_ids = [mock_order_items_ordered[0][0].id, mock_order_items_ordered[1][0].id]

        with patch.object(service, '_download_file', return_value=(None, "")):
            zip_bytes, filename = await service.generate_order_documents(
                manufacturer_id=manufacturer_id,
                order_item_ids=target_item_ids,
            )

        # ZIPが生成されたことを確認
        assert zip_bytes is not None

        # ステータス更新が指定された2件のみで呼ばれることを確認
        mock_order_repo.update_status_by_manufacturer.assert_called_once()
        call_args = mock_order_repo.update_status_by_manufacturer.call_args
        order_item_ids = call_args.kwargs["order_item_ids"]
        assert len(order_item_ids) == 2
        assert set(order_item_ids) == set(target_item_ids)

    @pytest.mark.asyncio
    async def test_generate_order_documents_status_update_in_transaction(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer,
        mock_order_items_ordered,
    ):
        """ZIP生成成功後のみステータス更新が行われる（トランザクション整合性）

        given: メーカーAに「発注中」ステータスの受注明細がある
        when: ZIP生成が成功する
        then: ステータス更新が行われる

        Note: ZIP生成が失敗した場合はステータス更新が行われないことは
        別途テストで確認
        """
        manufacturer_id = mock_manufacturer.id
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = mock_order_items_ordered

        with patch.object(service, '_download_file', return_value=(None, "")):
            await service.generate_order_documents(manufacturer_id=manufacturer_id)

        # ZIP生成成功後にステータス更新が呼ばれることを確認
        mock_order_repo.update_status_by_manufacturer.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_order_documents_raises_not_found_for_invalid_manufacturer(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
    ):
        """存在しないメーカーIDの場合はNotFoundError

        given: 存在しないメーカーID
        when: ダウンロードを実行する
        then: NotFoundError（404エラー）が返る
        """
        mock_manufacturer_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.generate_order_documents(
                manufacturer_id="non-existent-id",
            )
