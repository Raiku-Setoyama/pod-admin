"""ManufacturerOrderService のユニットテスト

FEAT-0004: 発注資料ダウンロード時のステータス自動切り替え
FEAT-0012: 発注資料ダウンロードの命名規則変更

テスト対象: generate_order_documents メソッド
- 「発注中」の明細のみをZIPに含める
- ダウンロード成功時に「発注中」→「製造中」にステータス更新
- 発注中の明細が0件の場合は NoOrderedItemsError を発生
- 新命名規則でZIP/フォルダ/ファイルが生成される
"""

import io
import zipfile
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.order import OrderItemStatus, OrderStatus
from app.services.manufacturer_order_service import ManufacturerOrderService
from app.utils.exceptions import NoOrderedItemsError, NotFoundError

# ---------------------------------------------------------------------------
# Helper: mock order item factory
# ---------------------------------------------------------------------------

def _make_order_item(
    *,
    order_number: str = "POD-20260101-0001",
    uid: str = "abc123",
    product_name: str = "Tシャツ - M - 正面 - 白",
    product_type: str = "tshirt",
    quantity: int = 1,
    size: str = "M",
    position: str | None = "正面",
    color: str = "白",
    design_image_url: str | None = "https://example.com/design.ai",
    thumbnail_image_url: str | None = "https://example.com/thumb.png",
    status: OrderStatus = OrderStatus.ORDERED,
    cost: int = 1000,
    ordered_at: datetime | None = None,
    lead_time_days: int = 3,
) -> tuple[Any, ...]:
    """Create a mock order item tuple matching the repository return format.

    Returns: (OrderItem, order_number, ordered_at, customer_name, cost, item_status, order_status, lead_time_days)
    """
    order_item = MagicMock()
    order_item.id = str(uuid4())
    order_item.order_id = str(uuid4())
    order_item.uid = uid
    order_item.product_name = product_name
    order_item.product_type = product_type
    order_item.quantity = quantity
    order_item.size = size
    order_item.position = position
    order_item.color = color
    order_item.design_image_url = design_image_url
    order_item.thumbnail_image_url = thumbnail_image_url
    order_item.status = status.value  # OrderItem.status
    # v1 明細（製造データなし）: 発注ゲート・生成ファイル封入の対象外
    order_item.manufacturing_data_id = None
    order_item.manufacturing_data = None
    order_item.is_manufacturing_ready = True

    order = MagicMock()
    order.id = order_item.order_id
    order.order_number = order_number
    order.status = status.value
    order_item.order = order

    # 新しいタプル構造: (OrderItem, order_number, ordered_at, customer_name, cost, item_status, order_status, lead_time_days)
    return (
        order_item,
        order_number,
        ordered_at or datetime(2026, 2, 24, 10, 0, 0),
        "顧客名",
        cost,
        status.value,  # item_status (OrderItem.status)
        status.value,  # order_status (Order.status)
        lead_time_days,  # lead_time_days
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

class TestGenerateOrderDocumentsStatusUpdate:
    """発注資料ダウンロード時のステータス自動更新テスト"""

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
    def mock_manufacturer(self) -> Any:
        """モックメーカー"""
        manufacturer = MagicMock()
        manufacturer.id = str(uuid4())
        manufacturer.name = "テストメーカー"
        return manufacturer

    @pytest.fixture
    def mock_order_items_ordered(self) -> Any:
        """発注中ステータスの受注明細3件"""
        return [
            _make_order_item(
                order_number=f"ORD-{i+1}",
                uid=f"UID-{i+1}",
                product_name=f"商品{i+1}",
                design_image_url=None,
                thumbnail_image_url=None,
            )
            for i in range(3)
        ]

    @pytest.fixture
    def mock_order_items_mixed(self) -> Any:
        """発注中2件、製造中1件のミックス明細"""
        statuses = [OrderStatus.ORDERED, OrderStatus.ORDERED, OrderStatus.MANUFACTURING]
        return [
            _make_order_item(
                order_number=f"ORD-{i+1}",
                uid=f"UID-{i+1}",
                product_name=f"商品{i+1}",
                status=status,
                design_image_url=None,
                thumbnail_image_url=None,
            )
            for i, status in enumerate(statuses)
        ]

    @pytest.mark.asyncio
    async def test_generate_order_documents_updates_status_to_manufacturing(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer: Any,
        mock_order_items_ordered: Any,
    ) -> None:
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

        # update_item_status_by_manufacturerのモック設定
        affected_order_ids = {item[0].order_id for item in mock_order_items_ordered}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            [item[0] for item in mock_order_items_ordered],
            affected_order_ids,
        )

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
        mock_order_repo.update_item_status_by_manufacturer.assert_called_once()
        call_args = mock_order_repo.update_item_status_by_manufacturer.call_args
        assert call_args.kwargs["manufacturer_id"] == manufacturer_id
        assert call_args.kwargs["new_status"] == OrderItemStatus.MANUFACTURING
        # 3件のorder_item_idsが渡されること
        order_item_ids = call_args.kwargs["order_item_ids"]
        assert len(order_item_ids) == 3

    @pytest.mark.asyncio
    async def test_generate_order_documents_only_includes_ordered_status(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer: Any,
        mock_order_items_mixed: Any,
    ) -> None:
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

        # update_item_status_by_manufacturerのモック設定
        affected_order_ids = {item[0].order_id for item in ordered_items}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            [item[0] for item in ordered_items],
            affected_order_ids,
        )

        with patch.object(service, '_download_file', return_value=(None, "")):
            zip_bytes, filename = await service.generate_order_documents(
                manufacturer_id=manufacturer_id,
            )

        # ZIPが生成されたことを確認
        assert zip_bytes is not None

        # ステータス更新が呼ばれたことを確認
        mock_order_repo.update_item_status_by_manufacturer.assert_called_once()
        call_args = mock_order_repo.update_item_status_by_manufacturer.call_args
        # 2件のorder_item_idsのみが渡されること
        order_item_ids = call_args.kwargs["order_item_ids"]
        assert len(order_item_ids) == 2

    @pytest.mark.asyncio
    async def test_generate_order_documents_raises_error_when_no_ordered_items(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer: Any,
    ) -> None:
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
        mock_manufacturer: Any,
        mock_order_items_ordered: Any,
    ) -> None:
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

        # update_item_status_by_manufacturerのモック設定
        target_items = mock_order_items_ordered[:2]
        affected_order_ids = {item[0].order_id for item in target_items}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            [item[0] for item in target_items],
            affected_order_ids,
        )

        with patch.object(service, '_download_file', return_value=(None, "")):
            zip_bytes, filename = await service.generate_order_documents(
                manufacturer_id=manufacturer_id,
                order_item_ids=target_item_ids,
            )

        # ZIPが生成されたことを確認
        assert zip_bytes is not None

        # ステータス更新が指定された2件のみで呼ばれることを確認
        mock_order_repo.update_item_status_by_manufacturer.assert_called_once()
        call_args = mock_order_repo.update_item_status_by_manufacturer.call_args
        order_item_ids = call_args.kwargs["order_item_ids"]
        assert len(order_item_ids) == 2
        assert set(order_item_ids) == set(target_item_ids)

    @pytest.mark.asyncio
    async def test_generate_order_documents_status_update_in_transaction(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer: Any,
        mock_order_items_ordered: Any,
    ) -> None:
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

        # update_item_status_by_manufacturerのモック設定
        affected_order_ids = {item[0].order_id for item in mock_order_items_ordered}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            [item[0] for item in mock_order_items_ordered],
            affected_order_ids,
        )

        with patch.object(service, '_download_file', return_value=(None, "")):
            await service.generate_order_documents(manufacturer_id=manufacturer_id)

        # ZIP生成成功後にステータス更新が呼ばれることを確認
        mock_order_repo.update_item_status_by_manufacturer.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_order_documents_raises_not_found_for_invalid_manufacturer(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
    ) -> None:
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


# ===========================================================================
# FEAT-0012: 命名規則変更テスト
# ===========================================================================

class TestFeat0012NamingRules:
    """発注資料ダウンロードの命名規則

    命名規則:
    - ZIP名: TAPI_{メーカー名}_発注資料.zip
    - タイプフォルダ: {商品種類カテゴリ}_{YYYYMMDD}
    - Tシャツ特殊: Tシャツ- {印刷位置} -_{YYYYMMDD}
    - XLSX名: {prefix}_発注リスト_{YYYYMMDD}.xlsx (商品名・原価列なし)
    - 画像: {注文番号}_{製造番号}.png
    - 製造データ①: {商品フルネーム}【{数量}個】_{注文番号}_{製造番号}_{MMDD}.{ext}
    - 製造データ②: アクリルフィギュアのみ _stand.ai
    - 注文番号別サブフォルダに配置（XLSXはタイプフォルダ直下）
    """

    @pytest.fixture
    def mock_order_repo(self) -> Any:
        return AsyncMock()

    @pytest.fixture
    def mock_manufacturer_repo(self) -> Any:
        return AsyncMock()

    @pytest.fixture
    def mock_shipment_repo(self) -> Any:
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_repo: Any, mock_manufacturer_repo: Any, mock_shipment_repo: Any) -> Any:
        return ManufacturerOrderService(
            order_repo=mock_order_repo,
            manufacturer_repo=mock_manufacturer_repo,
            shipment_repo=mock_shipment_repo,
        )

    @pytest.fixture
    def mock_manufacturer(self) -> Any:
        manufacturer = MagicMock()
        manufacturer.id = str(uuid4())
        manufacturer.name = "テストメーカー"
        return manufacturer

    @pytest.fixture
    def fixed_now(self) -> Any:
        """テスト用の固定日時 (2026-02-24 10:30:00)"""
        return datetime(2026, 2, 24, 10, 30, 0)

    def _extract_zip(self, zip_bytes: bytes) -> zipfile.ZipFile:
        """ZIPバイト列を展開してZipFileオブジェクトを返す"""
        return zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

    def _get_zip_paths(self, zip_bytes: bytes) -> list[str]:
        """ZIP内の全パスをリストで返す"""
        with self._extract_zip(zip_bytes) as zf:
            return sorted(zf.namelist())

    async def _generate_zip(
        self,
        service: ManufacturerOrderService,
        mock_manufacturer_repo: AsyncMock,
        mock_order_repo: AsyncMock,
        mock_manufacturer: Any,
        items: list[tuple[Any, ...]],
        fixed_now: datetime,
        download_file_side_effect: Any=None,
    ) -> tuple[bytes, str]:
        """テスト用にZIPを生成するヘルパー"""
        mock_manufacturer_repo.find_by_id.return_value = mock_manufacturer
        mock_order_repo.find_ordered_items_by_manufacturer_detail.return_value = items

        # update_item_status_by_manufacturerのモック設定
        affected_order_ids = {item[0].order_id for item in items}
        mock_order_repo.update_item_status_by_manufacturer.return_value = (
            [item[0] for item in items],
            affected_order_ids,
        )

        if download_file_side_effect:
            side_effect = download_file_side_effect
        else:
            # デフォルト: design_image_url は .ai ファイル内容を返す、thumbnail は .png
            async def default_download(url: str) -> tuple[Any, ...]:
                if not url:
                    return None, ""
                if "design" in url:
                    return b"AI_FILE_CONTENT", "design.ai"
                if "thumb" in url:
                    return b"PNG_FILE_CONTENT", "thumb.png"
                return None, ""

            side_effect = default_download

        with patch.object(service, '_download_file', side_effect=side_effect), \
             patch('app.services.manufacturer_order_service.load_stand_file', return_value=b"STAND_CONTENT"), \
             patch('app.services.manufacturer_order_service.datetime') as mock_dt:
                mock_dt.now.return_value = fixed_now
                mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
                zip_bytes, filename = await service.generate_order_documents(
                    manufacturer_id=mock_manufacturer.id,
                )

        return zip_bytes, filename

    # -------------------------------------------------------------------
    # ZIP名テスト
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_zip_filename_is_tapi_manufacturer_name(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """ZIP名が TAPI_{メーカー名}_発注資料.zip になる

        given: アクリルキーホルダーの明細1件
        when: ZIPを生成する
        then: ZIP名が 'TAPI_テストメーカー_発注資料.zip' になる
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                uid="def456",
                order_number="POD-20260101-0002",
            ),
        ]

        _, filename = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        assert filename == "TAPI_テストメーカー_発注資料.zip"

    # -------------------------------------------------------------------
    # タイプフォルダ名テスト
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_type_folder_acrylic_keychain(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """タイプフォルダ名: アクリルキーホルダー_{YYYYMMDD}

        given: acrylic_keychain の明細
        when: ZIPを生成する
        then: タイプフォルダが 'アクリルキーホルダー_20260224' になる
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        folder_names = {p.split("/")[0] for p in paths}
        assert "アクリルキーホルダー_20260224" in folder_names

    @pytest.mark.asyncio
    async def test_type_folder_acrylic_figure(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """タイプフォルダ名: アクリルフィギュア_{YYYYMMDD}

        given: acrylic_stand (アクリルフィギュア) の明細
        when: ZIPを生成する
        then: タイプフォルダが 'アクリルフィギュア_20260224' になる
              (旧名「アクリルスタンド」ではない)
        """
        items = [
            _make_order_item(
                product_type="acrylic_stand",
                product_name="アクリルフィギュア - 70x70mm - アクリル",
                size="70x70mm",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        folder_names = {p.split("/")[0] for p in paths}
        assert "アクリルフィギュア_20260224" in folder_names
        # 旧名が使われていないこと
        assert "アクリルスタンド_20260224" not in folder_names

    @pytest.mark.asyncio
    async def test_type_folder_sticker(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """タイプフォルダ名: ステッカー_{YYYYMMDD}"""
        items = [
            _make_order_item(
                product_type="sticker",
                product_name="ステッカー - 100x100mm - ホワイト",
                size="100x100mm",
                color="ホワイト",
                position=None,
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        folder_names = {p.split("/")[0] for p in paths}
        assert "ステッカー_20260224" in folder_names

    @pytest.mark.asyncio
    async def test_type_folder_tote_bag(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """タイプフォルダ名: トートバッグ_{YYYYMMDD}"""
        items = [
            _make_order_item(
                product_type="tote_bag",
                product_name="トートバッグ - M - ナチュラル",
                size="M",
                color="ナチュラル",
                position=None,
                design_image_url="https://example.com/design.pdf",
            ),
        ]

        async def download_pdf(url: Any) -> tuple[Any, ...]:
            if "design" in url:
                return b"PDF_CONTENT", "design.pdf"
            if "thumb" in url:
                return b"PNG_CONTENT", "thumb.png"
            return None, ""

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
            download_file_side_effect=download_pdf,
        )

        paths = self._get_zip_paths(zip_bytes)
        folder_names = {p.split("/")[0] for p in paths}
        assert "トートバッグ_20260224" in folder_names

    # -------------------------------------------------------------------
    # Tシャツ印刷位置別フォルダ分割テスト
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_tshirt_folder_split_by_position(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """Tシャツは印刷位置ごとにフォルダが分割される

        given: Tシャツの正面1件、背面1件
        when: ZIPを生成する
        then: 'Tシャツ- 正面 -_20260224' と 'Tシャツ- 背面 -_20260224' の2フォルダが生成される
        """
        items = [
            _make_order_item(
                product_type="tshirt",
                product_name="Tシャツ - M - 正面 - 白",
                uid="front001",
                order_number="POD-20260101-0001",
                position="正面",
            ),
            _make_order_item(
                product_type="tshirt",
                product_name="Tシャツ - L - 背面 - 黒",
                uid="back001",
                order_number="POD-20260101-0002",
                position="背面",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        folder_names = {p.split("/")[0] for p in paths}
        assert "Tシャツ- 正面 -_20260224" in folder_names
        assert "Tシャツ- 背面 -_20260224" in folder_names

    @pytest.mark.asyncio
    async def test_tshirt_front_items_in_front_folder(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """正面のTシャツ明細は正面フォルダに含まれる

        given: Tシャツ正面1件
        when: ZIPを生成する
        then: 'Tシャツ- 正面 -_20260224/' 配下にファイルが存在する
        """
        items = [
            _make_order_item(
                product_type="tshirt",
                product_name="Tシャツ - M - 正面 - 白",
                uid="front001",
                order_number="POD-20260101-0001",
                position="正面",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        front_folder_files = [p for p in paths if p.startswith("Tシャツ- 正面 -_20260224/")]
        assert len(front_folder_files) > 0

    # -------------------------------------------------------------------
    # XLSXファイル名テスト（FEAT-0024: CSV→XLSX変更）
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_xlsx_filename_for_acrylic_keychain(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """XLSX名: アクリルキーホルダー_発注リスト_20260224.xlsx

        given: acrylic_keychain の明細
        when: ZIPを生成する
        then: XLSXが 'アクリルキーホルダー_発注リスト_20260224.xlsx' の名前で含まれる
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        xlsx_files = [p for p in paths if p.endswith(".xlsx")]
        assert any("アクリルキーホルダー_発注リスト_20260224.xlsx" in xlsx for xlsx in xlsx_files)

    @pytest.mark.asyncio
    async def test_xlsx_filename_for_tshirt_with_position(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """XLSX名: Tシャツ- 正面 -_発注リスト_20260224.xlsx

        given: Tシャツ正面の明細
        when: ZIPを生成する
        then: XLSXが 'Tシャツ- 正面 -_発注リスト_20260224.xlsx' の名前で含まれる
        """
        items = [
            _make_order_item(
                product_type="tshirt",
                product_name="Tシャツ - M - 正面 - 白",
                position="正面",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        xlsx_files = [p for p in paths if p.endswith(".xlsx")]
        assert any("Tシャツ- 正面 -_発注リスト_20260224.xlsx" in xlsx for xlsx in xlsx_files)

    @pytest.mark.asyncio
    async def test_xlsx_filename_for_acrylic_figure(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """XLSX名: アクリルフィギュア_発注リスト_20260224.xlsx"""
        items = [
            _make_order_item(
                product_type="acrylic_stand",
                product_name="アクリルフィギュア - 70x70mm - アクリル",
                size="70x70mm",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        xlsx_files = [p for p in paths if p.endswith(".xlsx")]
        assert any("アクリルフィギュア_発注リスト_20260224.xlsx" in xlsx for xlsx in xlsx_files)

    # -------------------------------------------------------------------
    # 画像ファイル名テスト
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_image_filename_format(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """画像ファイル名: {注文番号}_{製造番号}.png

        given: thumbnail_image_url を持つ明細
        when: ZIPを生成する
        then: 画像が '{注文番号}_{製造番号}.png' で保存される
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                order_number="POD-20260101-0002",
                uid="def456",
                thumbnail_image_url="https://example.com/thumb.png",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        png_files = [p for p in paths if p.endswith(".png")]
        # ファイル名部分のみ取り出す
        png_basenames = [p.split("/")[-1] for p in png_files]
        assert "POD-20260101-0002_def456.png" in png_basenames

    @pytest.mark.asyncio
    async def test_image_filename_not_old_format(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """旧フォーマット thumbnail_{filename} が使われていないこと

        given: thumbnail_image_url を持つ明細
        when: ZIPを生成する
        then: 'thumbnail_' プレフィックスのファイルが存在しない
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                order_number="POD-20260101-0002",
                uid="def456",
                thumbnail_image_url="https://example.com/thumb.png",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        # 旧フォーマットの thumbnail_ プレフィックスが存在しないこと
        thumbnail_prefixed = [p for p in paths if "thumbnail_" in p]
        assert len(thumbnail_prefixed) == 0

    # -------------------------------------------------------------------
    # 製造データ①ファイル名テスト
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_manufacturing_data_tshirt_front_pdf(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """Tシャツの製造データ①: _front.pdf 拡張子

        given: Tシャツの明細（design_image_url あり）
        when: ZIPを生成する
        then: 製造データが '{商品フルネーム}【{N}個】_{注文番号}_{製造番号}_{MMDD}_front.pdf' になる
        """
        items = [
            _make_order_item(
                product_type="tshirt",
                product_name="Tシャツ - M - 正面 - 白",
                order_number="POD-20260101-0001",
                uid="abc123",
                quantity=1,
                position="正面",
                design_image_url="https://example.com/design.pdf",
            ),
        ]

        async def download_pdf(url: Any) -> tuple[Any, ...]:
            if "design" in url:
                return b"PDF_CONTENT", "design.pdf"
            if "thumb" in url:
                return b"PNG_CONTENT", "thumb.png"
            return None, ""

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
            download_file_side_effect=download_pdf,
        )

        paths = self._get_zip_paths(zip_bytes)
        expected_name = "Tシャツ - M - 正面 - 白【個数】1個_POD-20260101-0001_abc123_0224_front.pdf"
        matching = [p for p in paths if expected_name in p]
        assert len(matching) == 1, f"Expected '{expected_name}' in paths: {paths}"

    @pytest.mark.asyncio
    async def test_manufacturing_data_tote_bag_pdf(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """トートバッグの製造データ①: .pdf 拡張子（_front なし）

        given: トートバッグの明細
        when: ZIPを生成する
        then: 製造データが '{商品フルネーム}【{N}個】_{注文番号}_{製造番号}_{MMDD}.pdf' になる
        """
        items = [
            _make_order_item(
                product_type="tote_bag",
                product_name="トートバッグ - M - ナチュラル",
                order_number="POD-20260101-0005",
                uid="mno345",
                quantity=1,
                size="M",
                color="ナチュラル",
                position=None,
                design_image_url="https://example.com/design.pdf",
            ),
        ]

        async def download_pdf(url: Any) -> tuple[Any, ...]:
            if "design" in url:
                return b"PDF_CONTENT", "design.pdf"
            if "thumb" in url:
                return b"PNG_CONTENT", "thumb.png"
            return None, ""

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
            download_file_side_effect=download_pdf,
        )

        paths = self._get_zip_paths(zip_bytes)
        expected_name = "トートバッグ - M - ナチュラル【個数】1個_POD-20260101-0005_mno345_0224.pdf"
        matching = [p for p in paths if p.endswith(expected_name)]
        assert len(matching) == 1, f"Expected '{expected_name}' in paths: {paths}"

    @pytest.mark.asyncio
    async def test_manufacturing_data_acrylic_keychain_ai(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """アクリルキーホルダーの製造データ①: .ai 拡張子

        given: アクリルキーホルダーの明細
        when: ZIPを生成する
        then: 製造データが '{商品フルネーム}【{N}個】_{注文番号}_{製造番号}_{MMDD}.ai' になる
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                order_number="POD-20260101-0002",
                uid="def456",
                quantity=2,
                size="50x50 (mm)",
                position="",
                color="アクリル",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        expected_name = "アクリルキーホルダー - 50x50 (mm) - アクリル【個数】2個_POD-20260101-0002_def456_0224.ai"
        matching = [p for p in paths if p.endswith(expected_name)]
        assert len(matching) == 1, f"Expected '{expected_name}' in paths: {paths}"

    @pytest.mark.asyncio
    async def test_manufacturing_data_acrylic_figure_ai(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """アクリルフィギュアの製造データ①: .ai 拡張子

        given: アクリルフィギュア (acrylic_stand) の明細
        when: ZIPを生成する
        then: 製造データが '{商品フルネーム}【{N}個】_{注文番号}_{製造番号}_{MMDD}.ai' になる
        """
        items = [
            _make_order_item(
                product_type="acrylic_stand",
                product_name="アクリルフィギュア - 70x70mm - アクリル",
                order_number="POD-20260101-0003",
                uid="ghi789",
                quantity=1,
                size="70x70mm",
                position="",
                color="アクリル",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        expected_name = "アクリルフィギュア - 70x70mm - アクリル【個数】1個_POD-20260101-0003_ghi789_0224.ai"
        matching = [p for p in paths if p.endswith(expected_name)]
        assert len(matching) == 1, f"Expected '{expected_name}' in paths: {paths}"

    @pytest.mark.asyncio
    async def test_manufacturing_data_sticker_ai(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """ステッカーの製造データ①: .ai 拡張子

        given: ステッカーの明細
        when: ZIPを生成する
        then: 製造データが '{商品フルネーム}【{N}個】_{注文番号}_{製造番号}_{MMDD}.ai' になる
        """
        items = [
            _make_order_item(
                product_type="sticker",
                product_name="ステッカー - 100x100mm - ホワイト",
                order_number="POD-20260101-0004",
                uid="jkl012",
                quantity=3,
                size="100x100mm",
                color="ホワイト",
                position=None,
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        expected_name = "ステッカー - 100x100mm - ホワイト【個数】3個_POD-20260101-0004_jkl012_0224.ai"
        matching = [p for p in paths if p.endswith(expected_name)]
        assert len(matching) == 1, f"Expected '{expected_name}' in paths: {paths}"

    # -------------------------------------------------------------------
    # 製造データ②テスト（アクリルフィギュア _stand.ai）
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_acrylic_figure_has_stand_file(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """アクリルフィギュアに製造データ②（_stand.ai）が含まれる

        given: アクリルフィギュアの明細
        when: ZIPを生成する
        then: '{商品フルネーム}【{N}個】_{注文番号}_{製造番号}_{MMDD}_stand.ai' が含まれる
        """
        items = [
            _make_order_item(
                product_type="acrylic_stand",
                product_name="アクリルフィギュア - 70x70mm - アクリル",
                order_number="POD-20260101-0003",
                uid="ghi789",
                quantity=1,
                size="70x70mm",
                position="",
                color="アクリル",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        expected_stand = "アクリルフィギュア - 70x70mm - アクリル【個数】1個_POD-20260101-0003_ghi789_0224_stand.ai"
        matching = [p for p in paths if p.endswith(expected_stand)]
        assert len(matching) == 1, f"Expected stand file '{expected_stand}' in paths: {paths}"

    @pytest.mark.asyncio
    async def test_non_acrylic_figure_has_no_stand_file(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """アクリルフィギュア以外に _stand.ai が含まれない

        given: アクリルキーホルダーの明細
        when: ZIPを生成する
        then: '_stand.ai' が含まれない
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                order_number="POD-20260101-0002",
                uid="def456",
                quantity=2,
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        stand_files = [p for p in paths if "_stand.ai" in p]
        assert len(stand_files) == 0, f"Unexpected stand files: {stand_files}"

    @pytest.mark.asyncio
    async def test_tshirt_has_no_stand_file(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """Tシャツに _stand.ai が含まれない"""
        items = [
            _make_order_item(
                product_type="tshirt",
                product_name="Tシャツ - M - 正面 - 白",
                position="正面",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        stand_files = [p for p in paths if "_stand.ai" in p]
        assert len(stand_files) == 0

    # -------------------------------------------------------------------
    # 注文番号サブフォルダ配置テスト
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_order_number_subfolders(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """製造データ・画像が注文番号フォルダに配置される

        given: 同一タイプの明細2件（異なる注文番号）
        when: ZIPを生成する
        then: 各注文番号のサブフォルダにファイルが配置される
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                order_number="POD-20260101-0001",
                uid="aaa111",
                quantity=1,
            ),
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                order_number="POD-20260101-0002",
                uid="bbb222",
                quantity=1,
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        type_folder = "アクリルキーホルダー_20260224"

        # 注文番号サブフォルダが存在する
        non_xlsx_files = [
            p for p in paths
            if p.startswith(type_folder + "/") and not p.endswith(".xlsx")
        ]
        for path in non_xlsx_files:
            parts = path.split("/")
            assert len(parts) == 3, (
                f"Expected {type_folder}/{{order_number}}/{{filename}} but got: {path}"
            )

        # 各注文番号のフォルダが存在
        subfolders = {p.split("/")[1] for p in non_xlsx_files}
        assert "POD-20260101-0001" in subfolders
        assert "POD-20260101-0002" in subfolders

    @pytest.mark.asyncio
    async def test_xlsx_at_type_folder_level(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """XLSXはタイプフォルダ直下に配置される（注文番号フォルダに入らない）

        given: 同一タイプの明細2件
        when: ZIPを生成する
        then: XLSXは {type_folder}/ 直下にある
        """
        items = [
            _make_order_item(
                product_type="sticker",
                product_name="ステッカー - 100x100mm - ホワイト",
                order_number=f"POD-20260101-000{i+1}",
                uid=f"uid{i+1:03d}",
                quantity=1,
                size="100x100mm",
                color="ホワイト",
                position=None,
            )
            for i in range(2)
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        type_folder = "ステッカー_20260224"

        # XLSXはタイプフォルダ直下
        xlsx_files = [p for p in paths if p.endswith(".xlsx")]
        for xlsx in xlsx_files:
            parts = xlsx.split("/")
            assert len(parts) == 2, f"XLSX should be at type folder level: {xlsx}"
            assert parts[0] == type_folder

        # 製造データ・画像は注文番号フォルダ内
        non_xlsx_files = [
            p for p in paths
            if p.startswith(type_folder + "/") and not p.endswith(".xlsx")
        ]
        assert len(non_xlsx_files) >= 2  # 最低でも製造データ2件
        for path in non_xlsx_files:
            parts = path.split("/")
            assert len(parts) == 3, f"Expected order subfolder: {path}"

    # -------------------------------------------------------------------
    # ZIP構造全体の統合テスト
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_zip_contains_expected_structure_acrylic_keychain(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """アクリルキーホルダーのZIP構造が正しい

        given: アクリルキーホルダー明細1件
        when: ZIPを生成する
        then: 以下の構造になる
          アクリルキーホルダー_20260224/
            アクリルキーホルダー_発注リスト_20260224.xlsx
            POD-20260101-0002/
              POD-20260101-0002_def456.png
              アクリルキーホルダー - 50x50 (mm) - アクリル【個数】2個_POD-20260101-0002_def456_0224.ai
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                order_number="POD-20260101-0002",
                uid="def456",
                quantity=2,
                size="50x50 (mm)",
                position="",
                color="アクリル",
                thumbnail_image_url="https://example.com/thumb.png",
                design_image_url="https://example.com/design.ai",
            ),
        ]

        zip_bytes, filename = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        type_folder = "アクリルキーホルダー_20260224"

        # ZIP名
        assert filename == "TAPI_テストメーカー_発注資料.zip"

        # 期待されるファイル
        expected_files = [
            f"{type_folder}/アクリルキーホルダー_発注リスト_20260224.xlsx",
            f"{type_folder}/POD-20260101-0002/POD-20260101-0002_def456.png",
            f"{type_folder}/POD-20260101-0002/アクリルキーホルダー - 50x50 (mm) - アクリル【個数】2個_POD-20260101-0002_def456_0224.ai",
        ]

        for expected in expected_files:
            assert expected in paths, f"Expected '{expected}' in {paths}"

    @pytest.mark.asyncio
    async def test_zip_contains_expected_structure_acrylic_figure(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """アクリルフィギュアのZIP構造が正しい（スタンドファイル含む）

        given: アクリルフィギュア明細1件
        when: ZIPを生成する
        then: 以下の構造になる
          アクリルフィギュア_20260224/
            アクリルフィギュア_発注リスト_20260224.xlsx
            POD-20260101-0003/
              POD-20260101-0003_ghi789.png
              アクリルフィギュア - 70x70mm - アクリル【個数】1個_POD-20260101-0003_ghi789_0224.ai
              アクリルフィギュア - 70x70mm - アクリル【個数】1個_POD-20260101-0003_ghi789_0224_stand.ai
        """
        items = [
            _make_order_item(
                product_type="acrylic_stand",
                product_name="アクリルフィギュア - 70x70mm - アクリル",
                order_number="POD-20260101-0003",
                uid="ghi789",
                quantity=1,
                size="70x70mm",
                position="",
                color="アクリル",
                thumbnail_image_url="https://example.com/thumb.png",
                design_image_url="https://example.com/design.ai",
            ),
        ]

        zip_bytes, filename = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        type_folder = "アクリルフィギュア_20260224"

        # ZIP名
        assert filename == "TAPI_テストメーカー_発注資料.zip"

        # 期待されるファイル（スタンドファイル含む）
        expected_files = [
            f"{type_folder}/アクリルフィギュア_発注リスト_20260224.xlsx",
            f"{type_folder}/POD-20260101-0003/POD-20260101-0003_ghi789.png",
            f"{type_folder}/POD-20260101-0003/アクリルフィギュア - 70x70mm - アクリル【個数】1個_POD-20260101-0003_ghi789_0224.ai",
            f"{type_folder}/POD-20260101-0003/アクリルフィギュア - 70x70mm - アクリル【個数】1個_POD-20260101-0003_ghi789_0224_stand.ai",
        ]

        for expected in expected_files:
            assert expected in paths, f"Expected '{expected}' in {paths}"

    @pytest.mark.asyncio
    async def test_zip_contains_expected_structure_tshirt(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """TシャツのZIP構造が正しい（_front.pdf 含む）

        given: Tシャツ正面の明細1件
        when: ZIPを生成する
        then: 以下の構造になる
          Tシャツ- 正面 -_20260224/
            Tシャツ- 正面 -_発注リスト_20260224.xlsx
            POD-20260101-0001/
              POD-20260101-0001_abc123.png
              Tシャツ - M - 正面 - 白【個数】1個_POD-20260101-0001_abc123_0224_front.pdf
        """
        items = [
            _make_order_item(
                product_type="tshirt",
                product_name="Tシャツ - M - 正面 - 白",
                order_number="POD-20260101-0001",
                uid="abc123",
                quantity=1,
                position="正面",
                thumbnail_image_url="https://example.com/thumb.png",
                design_image_url="https://example.com/design.pdf",
            ),
        ]

        async def download_pdf(url: Any) -> tuple[Any, ...]:
            if "design" in url:
                return b"PDF_CONTENT", "design.pdf"
            if "thumb" in url:
                return b"PNG_CONTENT", "thumb.png"
            return None, ""

        zip_bytes, filename = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
            download_file_side_effect=download_pdf,
        )

        paths = self._get_zip_paths(zip_bytes)
        type_folder = "Tシャツ- 正面 -_20260224"

        expected_files = [
            f"{type_folder}/Tシャツ- 正面 -_発注リスト_20260224.xlsx",
            f"{type_folder}/POD-20260101-0001/POD-20260101-0001_abc123.png",
            f"{type_folder}/POD-20260101-0001/Tシャツ - M - 正面 - 白【個数】1個_POD-20260101-0001_abc123_0224_front.pdf",
        ]

        for expected in expected_files:
            assert expected in paths, f"Expected '{expected}' in {paths}"

    # -------------------------------------------------------------------
    # 旧命名規則が使われていないことのテスト
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_manufacturer_name_in_zip_filename(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """ZIP名にメーカー名が含まれる

        given: テストメーカーの明細
        when: ZIPを生成する
        then: ZIP名が 'TAPI_テストメーカー_発注資料.zip'
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
            ),
        ]

        _, filename = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        assert filename == "TAPI_テストメーカー_発注資料.zip"

    @pytest.mark.asyncio
    async def test_no_manufacturer_name_in_zip_paths(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """ZIP内パスにメーカー名が含まれない

        given: テストメーカーの明細
        when: ZIPを生成する
        then: ZIP内のパスに 'テストメーカー' が含まれない
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        for path in paths:
            assert "テストメーカー" not in path, f"Manufacturer name found in path: {path}"

    @pytest.mark.asyncio
    async def test_no_old_xlsx_naming_format(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """旧XLSX命名フォーマット（ハイフン区切り）が使われていない

        given: 明細
        when: ZIPを生成する
        then: XLSX名に '-発注リスト_' のパターンがない（新は '発注リスト_'）
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        xlsx_files = [p for p in paths if p.endswith(".xlsx")]
        for xlsx_path in xlsx_files:
            basename = xlsx_path.split("/")[-1]
            # 旧フォーマットは "{product_type_name}-発注リスト_" だった
            # 新フォーマットは "{prefix}発注リスト_" でハイフンなし
            assert "-発注リスト_" not in basename, (
                f"Old XLSX naming format found: {basename}"
            )

    @pytest.mark.asyncio
    async def test_no_old_design_file_naming(
        self, service: Any, mock_manufacturer_repo: Any, mock_order_repo: Any, mock_manufacturer: Any, fixed_now: Any,
    ) -> None:
        """旧デザインファイル命名（{注文番号}_{uid}_{商品種類}.ai）が使われていない

        given: アクリルキーホルダーの明細
        when: ZIPを生成する
        then: '{order_number}_{uid}_アクリルキーホルダー.ai' のパターンがない
        """
        items = [
            _make_order_item(
                product_type="acrylic_keychain",
                product_name="アクリルキーホルダー - 50x50 (mm) - アクリル",
                order_number="POD-20260101-0002",
                uid="def456",
            ),
        ]

        zip_bytes, _ = await self._generate_zip(
            service, mock_manufacturer_repo, mock_order_repo,
            mock_manufacturer, items, fixed_now,
        )

        paths = self._get_zip_paths(zip_bytes)
        old_pattern_files = [
            p for p in paths
            if p.endswith("_アクリルキーホルダー.ai")
        ]
        assert len(old_pattern_files) == 0, f"Old naming found: {old_pattern_files}"
