"""Manufacturer portal service."""

from app.models.manufacturer import Manufacturer
from app.repositories.manufacturer_repository import ManufacturerRepository
from app.schemas.auth import TokenResponse
from app.schemas.manufacturer_portal import ManufacturerProfileUpdate
from app.utils.exceptions import NotFoundError, UnauthorizedError
from app.utils.security import create_access_token, create_refresh_token, verify_password


class ManufacturerPortalService:
    """Service for manufacturer portal operations."""

    def __init__(self, manufacturer_repo: ManufacturerRepository):
        self._manufacturer_repo = manufacturer_repo

    async def login(self, email: str, password: str) -> tuple[TokenResponse, Manufacturer]:
        """Authenticate manufacturer and return tokens."""
        manufacturer = await self._manufacturer_repo.find_by_email(email)

        if not manufacturer:
            raise UnauthorizedError("Invalid email or password")

        if not manufacturer.password_hash:
            raise UnauthorizedError("Password not set for this manufacturer")

        if not verify_password(password, manufacturer.password_hash):
            raise UnauthorizedError("Invalid email or password")

        if not manufacturer.is_active:
            raise UnauthorizedError("Manufacturer account is disabled")

        access_token = create_access_token({
            "sub": manufacturer.id,
            "type": "manufacturer",
            "manufacturer_id": manufacturer.id,
        })
        refresh_token = create_refresh_token({
            "sub": manufacturer.id,
            "type": "manufacturer",
        })

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        ), manufacturer

    async def update_profile(
        self, manufacturer_id: str, data: ManufacturerProfileUpdate
    ) -> Manufacturer:
        """Update manufacturer profile."""
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise NotFoundError("Manufacturer", manufacturer_id)

        # Update fields from data (only non-None values)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(manufacturer, field, value)

        return await self._manufacturer_repo.update(manufacturer)
