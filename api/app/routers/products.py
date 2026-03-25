"""Products router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_admin, get_product_service
from app.models.product import ProductType
from app.models.product_attributes import PRODUCT_ATTRIBUTES, get_attribute_spec
from app.models.user import User
from app.schemas.product import (
    ProductAttributeSpecResponse,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/attributes", response_model=list[ProductAttributeSpecResponse])
async def list_product_attributes(
    current_user: Annotated[User, Depends(get_current_admin)],
) -> list[ProductAttributeSpecResponse]:
    """List attribute specs for all product types."""
    return [
        ProductAttributeSpecResponse(
            product_type=pt.value,
            sizes=spec.sizes,
            colors=spec.colors,
            positions=spec.positions,
            required_size=spec.required_size,
            required_color=spec.required_color,
            required_position=spec.required_position,
        )
        for pt, spec in PRODUCT_ATTRIBUTES.items()
    ]


@router.get("/attributes/{product_type}", response_model=ProductAttributeSpecResponse)
async def get_product_attributes(
    product_type: ProductType,
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductAttributeSpecResponse:
    """Get attribute spec for a specific product type."""
    spec = get_attribute_spec(product_type)
    return ProductAttributeSpecResponse(
        product_type=product_type.value,
        sizes=spec.sizes,
        colors=spec.colors,
        positions=spec.positions,
        required_size=spec.required_size,
        required_color=spec.required_color,
        required_position=spec.required_position,
    )


@router.get("", response_model=ProductListResponse)
async def list_products(
    service: Annotated[ProductService, Depends(get_product_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    product_type: ProductType | None = None,
    manufacturer_id: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> ProductListResponse:
    """List products with pagination and filters."""
    return await service.list(
        page=page,
        limit=limit,
        product_type=product_type,
        manufacturer_id=manufacturer_id,
        is_active=is_active,
        search=search,
    )


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    service: Annotated[ProductService, Depends(get_product_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductResponse:
    """Create a new product."""
    return await service.create(data)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    service: Annotated[ProductService, Depends(get_product_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductResponse:
    """Get a product by ID."""
    return await service.get_by_id(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    service: Annotated[ProductService, Depends(get_product_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductResponse:
    """Update a product."""
    return await service.update(product_id, data)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    service: Annotated[ProductService, Depends(get_product_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a product."""
    await service.delete(product_id)
