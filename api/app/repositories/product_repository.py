"""Product repository for database operations."""

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductType


class ProductRepository:
    """Repository for Product model."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, product_id: str) -> Product | None:
        """Find a product by ID."""
        result = await self._db.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()

    async def find_all(
        self,
        page: int = 1,
        limit: int = 20,
        product_type: ProductType | None = None,
        manufacturer_id: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Product], int]:
        """Find all products with pagination and filters."""
        query = select(Product)
        count_query = select(func.count(Product.id))

        # Apply filters
        if product_type:
            query = query.where(Product.product_type == product_type.value)
            count_query = count_query.where(Product.product_type == product_type.value)

        if manufacturer_id:
            query = query.where(Product.manufacturer_id == manufacturer_id)
            count_query = count_query.where(Product.manufacturer_id == manufacturer_id)

        if is_active is not None:
            query = query.where(Product.is_active == is_active)
            count_query = count_query.where(Product.is_active == is_active)

        # Note: search parameter is no longer used (name column removed)

        # Get total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.order_by(Product.created_at.desc()).offset(offset).limit(limit)

        result = await self._db.execute(query)
        products = list(result.scalars().all())

        return products, total

    async def create(self, product: Product) -> Product:
        """Create a new product."""
        self._db.add(product)
        await self._db.flush()
        await self._db.refresh(product)
        return product

    async def update(self, product: Product) -> Product:
        """Update an existing product."""
        await self._db.flush()
        await self._db.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        """Delete a product."""
        await self._db.delete(product)
        await self._db.flush()

    async def find_by_product_type(
        self,
        product_type: ProductType,
    ) -> Product | None:
        """Find a product by type."""
        query = select(Product).where(
            Product.product_type == product_type.value,
            Product.is_active == True,  # noqa: E712
        )
        result = await self._db.execute(query)
        return result.scalars().first()

    async def find_duplicate(
        self,
        product_type: str,
        size: str,
        position: str | None,
        color: str | None,
        exclude_id: str | None = None,
    ) -> Product | None:
        """Find a product with the same (product_type, size, position, color) combination.

        Args:
            product_type: The product type value.
            size: The size value.
            position: The position value (can be None).
            color: The color value (can be None).
            exclude_id: Product ID to exclude from the check (for updates).

        Returns:
            The duplicate Product if found, None otherwise.
        """
        conditions = [
            Product.product_type == product_type,
            Product.size == size,
            Product.is_active == True,  # noqa: E712 - only active products
        ]

        # Handle NULL comparison: NULL == NULL should be True
        if position is None:
            conditions.append(Product.position.is_(None))
        else:
            conditions.append(Product.position == position)

        if color is None:
            conditions.append(Product.color.is_(None))
        else:
            conditions.append(Product.color == color)

        if exclude_id is not None:
            conditions.append(Product.id != exclude_id)

        query = select(Product).where(and_(*conditions))
        result = await self._db.execute(query)
        return result.scalars().first()
