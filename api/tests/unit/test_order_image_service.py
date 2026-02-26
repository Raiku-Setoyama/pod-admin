"""Unit tests for OrderImageService.

FEAT-0018: 受注イメージ画像ZIPダウンロード
Tests cover:
- AC-004: design_image_urlがnullのOrderItemはスキップされる
- AC-005: 画像取得失敗時はスキップ+ログ記録
- AC-006: 全件失敗時は404エラー
- AC-007: 存在しない受注IDはスキップ
- AC-008: ZIP内ファイル名の形式
- AC-009: 空のorder_idsで422エラー

NOTE: These tests are written in TDD Red phase - the implementation does not exist yet.
Tests will fail until the implementation is completed.
"""

import io
import logging
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.order import Order, OrderItem, OrderStatus

# Direct import - will cause ImportError (test failure) until implementation exists
from app.services.order_image_service import OrderImageService
from app.schemas.order import OrderImageDownloadRequest


# ======================================
# Fixtures
# ======================================


@pytest.fixture
def mock_order_repo():
    """Mock order repository."""
    return AsyncMock()


@pytest.fixture
def order_image_service(mock_order_repo):
    """Create OrderImageService with mocked dependencies."""
    return OrderImageService(order_repo=mock_order_repo)


# ======================================
# Helpers
# ======================================


def create_mock_order(
    order_id: str = "order-123",
    order_number: str = "ORD-001",
    status: str = OrderStatus.ORDERED.value,
    items: list | None = None,
) -> MagicMock:
    """Create a mock Order with OrderItems."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.order_number = order_number
    order.status = status
    order.items = items or []
    return order


def create_mock_order_item(
    item_id: str = "item-123",
    product_name: str = "Tshirt M White",
    design_image_url: str | None = "https://example.com/designs/design1.png",
    thumbnail_image_url: str | None = None,
) -> MagicMock:
    """Create a mock OrderItem."""
    item = MagicMock(spec=OrderItem)
    item.id = item_id
    item.product_name = product_name
    item.design_image_url = design_image_url
    item.thumbnail_image_url = thumbnail_image_url
    return item


# ======================================
# AC-004: design_image_urlがnullのOrderItemはスキップされる
# ======================================


class TestSkipNullDesignImageUrl:
    """AC-004: design_image_urlがnullのOrderItemはスキップされる."""

    async def test_null_design_image_url_items_are_skipped(
        self, order_image_service, mock_order_repo
    ):
        """design_image_urlがnullのアイテムはスキップされ、画像を持つアイテムのみがZIPに含まれる."""
        # Arrange
        item_with_image = create_mock_order_item(
            item_id="item-1",
            product_name="Tshirt M White",
            design_image_url="https://example.com/design1.png",
        )
        item_without_image = create_mock_order_item(
            item_id="item-2",
            product_name="Tshirt L Black",
            design_image_url=None,
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_with_image, item_without_image],
        )
        mock_order_repo.find_by_id.return_value = order

        # Mock httpx image fetch
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake-image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes = await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )

        # Assert: ZIP should only contain one file (the item with image)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1

    async def test_all_items_null_design_image_url_raises_error(
        self, order_image_service, mock_order_repo
    ):
        """全てのアイテムのdesign_image_urlがnullの場合、エラーが発生する."""
        # Arrange
        item_null_1 = create_mock_order_item(
            item_id="item-1", design_image_url=None
        )
        item_null_2 = create_mock_order_item(
            item_id="item-2", design_image_url=None
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_null_1, item_null_2],
        )
        mock_order_repo.find_by_id.return_value = order

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )
        assert exc_info.value.status_code == 404


# ======================================
# AC-005: 画像取得失敗時はスキップ+ログ記録
# ======================================


class TestImageFetchFailureSkipAndLog:
    """AC-005: 画像URLからの取得に失敗した場合はスキップしてログに記録する."""

    async def test_failed_image_fetch_is_skipped_and_logged(
        self, order_image_service, mock_order_repo, caplog
    ):
        """取得失敗した画像はスキップされ、ログに警告が記録される."""
        # Arrange
        item_good = create_mock_order_item(
            item_id="item-1",
            product_name="Good Product",
            design_image_url="https://example.com/good.png",
        )
        item_bad = create_mock_order_item(
            item_id="item-2",
            product_name="Bad Product",
            design_image_url="https://example.com/bad.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_good, item_bad],
        )
        mock_order_repo.find_by_id.return_value = order

        # Mock: first request succeeds, second returns 404
        mock_response_good = MagicMock()
        mock_response_good.status_code = 200
        mock_response_good.content = b"good-image-data"
        mock_response_good.headers = {"content-type": "image/png"}

        mock_response_bad = MagicMock()
        mock_response_bad.status_code = 404
        mock_response_bad.content = b""

        async def side_effect_get(url, **kwargs):
            if "good" in url:
                return mock_response_good
            return mock_response_bad

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = side_effect_get
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            with caplog.at_level(logging.WARNING):
                zip_bytes = await order_image_service.collect_and_build_zip(
                    order_ids=["order-1"]
                )

        # Assert: Only one file in ZIP (the good one)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1

        # Assert: Warning logged for failed fetch
        assert any("bad.png" in record.message or "bad" in record.message.lower()
                    for record in caplog.records
                    if record.levelno >= logging.WARNING)

    async def test_timeout_on_image_fetch_is_skipped(
        self, order_image_service, mock_order_repo
    ):
        """タイムアウトした画像取得はスキップされる."""
        import httpx

        # Arrange
        item_timeout = create_mock_order_item(
            item_id="item-1",
            product_name="Timeout Product",
            design_image_url="https://example.com/timeout.png",
        )
        item_good = create_mock_order_item(
            item_id="item-2",
            product_name="Good Product",
            design_image_url="https://example.com/good.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_timeout, item_good],
        )
        mock_order_repo.find_by_id.return_value = order

        mock_response_good = MagicMock()
        mock_response_good.status_code = 200
        mock_response_good.content = b"good-image-data"
        mock_response_good.headers = {"content-type": "image/png"}

        async def side_effect_get(url, **kwargs):
            if "timeout" in url:
                raise httpx.TimeoutException("Connection timed out")
            return mock_response_good

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = side_effect_get
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes = await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )

        # Assert: Only the good image is in ZIP
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert len(zf.namelist()) == 1


# ======================================
# AC-006: 全件失敗時は404エラー
# ======================================


class TestAllFetchFailuresReturn404:
    """AC-006: 全ての画像取得に失敗した場合は404エラーを返す."""

    async def test_all_images_fetch_failed_returns_404(
        self, order_image_service, mock_order_repo
    ):
        """全ての画像URLからの取得に失敗した場合、404エラーが返される."""
        # Arrange
        item_bad_1 = create_mock_order_item(
            item_id="item-1",
            design_image_url="https://example.com/bad1.png",
        )
        item_bad_2 = create_mock_order_item(
            item_id="item-2",
            design_image_url="https://example.com/bad2.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_bad_1, item_bad_2],
        )
        mock_order_repo.find_by_id.return_value = order

        mock_response_bad = MagicMock()
        mock_response_bad.status_code = 500
        mock_response_bad.content = b""

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response_bad
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act & Assert
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await order_image_service.collect_and_build_zip(
                    order_ids=["order-1"]
                )
            assert exc_info.value.status_code == 404

    async def test_no_design_image_urls_at_all_returns_404(
        self, order_image_service, mock_order_repo
    ):
        """design_image_urlを持つアイテムが0件の場合は404エラーが返される."""
        # Arrange
        item_null = create_mock_order_item(
            item_id="item-1",
            design_image_url=None,
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_null],
        )
        mock_order_repo.find_by_id.return_value = order

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )
        assert exc_info.value.status_code == 404


# ======================================
# AC-007: 存在しない受注IDはスキップ
# ======================================


class TestNonExistentOrderIdsSkipped:
    """AC-007: 存在しない受注IDが含まれている場合、存在する受注のみ処理される."""

    async def test_nonexistent_order_ids_are_skipped(
        self, order_image_service, mock_order_repo
    ):
        """存在しない受注IDはスキップされ、存在する受注の画像のみがZIPに含まれる."""
        # Arrange
        item = create_mock_order_item(
            item_id="item-1",
            product_name="Valid Product",
            design_image_url="https://example.com/valid.png",
        )
        valid_order = create_mock_order(
            order_id="order-valid",
            order_number="ORD-VALID",
            items=[item],
        )

        async def find_by_id(order_id):
            if order_id == "order-valid":
                return valid_order
            return None  # Not found

        mock_order_repo.find_by_id.side_effect = find_by_id

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes = await order_image_service.collect_and_build_zip(
                order_ids=["order-valid", "order-nonexistent"]
            )

        # Assert: ZIP contains files only from the valid order
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            # File should be under the valid order's directory
            assert any("ORD-VALID" in f for f in file_list)

    async def test_all_nonexistent_order_ids_returns_404(
        self, order_image_service, mock_order_repo
    ):
        """全ての受注IDが存在しない場合は404エラーが返される."""
        # Arrange
        mock_order_repo.find_by_id.return_value = None

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await order_image_service.collect_and_build_zip(
                order_ids=["nonexistent-1", "nonexistent-2"]
            )
        assert exc_info.value.status_code == 404


# ======================================
# AC-008: ZIP内ファイル名の形式
# ======================================


class TestZipFileNameFormat:
    """AC-008: ZIPファイル内のファイル名が注文番号と商品名で構成される."""

    async def test_zip_file_path_format(
        self, order_image_service, mock_order_repo
    ):
        """ZIP内のファイルパスが「{注文番号}/{商品名}_{連番}.{拡張子}」形式になっている."""
        # Arrange
        item = create_mock_order_item(
            item_id="item-1",
            product_name="Tシャツ Mサイズ 白",
            design_image_url="https://example.com/design1.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item],
        )
        mock_order_repo.find_by_id.return_value = order

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes = await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )

        # Assert
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            # Format: ORD-001/Tシャツ Mサイズ 白_1.png
            file_path = file_list[0]
            assert file_path.startswith("ORD-001/")
            assert "Tシャツ Mサイズ 白" in file_path
            assert "_1." in file_path
            assert file_path.endswith(".png")

    async def test_zip_file_path_with_multiple_items_has_sequential_numbers(
        self, order_image_service, mock_order_repo
    ):
        """同一注文の複数アイテムには連番が振られる."""
        # Arrange
        item_1 = create_mock_order_item(
            item_id="item-1",
            product_name="Tシャツ",
            design_image_url="https://example.com/design1.png",
        )
        item_2 = create_mock_order_item(
            item_id="item-2",
            product_name="Tシャツ",
            design_image_url="https://example.com/design2.png",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item_1, item_2],
        )
        mock_order_repo.find_by_id.return_value = order

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/png"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes = await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )

        # Assert: Two files with sequential numbers
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = sorted(zf.namelist())
            assert len(file_list) == 2
            assert "_1." in file_list[0]
            assert "_2." in file_list[1]

    async def test_zip_file_extension_from_url(
        self, order_image_service, mock_order_repo
    ):
        """拡張子はURLのパスから推定される."""
        # Arrange
        item = create_mock_order_item(
            item_id="item-1",
            product_name="Product",
            design_image_url="https://example.com/images/photo.jpg",
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item],
        )
        mock_order_repo.find_by_id.return_value = order

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/jpeg"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes = await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )

        # Assert: Extension should be .jpg from URL
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            assert file_list[0].endswith(".jpg")

    async def test_zip_file_extension_fallback_to_content_type(
        self, order_image_service, mock_order_repo
    ):
        """URLから拡張子が推定できない場合はContent-Typeから判定する."""
        # Arrange
        item = create_mock_order_item(
            item_id="item-1",
            product_name="Product",
            design_image_url="https://example.com/image?id=123",  # No extension in URL
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item],
        )
        mock_order_repo.find_by_id.return_value = order

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "image/jpeg"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes = await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )

        # Assert: Extension from Content-Type
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            assert file_list[0].endswith(".jpg") or file_list[0].endswith(".jpeg")

    async def test_zip_file_extension_fallback_to_png(
        self, order_image_service, mock_order_repo
    ):
        """URLからもContent-Typeからも拡張子が推定できない場合は.pngとする."""
        # Arrange
        item = create_mock_order_item(
            item_id="item-1",
            product_name="Product",
            design_image_url="https://example.com/image?id=123",  # No extension
        )
        order = create_mock_order(
            order_id="order-1",
            order_number="ORD-001",
            items=[item],
        )
        mock_order_repo.find_by_id.return_value = order

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"image-data"
        mock_response.headers = {"content-type": "application/octet-stream"}  # Unknown type

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Act
            zip_bytes = await order_image_service.collect_and_build_zip(
                order_ids=["order-1"]
            )

        # Assert: Fallback to .png
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            assert len(file_list) == 1
            assert file_list[0].endswith(".png")


# ======================================
# AC-009: 空のorder_idsで422エラー
# ======================================


class TestEmptyOrderIdsValidation:
    """AC-009: order_idsが空の場合は422エラーを返す."""

    def test_empty_order_ids_validation_error(self):
        """空のorder_idsリストはバリデーションエラーになる."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            OrderImageDownloadRequest(order_ids=[])

    def test_valid_order_ids_accepted(self):
        """1件以上のorder_idsは受け入れられる."""
        request = OrderImageDownloadRequest(order_ids=["order-1"])
        assert request.order_ids == ["order-1"]

    def test_multiple_order_ids_accepted(self):
        """複数のorder_idsも受け入れられる."""
        request = OrderImageDownloadRequest(order_ids=["order-1", "order-2", "order-3"])
        assert len(request.order_ids) == 3
