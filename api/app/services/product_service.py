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
from app.utils.exceptions import (
    DuplicateProductError,
    ManufacturerNotFoundError,
    ProductNotFoundError,
)


class ProductService:
    """Service for product operations."""

    def __init__(
        self,
        product_repo: ProductRepository,
        manufacturer_repo: ManufacturerRepository,
    ):
        self._product_repo = product_repo
        self._manufacturer_repo = manufacturer_repo

    @staticmethod
    def _to_response(product) -> ProductResponse:
        """Convert a Product model to ProductResponse with manufacturer_name."""
        manufacturer = getattr(product, "manufacturer", None)
        manufacturer_name: str | None = None
        if manufacturer is not None:
            name = getattr(manufacturer, "name", None)
            if isinstance(name, str):
                manufacturer_name = name
        data = {
            "id": product.id,
            "product_type": product.product_type,
            "size": product.size,
            "position": product.position,
            "color": product.color,
            "manufacturer_id": product.manufacturer_id,
            "cost": product.cost,
            "lead_time_days": product.lead_time_days,
            "order_limit": product.order_limit,
            "is_active": product.is_active,
            "manufacturer_name": manufacturer_name,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
        }
        return ProductResponse(**data)

    async def _check_duplicate(
        self,
        product_type: str,
        size: str,
        position: str | None,
        color: str | None,
        exclude_id: str | None = None,
    ) -> None:
        """Check for duplicate product specification and raise error if found."""
        duplicate = await self._product_repo.find_duplicate(
            product_type=product_type,
            size=size,
            position=position,
            color=color,
            exclude_id=exclude_id,
        )
        if duplicate:
            raise DuplicateProductError(
                product_type=product_type,
                size=size,
                position=position,
                color=color,
            )

    async def create(self, data: ProductCreate) -> ProductResponse:
        """Create a new product."""
        # Verify manufacturer exists
        manufacturer = await self._manufacturer_repo.find_by_id(data.manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(data.manufacturer_id)

        # Check for duplicate product specification
        await self._check_duplicate(
            product_type=data.product_type.value,
            size=data.size,
            position=data.position,
            color=data.color,
        )

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
        return self._to_response(product)

    async def get_by_id(self, product_id: str) -> ProductResponse:
        """Get a product by ID."""
        product = await self._product_repo.find_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        return self._to_response(product)

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
            items=[self._to_response(p) for p in products],
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

        # Determine the final values after update for duplicate check
        update_data = data.model_dump(exclude_unset=True)

        final_product_type = (
            update_data["product_type"].value
            if "product_type" in update_data and update_data["product_type"]
            else product.product_type
        )
        final_size = update_data.get("size", product.size)
        final_position = (
            update_data["position"]
            if "position" in update_data
            else product.position
        )
        final_color = (
            update_data["color"]
            if "color" in update_data
            else product.color
        )

        # Check for duplicate product specification (excluding self)
        await self._check_duplicate(
            product_type=final_product_type,
            size=final_size,
            position=final_position,
            color=final_color,
            exclude_id=product_id,
        )

        # Update fields
        for field, value in update_data.items():
            if field == "product_type" and value:
                setattr(product, field, value.value)
            else:
                setattr(product, field, value)

        product = await self._product_repo.update(product)
        return self._to_response(product)

    async def delete(self, product_id: str) -> None:
        """Delete a product."""
        product = await self._product_repo.find_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        await self._product_repo.delete(product)
