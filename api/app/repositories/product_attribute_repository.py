"""Product attribute repository."""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_attribute import (
    ProductAttributeOption,
    ProductAttributeRequirement,
)


class ProductAttributeRepository:
    """Repository for product attribute options and requirements."""

    def __init__(self, db: AsyncSession):
        self._db = db

    # --- Options ---

    async def find_options(
        self,
        product_type: str,
        attribute_name: str | None = None,
        is_active: bool | None = True,
    ) -> list[ProductAttributeOption]:
        """Find attribute options with optional filters."""
        stmt = select(ProductAttributeOption)
        conditions = []
        conditions.append(ProductAttributeOption.product_type == product_type)
        if attribute_name is not None:
            conditions.append(ProductAttributeOption.attribute_name == attribute_name)
        if is_active is not None:
            conditions.append(ProductAttributeOption.is_active == is_active)
        stmt = stmt.where(and_(*conditions)).order_by(
            ProductAttributeOption.attribute_name,
            ProductAttributeOption.display_order,
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def find_option_by_id(self, option_id: str) -> ProductAttributeOption | None:
        """Find a single option by ID."""
        stmt = select(ProductAttributeOption).where(
            ProductAttributeOption.id == option_id
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_option_by_value(
        self,
        product_type: str,
        attribute_name: str,
        attribute_value: str,
    ) -> ProductAttributeOption | None:
        """Find a specific option by its unique combination."""
        stmt = select(ProductAttributeOption).where(
            and_(
                ProductAttributeOption.product_type == product_type,
                ProductAttributeOption.attribute_name == attribute_name,
                ProductAttributeOption.attribute_value == attribute_value,
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_option(self, option: ProductAttributeOption) -> ProductAttributeOption:
        """Create a new attribute option."""
        self._db.add(option)
        await self._db.flush()
        await self._db.refresh(option)
        return option

    async def update_option(self, option: ProductAttributeOption) -> ProductAttributeOption:
        """Update an existing attribute option."""
        await self._db.flush()
        await self._db.refresh(option)
        return option

    async def delete_option(self, option: ProductAttributeOption) -> None:
        """Delete an attribute option."""
        await self._db.delete(option)
        await self._db.flush()

    # --- Requirements ---

    async def find_requirement(
        self, product_type: str
    ) -> ProductAttributeRequirement | None:
        """Find the attribute requirement for a product type."""
        stmt = select(ProductAttributeRequirement).where(
            ProductAttributeRequirement.product_type == product_type
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all_requirements(self) -> list[ProductAttributeRequirement]:
        """Find all attribute requirements."""
        stmt = select(ProductAttributeRequirement).order_by(
            ProductAttributeRequirement.product_type
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_requirement(
        self, requirement: ProductAttributeRequirement
    ) -> ProductAttributeRequirement:
        """Create or update an attribute requirement."""
        self._db.add(requirement)
        await self._db.flush()
        await self._db.refresh(requirement)
        return requirement
