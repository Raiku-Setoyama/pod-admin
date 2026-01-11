"""User repository for database operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository for User model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_email(self, email: str) -> User | None:
        """Find a user by email."""
        result = await self._db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def find_by_id(self, user_id: str) -> User | None:
        """Find a user by ID."""
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        """Create a new user."""
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """Update an existing user."""
        await self._db.flush()
        await self._db.refresh(user)
        return user
