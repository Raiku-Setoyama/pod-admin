"""Unit tests for external order cancellation feature.

FEAT-0023: External sales site can cancel orders via API.
Tests cover OrderStatus.CANCELLED enum, OrderCancelResponse schema,
and ExternalService.cancel_order service logic.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderStatus
from app.utils.exceptions import AppException, NotFoundError

# ============================================================
# AC-001: OrderStatus enum に CANCELLED が存在し、値が "cancelled"
# ============================================================


class TestOrderStatusCancelled:
    """Tests for OrderStatus.CANCELLED enum value."""

    def test_cancelled_enum_exists(self) -> None:
        """AC-001: OrderStatus.CANCELLED が存在する."""
        assert hasattr(OrderStatus, "CANCELLED")

    def test_cancelled_enum_value(self) -> None:
        """AC-001: OrderStatus.CANCELLED の値が 'cancelled' である."""
        assert OrderStatus.CANCELLED.value == "cancelled"

    def test_cancelled_is_str_enum(self) -> None:
        """AC-001: OrderStatus.CANCELLED は str として使える."""
        assert isinstance(OrderStatus.CANCELLED, str)
        assert OrderStatus.CANCELLED.value == "cancelled"


# ============================================================
# AC-002: OrderCancelResponse スキーマのフィールド検証
# ============================================================


class TestOrderCancelResponseSchema:
    """Tests for OrderCancelResponse schema."""

    def test_schema_has_required_fields(self) -> None:
        """AC-002: OrderCancelResponse が order_number, status, cancelled_at を持つ."""
        from app.schemas.external import OrderCancelResponse

        now = datetime.now(UTC)
        response = OrderCancelResponse(
            order_number="ORD-001",
            status=OrderStatus.CANCELLED,
            cancelled_at=now,
        )

        assert response.order_number == "ORD-001"
        assert response.status == OrderStatus.CANCELLED
        assert response.cancelled_at == now

    def test_schema_order_number_is_str(self) -> None:
        """AC-002: order_number は str 型."""
        from app.schemas.external import OrderCancelResponse

        response = OrderCancelResponse(
            order_number="TEST-123",
            status=OrderStatus.CANCELLED,
            cancelled_at=datetime.now(UTC),
        )
        assert isinstance(response.order_number, str)

    def test_schema_status_is_order_status(self) -> None:
        """AC-002: status は OrderStatus 型."""
        from app.schemas.external import OrderCancelResponse

        response = OrderCancelResponse(
            order_number="TEST-123",
            status=OrderStatus.CANCELLED,
            cancelled_at=datetime.now(UTC),
        )
        assert isinstance(response.status, OrderStatus)

    def test_schema_cancelled_at_is_datetime(self) -> None:
        """AC-002: cancelled_at は datetime 型."""
        from app.schemas.external import OrderCancelResponse

        now = datetime.now(UTC)
        response = OrderCancelResponse(
            order_number="TEST-123",
            status=OrderStatus.CANCELLED,
            cancelled_at=now,
        )
        assert isinstance(response.cancelled_at, datetime)


# ============================================================
# Helper: mock order factory
# ============================================================


def create_mock_order(
    order_id: str = "order-123",
    order_number: str = "ORD-001",
    status: str = OrderStatus.ORDERED.value,
) -> MagicMock:
    """Create a mock order object for unit testing."""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.order_number = order_number
    order.status = status
    order.updated_at = datetime.now(UTC)
    return order


# ============================================================
# Helper: ExternalService fixture with mocked repos
# ============================================================


@pytest.fixture
def mock_order_repo() -> Any:
    """Mock order repository."""
    return AsyncMock()


@pytest.fixture
def mock_product_repo() -> Any:
    """Mock product repository."""
    return AsyncMock()


@pytest.fixture
def external_service(mock_product_repo: Any, mock_order_repo: Any) -> Any:
    """Create ExternalService with mocked dependencies."""
    from app.services.external_service import ExternalService

    return ExternalService(product_repo=mock_product_repo, order_repo=mock_order_repo)


# ============================================================
# AC-003: 正常系 - ordered -> cancelled の更新
# ============================================================


class TestCancelOrderSuccess:
    """Tests for successful order cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_ordered_order_success(
        self, external_service: Any, mock_order_repo: Any
    ) -> None:
        """AC-003: ordered ステータスの注文を cancelled に更新できる."""
        # Arrange
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_order_number.return_value = order

        updated_order = create_mock_order(status=OrderStatus.CANCELLED.value)
        mock_order_repo.update_status.return_value = updated_order

        # Act
        await external_service.cancel_order("ORD-001")

        # Assert
        mock_order_repo.find_by_order_number.assert_called_once_with("ORD-001")
        mock_order_repo.update_status.assert_called_once_with(
            order.id, OrderStatus.CANCELLED
        )

    @pytest.mark.asyncio
    async def test_cancel_order_returns_cancel_response(
        self, external_service: Any, mock_order_repo: Any
    ) -> None:
        """AC-003: キャンセル成功時に OrderCancelResponse が返される."""
        from app.schemas.external import OrderCancelResponse

        # Arrange
        order = create_mock_order(status=OrderStatus.ORDERED.value)
        mock_order_repo.find_by_order_number.return_value = order

        updated_order = create_mock_order(status=OrderStatus.CANCELLED.value)
        mock_order_repo.update_status.return_value = updated_order

        # Act
        result = await external_service.cancel_order("ORD-001")

        # Assert
        assert isinstance(result, OrderCancelResponse)
        assert result.order_number == "ORD-001"
        assert result.status == OrderStatus.CANCELLED


# ============================================================
# AC-004: 存在しない注文 -> NotFoundError (404)
# ============================================================


class TestCancelOrderNotFound:
    """Tests for cancelling non-existent orders."""

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order_raises_not_found(
        self, external_service: Any, mock_order_repo: Any
    ) -> None:
        """AC-004: 存在しない order_number を指定すると NotFoundError が発生."""
        # Arrange
        mock_order_repo.find_by_order_number.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await external_service.cancel_order("NONEXISTENT-001")

        assert exc_info.value.status_code == 404


# ============================================================
# AC-005: manufacturing の注文 -> ConflictError (409)
# ============================================================


class TestCancelManufacturingOrder:
    """Tests for cancelling manufacturing orders."""

    @pytest.mark.asyncio
    async def test_cancel_manufacturing_order_raises_conflict(
        self, external_service: Any, mock_order_repo: Any
    ) -> None:
        """AC-005: manufacturing ステータスの注文を取り消すと 409 エラー."""
        # Arrange
        order = create_mock_order(status=OrderStatus.MANUFACTURING.value)
        mock_order_repo.find_by_order_number.return_value = order

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await external_service.cancel_order("ORD-001")

        assert exc_info.value.status_code == 409


# ============================================================
# AC-006: shipped の注文 -> ConflictError (409)
# ============================================================


class TestCancelShippedOrder:
    """Tests for cancelling shipped orders."""

    @pytest.mark.asyncio
    async def test_cancel_shipped_order_raises_conflict(
        self, external_service: Any, mock_order_repo: Any
    ) -> None:
        """AC-006: shipped ステータスの注文を取り消すと 409 エラー."""
        # Arrange
        order = create_mock_order(status=OrderStatus.SHIPPED.value)
        mock_order_repo.find_by_order_number.return_value = order

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await external_service.cancel_order("ORD-001")

        assert exc_info.value.status_code == 409


# ============================================================
# AC-007: delivered の注文 -> ConflictError (409)
# ============================================================


class TestCancelDeliveredOrder:
    """Tests for cancelling delivered orders."""

    @pytest.mark.asyncio
    async def test_cancel_delivered_order_raises_conflict(
        self, external_service: Any, mock_order_repo: Any
    ) -> None:
        """AC-007: delivered ステータスの注文を取り消すと 409 エラー."""
        # Arrange
        order = create_mock_order(status=OrderStatus.DELIVERED.value)
        mock_order_repo.find_by_order_number.return_value = order

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await external_service.cancel_order("ORD-001")

        assert exc_info.value.status_code == 409


# ============================================================
# Additional edge case: cancelled order -> ConflictError (409)
# ============================================================


class TestCancelAlreadyCancelledOrder:
    """Tests for cancelling already cancelled orders."""

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_order_raises_conflict(
        self, external_service: Any, mock_order_repo: Any
    ) -> None:
        """既にキャンセル済みの注文を再度キャンセルすると 409 エラー."""
        # Arrange
        order = create_mock_order(status=OrderStatus.CANCELLED.value)
        mock_order_repo.find_by_order_number.return_value = order

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await external_service.cancel_order("ORD-001")

        assert exc_info.value.status_code == 409
