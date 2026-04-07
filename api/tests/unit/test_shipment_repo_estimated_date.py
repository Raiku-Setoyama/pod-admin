"""Test ShipmentRepository.create with estimated_shipping_date."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.shipment_repository import ShipmentRepository


@pytest.mark.asyncio
async def test_create_sets_estimated_shipping_date():
    """Shipment作成時にestimated_shipping_dateがセットされる."""
    db = AsyncMock()
    repo = ShipmentRepository(db)

    mock_shipment = MagicMock()
    mock_shipment.id = "ship-1"

    with patch.object(repo, "find_by_id", return_value=mock_shipment):
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        created_shipments = []

        def capture_add(obj):
            from app.models.shipment import Shipment
            if isinstance(obj, Shipment):
                created_shipments.append(obj)

        db.add.side_effect = capture_add

        await repo.create(
            order_ids=["order-1"],
            estimated_shipping_date=date(2026, 4, 15),
        )

        assert len(created_shipments) == 1
        assert created_shipments[0].estimated_shipping_date == date(2026, 4, 15)


@pytest.mark.asyncio
async def test_create_without_estimated_shipping_date():
    """estimated_shipping_dateがNoneの場合もShipmentが作成される."""
    db = AsyncMock()
    repo = ShipmentRepository(db)

    mock_shipment = MagicMock()
    mock_shipment.id = "ship-1"

    with patch.object(repo, "find_by_id", return_value=mock_shipment):
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        created_shipments = []

        def capture_add(obj):
            from app.models.shipment import Shipment
            if isinstance(obj, Shipment):
                created_shipments.append(obj)

        db.add.side_effect = capture_add

        await repo.create(order_ids=["order-1"])

        assert len(created_shipments) == 1
        assert created_shipments[0].estimated_shipping_date is None
