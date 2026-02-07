"""Shipment service."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import UploadFile

from app.models.order import OrderStatus
from app.models.shipment import Shipment, ShipmentStatus
from app.repositories.order_repository import OrderRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.schemas.shipment import (
    ShipmentBulkStatusUpdate,
    ShipmentBulkStatusUpdateResponse,
    ShipmentCreate,
    ShipmentItemResponse,
    ShipmentListResponse,
    ShipmentResponse,
    ShipmentStatusUpdate,
    TrackingImportRequest,
)
from app.utils.exceptions import InvalidStatusTransitionError, NotFoundError, ValidationError
from app.utils.file_storage import FileStorage


class ShipmentService:
    """Service for shipment operations."""

    def __init__(
        self,
        shipment_repo: ShipmentRepository,
        order_repo: OrderRepository,
        file_storage: FileStorage,
    ):
        self._shipment_repo = shipment_repo
        self._order_repo = order_repo
        self._file_storage = file_storage

    async def create(self, data: ShipmentCreate) -> ShipmentResponse:
        """Create a new shipment."""
        # Verify all orders exist and get customer info from first order
        first_order = None
        for order_id in data.order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if not order:
                raise ValidationError(f"Order {order_id} not found")
            if order.status != OrderStatus.DELIVERED.value:
                raise ValidationError(f"Order {order_id} is not in delivered status")
            # Check if shipment already exists for this order (prevent duplicates)
            if await self._shipment_repo.exists_for_order(order_id):
                raise ValidationError(f"Order {order_id} already has a shipment")
            if first_order is None:
                first_order = order

        if not first_order:
            raise ValidationError("No valid orders provided")

        # Create shipment
        shipment = await self._shipment_repo.create(
            order_ids=data.order_ids,
            customer_name=first_order.customer_name,
            customer_postal_code=first_order.customer_postal_code,
            customer_address=first_order.customer_address,
            customer_phone=first_order.customer_phone,
        )

        return await self._to_response(shipment)

    async def get_by_id(self, shipment_id: str) -> ShipmentResponse:
        """Get a shipment by ID."""
        shipment = await self._shipment_repo.find_by_id(shipment_id)
        if not shipment:
            raise NotFoundError("Shipment", shipment_id)
        return await self._to_response(shipment)

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        status: ShipmentStatus | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        search: str | None = None,
        tracking_number: str | None = None,
        carrier: str | None = None,
        shipped_from: date | None = None,
        shipped_to: date | None = None,
        delivered_from: date | None = None,
        delivered_to: date | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> ShipmentListResponse:
        """List shipments with pagination and filters."""
        shipments, total = await self._shipment_repo.find_all(
            page=page,
            limit=limit,
            status=status,
            created_from=created_from,
            created_to=created_to,
            search=search,
            tracking_number=tracking_number,
            carrier=carrier,
            shipped_from=shipped_from,
            shipped_to=shipped_to,
            delivered_from=delivered_from,
            delivered_to=delivered_to,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        items = []
        for shipment in shipments:
            items.append(await self._to_response(shipment))

        return ShipmentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    async def update_status(
        self, shipment_id: str, data: ShipmentStatusUpdate
    ) -> ShipmentResponse:
        """Update shipment status."""
        shipment = await self._shipment_repo.find_by_id(shipment_id)
        if not shipment:
            raise NotFoundError("Shipment", shipment_id)

        current_status = ShipmentStatus(shipment.status)
        if not self._is_valid_transition(current_status, data.status):
            raise InvalidStatusTransitionError(current_status.value, data.status.value)

        shipment.status = data.status.value

        if data.tracking_number:
            shipment.tracking_number = data.tracking_number
        if data.carrier:
            shipment.carrier = data.carrier
        if data.note:
            shipment.note = data.note

        # Set timestamps
        if data.status == ShipmentStatus.SHIPPED:
            shipment.shipped_at = datetime.now(timezone.utc)
            # Set delivered_at (配送完了予定日時) if provided, or use default
            if data.delivered_at:
                shipment.delivered_at = data.delivered_at
            # Update related orders to SHIPPED
            for item in shipment.items:
                await self._order_repo.update_status(item.order_id, OrderStatus.SHIPPED)

        await self._shipment_repo.update(shipment)
        return await self._to_response(shipment)

    async def upload_packing_photo(
        self, shipment_id: str, photo: UploadFile
    ) -> ShipmentResponse:
        """Upload packing photo for a shipment."""
        shipment = await self._shipment_repo.find_by_id(shipment_id)
        if not shipment:
            raise NotFoundError("Shipment", shipment_id)

        # Save photo
        path = await self._file_storage.save(photo, f"shipments/{shipment_id}/")
        shipment.packing_photo_path = path

        await self._shipment_repo.update(shipment)
        return await self._to_response(shipment)

    async def import_tracking_numbers(
        self, data: TrackingImportRequest
    ) -> list[ShipmentResponse]:
        """Import tracking numbers from CSV data."""
        results = []
        for item in data.items:
            shipment = await self._shipment_repo.find_by_id(item.shipment_id)
            if shipment:
                shipment.tracking_number = item.tracking_number
                if item.carrier:
                    shipment.carrier = item.carrier
                await self._shipment_repo.update(shipment)
                results.append(await self._to_response(shipment))
        return results

    async def bulk_update_status(
        self, data: ShipmentBulkStatusUpdate
    ) -> ShipmentBulkStatusUpdateResponse:
        """配送ステータスを一括更新（バリデーション付き）"""
        updated_count = 0
        failed_count = 0
        failed_ids = []

        for shipment_id in data.shipment_ids:
            shipment = await self._shipment_repo.find_by_id(shipment_id)
            if not shipment:
                failed_ids.append(shipment_id)
                failed_count += 1
                continue

            current_status = ShipmentStatus(shipment.status)
            if not self._is_valid_transition(current_status, data.status):
                failed_ids.append(shipment_id)
                failed_count += 1
                continue

            shipment.status = data.status.value
            if data.tracking_number:
                shipment.tracking_number = data.tracking_number
            if data.carrier:
                shipment.carrier = data.carrier

            if data.status == ShipmentStatus.SHIPPED:
                shipment.shipped_at = datetime.now(timezone.utc)
                for item in shipment.items:
                    await self._order_repo.update_status(item.order_id, OrderStatus.SHIPPED)

            await self._shipment_repo.update(shipment)
            updated_count += 1

        return ShipmentBulkStatusUpdateResponse(
            updated_count=updated_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
        )

    def _is_valid_transition(
        self, current: ShipmentStatus, target: ShipmentStatus
    ) -> bool:
        """Check if status transition is valid."""
        valid_transitions = {
            ShipmentStatus.PENDING: [ShipmentStatus.READY],
            ShipmentStatus.READY: [ShipmentStatus.SHIPPED],
            ShipmentStatus.SHIPPED: [],  # 最終ステータス
        }
        return target in valid_transitions.get(current, [])

    async def _to_response(self, shipment: Shipment) -> ShipmentResponse:
        """Convert shipment model to response schema."""
        items = []
        for item in shipment.items:
            order = await self._order_repo.find_by_id(item.order_id)
            items.append(ShipmentItemResponse(
                id=item.id,
                order_id=item.order_id,
                order_number=order.order_number if order else None,
                product_name=order.product_name if order else None,
            ))

        return ShipmentResponse(
            id=shipment.id,
            status=ShipmentStatus(shipment.status),
            tracking_number=shipment.tracking_number,
            carrier=shipment.carrier,
            packing_photo_path=shipment.packing_photo_path,
            shipped_at=shipment.shipped_at,
            delivered_at=shipment.delivered_at,
            note=shipment.note,
            customer_name=shipment.customer_name,
            customer_postal_code=shipment.customer_postal_code,
            customer_address=shipment.customer_address,
            customer_phone=shipment.customer_phone,
            items=items,
            created_at=shipment.created_at,
            updated_at=shipment.updated_at,
        )
