"""Product attributes router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_current_admin, get_product_attribute_service
from app.models.user import User
from app.schemas.product_attribute import (
    ProductAttributeOptionCreate,
    ProductAttributeOptionResponse,
    ProductAttributeOptionUpdate,
    ProductAttributeRequirementResponse,
    ProductAttributeRequirementUpdate,
    ProductAttributeSpecResponse,
)
from app.services.product_attribute_service import ProductAttributeService

router = APIRouter(prefix="/product-attributes", tags=["product-attributes"])


@router.get("/{product_type}/spec", response_model=ProductAttributeSpecResponse)
async def get_attribute_spec(
    product_type: str,
    service: Annotated[ProductAttributeService, Depends(get_product_attribute_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductAttributeSpecResponse:
    """Get attribute spec (options + requirements) for a product type."""
    return await service.get_attribute_spec(product_type)


@router.get(
    "/{product_type}/options",
    response_model=list[ProductAttributeOptionResponse],
)
async def list_options(
    product_type: str,
    service: Annotated[ProductAttributeService, Depends(get_product_attribute_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    attribute_name: str | None = None,
    is_active: bool | None = None,
) -> list[ProductAttributeOptionResponse]:
    """List attribute options for a product type."""
    return await service.list_options(
        product_type=product_type,
        attribute_name=attribute_name,
        is_active=is_active,
    )


@router.post(
    "/options",
    response_model=ProductAttributeOptionResponse,
    status_code=201,
)
async def create_option(
    data: ProductAttributeOptionCreate,
    service: Annotated[ProductAttributeService, Depends(get_product_attribute_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductAttributeOptionResponse:
    """Create a new attribute option."""
    return await service.create_option(data)


@router.patch(
    "/options/{option_id}",
    response_model=ProductAttributeOptionResponse,
)
async def update_option(
    option_id: str,
    data: ProductAttributeOptionUpdate,
    service: Annotated[ProductAttributeService, Depends(get_product_attribute_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductAttributeOptionResponse:
    """Update an attribute option."""
    return await service.update_option(option_id, data)


@router.delete("/options/{option_id}", status_code=204)
async def delete_option(
    option_id: str,
    service: Annotated[ProductAttributeService, Depends(get_product_attribute_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete an attribute option."""
    await service.delete_option(option_id)


@router.get(
    "/{product_type}/requirements",
    response_model=ProductAttributeRequirementResponse,
)
async def get_requirements(
    product_type: str,
    service: Annotated[ProductAttributeService, Depends(get_product_attribute_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductAttributeRequirementResponse:
    """Get attribute requirements for a product type."""
    return await service.get_requirement(product_type)


@router.patch(
    "/{product_type}/requirements",
    response_model=ProductAttributeRequirementResponse,
)
async def update_requirements(
    product_type: str,
    data: ProductAttributeRequirementUpdate,
    service: Annotated[ProductAttributeService, Depends(get_product_attribute_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> ProductAttributeRequirementResponse:
    """Update attribute requirements for a product type."""
    return await service.update_requirement(product_type, data)
