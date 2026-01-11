"""Manufacturer service."""

from app.models.manufacturer import Manufacturer
from app.repositories.manufacturer_repository import ManufacturerRepository
from app.schemas.manufacturer import (
    ManufacturerCreate,
    ManufacturerListResponse,
    ManufacturerResponse,
    ManufacturerUpdate,
)
from app.utils.exceptions import DuplicateError, ManufacturerNotFoundError, ValidationError
from app.utils.security import hash_password


class ManufacturerService:
    """Service for manufacturer operations."""

    def __init__(self, manufacturer_repo: ManufacturerRepository):
        self._manufacturer_repo = manufacturer_repo

    async def create(self, data: ManufacturerCreate) -> ManufacturerResponse:
        """Create a new manufacturer."""
        # Check for duplicate name
        existing = await self._manufacturer_repo.find_by_name(data.name)
        if existing:
            raise DuplicateError("Manufacturer", "name", data.name)

        # Validate password for portal sharing method
        if data.sharing_method == "portal" and not data.password:
            raise ValidationError("Password is required for portal sharing method")

        # Hash password if provided
        password_hash = None
        if data.password:
            password_hash = hash_password(data.password)

        manufacturer = Manufacturer(
            name=data.name,
            email=data.email,
            phone=data.phone,
            supported_products=[p.value for p in data.supported_products],
            unit_prices=data.unit_prices,
            lead_time_days=data.lead_time_days,
            daily_order_limit=data.daily_order_limit,
            sharing_method=data.sharing_method,
            password_hash=password_hash,
        )

        manufacturer = await self._manufacturer_repo.create(manufacturer)
        return self._to_response(manufacturer)

    async def get_by_id(self, manufacturer_id: str) -> ManufacturerResponse:
        """Get a manufacturer by ID."""
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(manufacturer_id)
        return self._to_response(manufacturer)

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> ManufacturerListResponse:
        """List manufacturers with pagination and filters."""
        manufacturers, total = await self._manufacturer_repo.find_all(
            page=page,
            limit=limit,
            is_active=is_active,
            search=search,
        )

        return ManufacturerListResponse(
            items=[self._to_response(m) for m in manufacturers],
            total=total,
            page=page,
            limit=limit,
        )

    async def update(
        self, manufacturer_id: str, data: ManufacturerUpdate
    ) -> ManufacturerResponse:
        """Update a manufacturer."""
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(manufacturer_id)

        # Check for duplicate name if being changed
        if data.name and data.name != manufacturer.name:
            existing = await self._manufacturer_repo.find_by_name(data.name)
            if existing:
                raise DuplicateError("Manufacturer", "name", data.name)

        # Update fields
        update_data = data.model_dump(exclude_unset=True, exclude={"password"})
        for field, value in update_data.items():
            if field == "supported_products" and value:
                setattr(manufacturer, field, [p.value for p in value])
            else:
                setattr(manufacturer, field, value)

        # Update password if provided
        if data.password:
            manufacturer.password_hash = hash_password(data.password)

        manufacturer = await self._manufacturer_repo.update(manufacturer)
        return self._to_response(manufacturer)

    async def delete(self, manufacturer_id: str) -> None:
        """Delete a manufacturer."""
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(manufacturer_id)
        await self._manufacturer_repo.delete(manufacturer)

    def _to_response(self, manufacturer: Manufacturer) -> ManufacturerResponse:
        """Convert manufacturer model to response schema."""
        return ManufacturerResponse(
            id=manufacturer.id,
            name=manufacturer.name,
            email=manufacturer.email,
            phone=manufacturer.phone,
            supported_products=manufacturer.supported_products,
            unit_prices=manufacturer.unit_prices,
            lead_time_days=manufacturer.lead_time_days,
            daily_order_limit=manufacturer.daily_order_limit,
            sharing_method=manufacturer.sharing_method,
            is_active=manufacturer.is_active,
            created_at=manufacturer.created_at,
            updated_at=manufacturer.updated_at,
        )
