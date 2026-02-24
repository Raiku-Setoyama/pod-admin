"""OrderSource service."""

from app.models.order_source import OrderSource
from app.repositories.order_source_repository import OrderSourceRepository
from app.schemas.order_source import (
    OrderSourceCreate,
    OrderSourceListResponse,
    OrderSourceResponse,
    OrderSourceUpdate,
)
from app.utils.exceptions import DuplicateError, OrderSourceNotFoundError


class OrderSourceService:
    """Service for order source operations."""

    def __init__(self, order_source_repo: OrderSourceRepository):
        self._order_source_repo = order_source_repo

    async def create(self, data: OrderSourceCreate) -> OrderSourceResponse:
        """Create a new order source."""
        # Check for duplicate code
        existing_by_code = await self._order_source_repo.find_by_code(data.code)
        if existing_by_code:
            raise DuplicateError("OrderSource", "code", data.code)

        # Check for duplicate api_key
        existing_by_api_key = await self._order_source_repo.find_by_api_key(data.api_key)
        if existing_by_api_key:
            raise DuplicateError("OrderSource", "api_key", data.api_key)

        order_source = OrderSource(
            code=data.code,
            name=data.name,
            api_key=data.api_key,
            phone=data.phone,
            postal_code=data.postal_code,
            address_prefecture=data.address_prefecture,
            address_city=data.address_city,
            address_building=data.address_building,
        )

        order_source = await self._order_source_repo.create(order_source)
        return self._to_response(order_source)

    async def get_by_id(self, order_source_id: str) -> OrderSourceResponse:
        """Get an order source by ID."""
        order_source = await self._order_source_repo.find_by_id(order_source_id)
        if not order_source:
            raise OrderSourceNotFoundError(order_source_id)
        return self._to_response(order_source)

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> OrderSourceListResponse:
        """List order sources with pagination and filters."""
        order_sources, total = await self._order_source_repo.find_all(
            page=page,
            limit=limit,
            is_active=is_active,
        )

        return OrderSourceListResponse(
            items=[self._to_response(s) for s in order_sources],
            total=total,
            page=page,
            limit=limit,
        )

    async def update(
        self, order_source_id: str, data: OrderSourceUpdate
    ) -> OrderSourceResponse:
        """Update an order source."""
        order_source = await self._order_source_repo.find_by_id(order_source_id)
        if not order_source:
            raise OrderSourceNotFoundError(order_source_id)

        # Check for duplicate code if being changed
        if data.code and data.code != order_source.code:
            existing = await self._order_source_repo.find_by_code(data.code)
            if existing:
                raise DuplicateError("OrderSource", "code", data.code)

        # Check for duplicate api_key if being changed
        if data.api_key and data.api_key != order_source.api_key:
            existing = await self._order_source_repo.find_by_api_key(data.api_key)
            if existing:
                raise DuplicateError("OrderSource", "api_key", data.api_key)

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(order_source, field, value)

        order_source = await self._order_source_repo.update(order_source)
        return self._to_response(order_source)

    async def delete(self, order_source_id: str) -> None:
        """Delete an order source."""
        order_source = await self._order_source_repo.find_by_id(order_source_id)
        if not order_source:
            raise OrderSourceNotFoundError(order_source_id)
        await self._order_source_repo.delete(order_source)

    def _to_response(self, order_source: OrderSource) -> OrderSourceResponse:
        """Convert order source model to response schema."""
        return OrderSourceResponse(
            id=order_source.id,
            code=order_source.code,
            name=order_source.name,
            api_key=order_source.api_key,
            phone=order_source.phone,
            postal_code=order_source.postal_code,
            address_prefecture=order_source.address_prefecture,
            address_city=order_source.address_city,
            address_building=order_source.address_building,
            is_active=order_source.is_active,
            created_at=order_source.created_at,
            updated_at=order_source.updated_at,
        )
