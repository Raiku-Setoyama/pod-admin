"""Authentication service."""

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.utils.exceptions import UnauthorizedError
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def login(self, request: LoginRequest) -> TokenResponse:
        """Authenticate user and return tokens."""
        user = await self._user_repo.find_by_email(request.email)

        if not user or not verify_password(request.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("User account is disabled")

        # user.role is already a string from DB
        role = user.role.value if hasattr(user.role, "value") else user.role
        access_token = create_access_token({"sub": user.id, "role": role})
        refresh_token = create_refresh_token({"sub": user.id})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token."""
        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")

        user_id = payload.get("sub")
        user = await self._user_repo.find_by_id(user_id)

        if not user or not user.is_active:
            raise UnauthorizedError("User not found or disabled")

        role = user.role.value if hasattr(user.role, "value") else user.role
        access_token = create_access_token({"sub": user.id, "role": role})
        new_refresh_token = create_refresh_token({"sub": user.id})

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

    async def get_current_user(self, token: str) -> User:
        """Get current user from access token."""
        payload = decode_token(token)

        if not payload or payload.get("type") != "access":
            raise UnauthorizedError("Invalid access token")

        user_id = payload.get("sub")
        user = await self._user_repo.find_by_id(user_id)

        if not user or not user.is_active:
            raise UnauthorizedError("User not found or disabled")

        return user
