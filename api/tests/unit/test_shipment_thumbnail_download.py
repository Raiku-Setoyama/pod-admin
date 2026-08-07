"""Unit tests for shipment thumbnail ZIP download.

FEAT-0022: 配送一覧ページから選択した配送に紐づく商品サムネイル画像をZIPダウンロード
FEAT-0023: ZIP内画像ファイル名を「{order_number}_{uid}{ext}」のフラット構造に変更

Tests cover:
- AC-001: ShipmentThumbnailDownloadRequest スキーマのバリデーション
- AC-002: shipment_ids が空リストの場合は 422 バリデーションエラー
- AC-003: 配送IDに紐づく OrderItem の thumbnail_image_url を収集してZIPを返す
- AC-004: thumbnail_image_url が null の OrderItem はスキップされる
- AC-005: 画像取得失敗時はスキップ+ログ記録
- AC-006: 全 thumbnail が null / 全取得失敗時は 404 エラー
- AC-007: 存在しない配送IDはスキップ
- AC-008: ZIP内のファイルパスが {order_number}_{uid}{ext} 形式（フラット構造、FEAT-0023）
- AC-009: ZIPファイル名が 配送サムネイル_{YYYYMMDD_HHMMSS}.zip 形式
"""

import io
import logging
import re
import zipfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.order import Order, OrderItem
from app.models.shipment import Shipment, ShipmentItem, ShipmentStatus

# Direct import - will cause ImportError (test failure) until implementation exists
from app.schemas.shipment import ShipmentThumbnailDownloadRequest
from app.services.shipment_service import ShipmentService

# ======================================
# Fixtures
# ======================================


@pytest.fixture
def mock_shipment_repo() -> Any:
    """Mock shipment repository."""
    return AsyncMock()


@pytest.fixture
def mock_order_repo() -> Any:
    """Mock order repository."""
    return AsyncMock()


@pytest.fixture
def mock_file_storage() -> Any:
    """Mock file storage."""
    return AsyncMock()


@pytest.fixture
def shipment_service(mock_shipment_repo: Any, mock_order_repo: Any, mock_file_storage: Any) -> Any:
    """Create ShipmentService with mocked dependencies."""
    return ShipmentService(
        shipment_repo=mock_shipment_repo,
        order_repo=mock_order_repo,
        file_storage=mock_file_storage,
    )


# ======================================
# Helpers
# ======================================


def create_mock_order_item(
    item_id: str = "item-123",
    product_name: str = "Tshirt M White",
    thumbnail_image_url: str | None = "https://example.com/thumbnails/thumb1.png",
    design_image_url: str | None = None,
    uid: str | None = None,
) -> MagicMock:
    """Create a mock OrderItem."""
    item = MagicMock(spec=OrderItem)
    item.id = item_id
    item.product_name = product_name
    item.thumbnail_image_url = thumbnail_image_url
    item.design_image_url = design_image_url
    item.uid = uid
    item.quantity = 1
    return item


def create_mock_order(
    order_id: str = "order-123",
    order_number: str = "ORD-001",
    items: list[Any] | None = None,
) -> MagicMock:
    """Create a mock Order with OrderItems."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.order_number = order_number
    order.items = items or []
    return order


def create_mock_shipment_item(
    item_id: str = "si-123",
    order_id: str = "order-123",
    order: MagicMock | None = None,
) -> MagicMock:
    """Create a mock ShipmentItem."""
    si = MagicMock(spec=ShipmentItem)
    si.id = item_id
    si.order_id = order_id
    si.order = order
    return si


def create_mock_shipment(
    shipment_id: str = "shipment-123",
    items: list[Any] | None = None,
) -> MagicMock:
    """Create a mock Shipment with ShipmentItems."""
    shipment = MagicMock(spec=Shipment)
    shipment.id = shipment_id
    shipment.status = ShipmentStatus.PENDING.value
    shipment.items = items or []
    return shipment


# ======================================
# AC-001: ShipmentThumbnailDownloadRequest スキーマバリデーション
# ======================================


class TestShipmentThumbnailDownloadRequestSchema:
    """AC-001: ShipmentThumbnailDownloadRequest が shipment_ids フィールドを持ち、min_length=1 のバリデーションがある."""

    def test_valid_shipment_ids_accepted(self) -> None:
        """shipment_ids フィールドが正しく設定される（1件）."""
        request = ShipmentThumbnailDownloadRequest(shipment_ids=["shipment-1"])
        assert request.shipment_ids == ["shipment-1"]

    def test_multiple_shipment_ids_accepted(self) -> None:
        """shipment_ids フィールドが正しく設定される（複数件）."""
        request = ShipmentThumbnailDownloadRequest(
            shipment_ids=["shipment-1", "shipment-2", "shipment-3"]
        )
        assert len(request.shipment_ids) == 3


# ======================================
# AC-002: shipment_ids が空リストの場合は 422 バリデーションエラー
# ======================================


class TestEmptyShipmentIdsValidation:
    """AC-002: shipment_ids が空リストの場合は 422 バリデーションエラーになる."""

    def test_empty_shipment_ids_validation_error(self) -> None:
        """空の shipment_ids リストは ValidationError になる."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            ShipmentThumbnailDownloadRequest(shipment_ids=[])


# ======================================
# AC-003: 配送IDに紐づく OrderItem の thumbnail_image_url を収集してZIPを返す
# ======================================


class TestDownloadThumbnailsReturnsZip:
    """AC-003: 選択された配送IDに紐づく OrderItem の thumbnail_image_url を収集してZIPを返す."""

    @pytest.mark.asyncio
    async def test_download_thumbnails_returns_zip_bytes_and_filename(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """対象画像を含むZIPファイルのバイトデータとファイル名のタプルが返される."""
        # Arrange: shipment -> shipment_item -> order -> order_item with thumbnail
        order_item = create_mock_order_item(
            item_id="oi-1",
            product_name="Tshirt M White",
            thumbnail_image_url="https://example.com/thumb1.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[order_item],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1",
            order_id="order-1",
            order=order,
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1",
            items=[shipment_item],
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        # Mock httpx image fetch
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake-image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            result = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: returns tuple of (bytes, filename)
        assert isinstance(result, tuple)
        zip_bytes, filename = result
        assert isinstance(zip_bytes, bytes)
        assert isinstance(filename, str)
        assert len(zip_bytes) > 0

        # Verify it's a valid ZIP
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1


# ======================================
# AC-004: thumbnail_image_url が null の OrderItem はスキップされる
# ======================================


class TestSkipNullThumbnailImageUrl:
    """AC-004: thumbnail_image_url が null の OrderItem はスキップされる."""

    @pytest.mark.asyncio
    async def test_null_thumbnail_items_are_skipped(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """thumbnail_image_url が null のアイテムはスキップされ、画像を持つアイテムのみがZIPに含まれる."""
        # Arrange
        item_with_thumb = create_mock_order_item(
            item_id="oi-1",
            product_name="Tshirt M White",
            thumbnail_image_url="https://example.com/thumb1.png",
        )
        item_without_thumb = create_mock_order_item(
            item_id="oi-2",
            product_name="Tshirt L Black",
            thumbnail_image_url=None,
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_with_thumb, item_without_thumb],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake-image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: ZIP should only contain one file (the item with thumbnail)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1


# ======================================
# AC-005: 画像取得失敗時はスキップ+ログ記録
# ======================================


class TestImageFetchFailureSkipAndLog:
    """AC-005: 画像URLからの取得に失敗した場合はスキップしてログに記録する."""

    @pytest.mark.asyncio
    async def test_failed_image_fetch_is_skipped_and_logged(
        self, shipment_service: Any, mock_shipment_repo: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """取得失敗した画像はスキップされ、ログに警告が記録される."""
        # Arrange
        item_good = create_mock_order_item(
            item_id="oi-1",
            product_name="Good Product",
            thumbnail_image_url="https://example.com/good.png",
        )
        item_bad = create_mock_order_item(
            item_id="oi-2",
            product_name="Bad Product",
            thumbnail_image_url="https://example.com/bad.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_good, item_bad],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        # Mock: good URL succeeds, bad URL returns 404
        mock_response_good = MagicMock()
        mock_response_good.status_code = 200
        mock_response_good.content = b"good-image-data"
        mock_response_good.headers = {"content-type": "image/png"}

        mock_response_bad = MagicMock()
        mock_response_bad.status_code = 404
        mock_response_bad.content = b""

        async def side_effect_get(url: Any, **kwargs: Any) -> Any:
            if "good" in url:
                return mock_response_good
            return mock_response_bad

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = side_effect_get
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            with caplog.at_level(logging.WARNING):
                zip_bytes, _ = await shipment_service.download_thumbnails(
                    shipment_ids=["shipment-1"]
                )

        # Assert: Only one file in ZIP (the good one)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1

        # Assert: Warning logged for failed fetch
        assert any(
            "bad.png" in record.message or "bad" in record.message.lower()
            for record in caplog.records
            if record.levelno >= logging.WARNING
        )

    @pytest.mark.asyncio
    async def test_timeout_on_image_fetch_is_skipped(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """タイムアウトした画像取得はスキップされる."""
        import httpx

        # Arrange
        item_timeout = create_mock_order_item(
            item_id="oi-1",
            product_name="Timeout Product",
            thumbnail_image_url="https://example.com/timeout.png",
        )
        item_good = create_mock_order_item(
            item_id="oi-2",
            product_name="Good Product",
            thumbnail_image_url="https://example.com/good.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_timeout, item_good],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response_good = MagicMock()
        mock_response_good.status_code = 200
        mock_response_good.content = b"good-image-data"
        mock_response_good.headers = {"content-type": "image/png"}

        async def side_effect_get(url: Any, **kwargs: Any) -> Any:
            if "timeout" in url:
                raise httpx.TimeoutException("Connection timed out")
            return mock_response_good

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = side_effect_get
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: Only the good image is in ZIP
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert len(zf.namelist()) == 1


# ======================================
# AC-006: 全 thumbnail が null / 全取得失敗時は 404 エラー
# ======================================


class TestAllThumbnailsNullOrFailedReturn404:
    """AC-006: 全ての thumbnail_image_url が null または全ての画像取得に失敗した場合は 404 エラーを返す."""

    @pytest.mark.asyncio
    async def test_all_thumbnails_null_returns_404(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """全ての thumbnail_image_url が null の場合、404 エラーが返される."""
        # Arrange
        item_null_1 = create_mock_order_item(
            item_id="oi-1", thumbnail_image_url=None
        )
        item_null_2 = create_mock_order_item(
            item_id="oi-2", thumbnail_image_url=None
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_null_1, item_null_2],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )
        assert exc_info.value.status_code == 404
        assert "サムネイル画像" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_all_image_fetches_failed_returns_404(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """全ての画像URLからの取得に失敗した場合、404 エラーが返される."""
        # Arrange
        item_1 = create_mock_order_item(
            item_id="oi-1",
            thumbnail_image_url="https://example.com/bad1.png",
        )
        item_2 = create_mock_order_item(
            item_id="oi-2",
            thumbnail_image_url="https://example.com/bad2.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_1, item_2],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response_bad = MagicMock()
        mock_response_bad.status_code = 500
        mock_response_bad.content = b""

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response_bad
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await shipment_service.download_thumbnails(
                    shipment_ids=["shipment-1"]
                )
            assert exc_info.value.status_code == 404


# ======================================
# AC-007: 存在しない配送IDはスキップ
# ======================================


class TestNonExistentShipmentIdsSkipped:
    """AC-007: 存在しない配送IDが含まれている場合、存在する配送のみ処理される."""

    @pytest.mark.asyncio
    async def test_nonexistent_shipment_ids_are_skipped(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """存在しない配送IDはスキップされ、存在する配送の画像のみがZIPに含まれる."""
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-1",
            product_name="Valid Product",
            thumbnail_image_url="https://example.com/valid.png",
        )
        order = create_mock_order(
            order_id="order-valid",
            order_number="ORD-VALID",
            items=[order_item],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-valid", order=order
        )
        valid_shipment = create_mock_shipment(
            shipment_id="shipment-valid", items=[shipment_item]
        )

        async def find_by_id(shipment_id: Any) -> Any:
            if shipment_id == "shipment-valid":
                return valid_shipment
            return None  # Not found

        mock_shipment_repo.find_by_id.side_effect = find_by_id

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-valid", "shipment-nonexistent"]
            )

        # Assert: ZIP contains files only from the valid shipment
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            assert any("ORD-VALID" in f for f in file_list)

    @pytest.mark.asyncio
    async def test_all_nonexistent_shipment_ids_returns_404(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """全ての配送IDが存在しない場合は 404 エラーが返される."""
        # Arrange
        mock_shipment_repo.find_by_id.return_value = None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await shipment_service.download_thumbnails(
                shipment_ids=["nonexistent-1", "nonexistent-2"]
            )
        assert exc_info.value.status_code == 404


# ======================================
# AC-008: ZIP内のファイルパスが {order_number}_{uid}{ext} 形式（フラット構造）
# FEAT-0023: サブディレクトリなし、product_name/index を除去し uid で命名
# ======================================


class TestZipFilePathFormat:
    """AC-008: ZIP内のファイルパスが「{order_number}_{uid}{ext}」のフラット形式になっている."""

    @pytest.mark.asyncio
    async def test_zip_file_path_flat_format_with_uid(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-002: ZIP内ファイルパスが「{order_number}_{uid}{ext}」形式のフラット構造."""
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-1",
            product_name="Tシャツ Mサイズ 白",
            thumbnail_image_url="https://example.com/thumb1.png",
            uid="MFG-001",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[order_item],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: flat path "ORD-001_MFG-001.png" (no subdirectory)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            file_path = file_list[0]
            assert file_path == "ORD-001_MFG-001.png"
            # Must NOT contain "/" (no subdirectory)
            assert "/" not in file_path

    @pytest.mark.asyncio
    async def test_zip_file_path_no_product_name_or_index(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-001: image_tasks に uid が含まれ、product_name と index が含まれない.

        ファイルパスに product_name や連番 index が使われていないことを確認する。
        """
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-1",
            product_name="Tシャツ Mサイズ 白",
            thumbnail_image_url="https://example.com/thumb1.png",
            uid="MFG-ABC",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[order_item],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: file path must NOT contain product_name or sequential index
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            file_path = file_list[0]
            # product_name must not appear in the path
            assert "Tシャツ" not in file_path
            # Sequential index pattern (_1.) must not appear
            assert "_1." not in file_path
            # uid must appear
            assert "MFG-ABC" in file_path

    @pytest.mark.asyncio
    async def test_zip_file_path_uid_none_uses_empty_string(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-003: uid が None の場合は空文字として扱われ「{order_number}_{ext}」形式になる."""
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-1",
            product_name="Product",
            thumbnail_image_url="https://example.com/thumb1.png",
            uid=None,
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[order_item],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: "ORD-001_.png" (uid part is empty string)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            file_path = file_list[0]
            assert file_path == "ORD-001_.png"
            assert "/" not in file_path

    @pytest.mark.asyncio
    async def test_zip_file_path_multiple_items_with_individual_uids(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """AC-004: 複数アイテムがある場合、各ファイルが個別のuidで命名される."""
        # Arrange
        item_1 = create_mock_order_item(
            item_id="oi-1",
            product_name="Tシャツ",
            thumbnail_image_url="https://example.com/thumb1.png",
            uid="MFG-001",
        )
        item_2 = create_mock_order_item(
            item_id="oi-2",
            product_name="Tシャツ",
            thumbnail_image_url="https://example.com/thumb2.png",
            uid="MFG-002",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_1, item_2],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: Two files with individual uid naming
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = sorted(zf.namelist())
            assert len(file_list) == 2
            assert "ORD-001_MFG-001.png" in file_list
            assert "ORD-001_MFG-002.png" in file_list
            # No subdirectories
            for f in file_list:
                assert "/" not in f

    @pytest.mark.asyncio
    async def test_zip_file_extension_from_url(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """拡張子はURLのパスから推定される."""
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-1",
            product_name="Product",
            thumbnail_image_url="https://example.com/images/photo.jpg",
            uid="MFG-001",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[order_item],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/jpeg"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: Extension should be .jpg from URL, flat path format
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            assert file_list[0] == "ORD-001_MFG-001.jpg"

    @pytest.mark.asyncio
    async def test_zip_file_extension_fallback_to_png(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """URLからもContent-Typeからも拡張子が推定できない場合は.pngとする."""
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-1",
            product_name="Product",
            thumbnail_image_url="https://example.com/image?id=123",
            uid="MFG-001",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[order_item],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "application/octet-stream"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes, _ = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: Fallback to .png, flat path format
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            assert file_list[0] == "ORD-001_MFG-001.png"


# ======================================
# AC-009: ZIPファイル名が 配送サムネイル_{YYYYMMDD_HHMMSS}.zip 形式
# ======================================


class TestZipFilenameFormat:
    """AC-009: ZIPファイル名が「配送サムネイル_{YYYYMMDD_HHMMSS}.zip」形式である."""

    @pytest.mark.asyncio
    async def test_zip_filename_matches_expected_pattern(
        self, shipment_service: Any, mock_shipment_repo: Any
    ) -> None:
        """ファイル名が「配送サムネイル_YYYYMMDD_HHMMSS.zip」のパターンに一致する."""
        # Arrange
        order_item = create_mock_order_item(
            item_id="oi-1",
            product_name="Product",
            thumbnail_image_url="https://example.com/thumb.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[order_item],
        )
        shipment_item = create_mock_shipment_item(
            item_id="si-1", order_id="order-1", order=order
        )
        shipment = create_mock_shipment(
            shipment_id="shipment-1", items=[shipment_item]
        )
        mock_shipment_repo.find_by_id.return_value = shipment

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("app.services.shipment_service.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            _, filename = await shipment_service.download_thumbnails(
                shipment_ids=["shipment-1"]
            )

        # Assert: filename pattern
        assert re.match(r"配送サムネイル_\d{8}_\d{6}\.zip", filename), (
            f"Expected filename to match '配送サムネイル_YYYYMMDD_HHMMSS.zip', got '{filename}'"
        )
