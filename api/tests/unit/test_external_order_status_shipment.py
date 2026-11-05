"""Unit tests for shipment info in the external order status API.

Issue #165: GET /api/v1/external/orders/{order_number}/status に配送情報を返す。
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.order import Order, OrderStatus
from app.models.shipment import Shipment
from app.services.external_service import ExternalService


def create_mock_order(status: str = OrderStatus.SHIPPED.value) -> MagicMock:
    order = MagicMock(spec=Order)
    order.id = "order-uuid-001"
    order.order_number = "ORD-001"
    order.status = status
    order.ordered_at = datetime(2026, 3, 1, 1, 0, tzinfo=UTC)
    order.updated_at = datetime(2026, 3, 5, 6, 0, tzinfo=UTC)
    return order


def create_mock_shipment(
    tracking_number: str | None = "1234-5678-9012",
    carrier: str | None = "ヤマト運輸",
    shipped_at: datetime | None = datetime(2026, 3, 5, 6, 0, tzinfo=UTC),
) -> MagicMock:
    shipment = MagicMock(spec=Shipment)
    shipment.tracking_number = tracking_number
    shipment.carrier = carrier
    shipment.shipped_at = shipped_at
    return shipment


@pytest.fixture
def mock_order_repo() -> Any:
    return AsyncMock()


@pytest.fixture
def mock_shipment_repo() -> Any:
    return AsyncMock()


@pytest.fixture
def external_service(mock_order_repo: Any, mock_shipment_repo: Any) -> ExternalService:
    return ExternalService(
        product_repo=AsyncMock(),
        order_repo=mock_order_repo,
        shipment_repo=mock_shipment_repo,
    )


class TestOrderStatusShipment:
    """get_order_status_by_order_number が配送情報を返すこと."""

    @pytest.mark.asyncio
    async def test_returns_shipment_with_tracking_number(
        self, external_service: ExternalService, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        order = create_mock_order()
        mock_order_repo.find_by_order_number.return_value = order
        mock_shipment_repo.find_latest_tracked_for_order.return_value = create_mock_shipment()

        result = await external_service.get_order_status_by_order_number("ORD-001")

        mock_shipment_repo.find_latest_tracked_for_order.assert_called_once_with(order.id)
        assert result.shipment is not None
        assert result.shipment.carrier == "ヤマト運輸"
        assert result.shipment.tracking_number == "1234-5678-9012"
        assert result.shipment.shipped_at == datetime(2026, 3, 5, 6, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_shipment_is_null_without_tracked_shipment(
        self, external_service: ExternalService, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        mock_order_repo.find_by_order_number.return_value = create_mock_order(
            status=OrderStatus.MANUFACTURING.value
        )
        mock_shipment_repo.find_latest_tracked_for_order.return_value = None

        result = await external_service.get_order_status_by_order_number("ORD-001")

        assert result.shipment is None
        assert result.model_dump(mode="json")["shipment"] is None

    @pytest.mark.asyncio
    async def test_unshipped_and_carrier_unknown_are_null(
        self, external_service: ExternalService, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        """伝票番号は登録済みでも未発送なら shipped_at は null、運送会社未登録なら carrier は null."""
        mock_order_repo.find_by_order_number.return_value = create_mock_order(
            status=OrderStatus.DELIVERED.value
        )
        mock_shipment_repo.find_latest_tracked_for_order.return_value = create_mock_shipment(
            carrier=None, shipped_at=None
        )

        result = await external_service.get_order_status_by_order_number("ORD-001")

        assert result.shipment is not None
        assert result.shipment.tracking_number == "1234-5678-9012"
        assert result.shipment.carrier is None
        assert result.shipment.shipped_at is None

    @pytest.mark.asyncio
    async def test_existing_fields_unchanged(
        self, external_service: ExternalService, mock_order_repo: Any, mock_shipment_repo: Any
    ) -> None:
        order = create_mock_order(status=OrderStatus.PREPARING_ORDER.value)
        mock_order_repo.find_by_order_number.return_value = order
        mock_shipment_repo.find_latest_tracked_for_order.return_value = None

        result = await external_service.get_order_status_by_order_number("ORD-001")

        assert result.order_number == "ORD-001"
        assert result.status == OrderStatus.PREPARING_ORDER
        assert result.ordered_at == order.ordered_at
        assert result.updated_at == order.updated_at
