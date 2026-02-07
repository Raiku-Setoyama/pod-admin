"""Product service."""

from app.models.product import Product, ProductType
from app.repositories.manufacturer_repository import ManufacturerRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.utils.exceptions import ManufacturerNotFoundError, ProductNotFoundError


class ProductService:
    """Service for product operations."""

    def __init__(
        self,
        product_repo: ProductRepository,
        manufacturer_repo: ManufacturerRepository,
    ):
        self._product_repo = product_repo
        self._manufacturer_repo = manufacturer_repo

    async def create(self, data: ProductCreate) -> ProductResponse:
        """Create a new product."""
        # Verify manufacturer exists
        manufacturer = await self._manufacturer_repo.find_by_id(data.manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(data.manufacturer_id)

        product = Product(
            product_type=data.product_type.value,
            size=data.size,
            position=data.position,
            color=data.color,
            manufacturer_id=data.manufacturer_id,
            cost=data.cost,
            lead_time_days=data.lead_time_days,
            order_limit=data.order_limit,
        )

        product = await self._product_repo.create(product)
        return ProductResponse.model_validate(product)

    async def get_by_id(self, product_id: str) -> ProductResponse:
        """Get a product by ID."""
        product = await self._product_repo.find_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        return ProductResponse.model_validate(product)

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        product_type: ProductType | None = None,
        manufacturer_id: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> ProductListResponse:
        """List products with pagination and filters."""
        products, total = await self._product_repo.find_all(
            page=page,
            limit=limit,
            product_type=product_type,
            manufacturer_id=manufacturer_id,
            is_active=is_active,
            search=search,
        )

        return ProductListResponse(
            items=[ProductResponse.model_validate(p) for p in products],
            total=total,
            page=page,
            limit=limit,
        )

    async def update(self, product_id: str, data: ProductUpdate) -> ProductResponse:
        """Update a product."""
        product = await self._product_repo.find_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)

        # Verify manufacturer if being changed
        if data.manufacturer_id and data.manufacturer_id != product.manufacturer_id:
            manufacturer = await self._manufacturer_repo.find_by_id(data.manufacturer_id)
            if not manufacturer:
                raise ManufacturerNotFoundError(data.manufacturer_id)

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "product_type" and value:
                setattr(product, field, value.value)
            else:
                setattr(product, field, value)

        product = await self._product_repo.update(product)
        return ProductResponse.model_validate(product)

    async def delete(self, product_id: str) -> None:
        """Delete a product."""
        product = await self._product_repo.find_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        await self._product_repo.delete(product)
