"""Order sources router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_admin, get_order_source_service
from app.models.user import User
from app.schemas.order_source import (
    OrderSourceCreate,
    OrderSourceListResponse,
    OrderSourceResponse,
    OrderSourceUpdate,
)
from app.services.order_source_service import OrderSourceService

router = APIRouter(prefix="/order-sources", tags=["order-sources"])


@router.get("", response_model=OrderSourceListResponse)
async def list_order_sources(
    service: Annotated[OrderSourceService, Depends(get_order_source_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    is_active: bool | None = None,
) -> OrderSourceListResponse:
    """List order sources with pagination and filters."""
    return await service.list(
        page=page,
        limit=limit,
        is_active=is_active,
    )


@router.get("/{order_source_id}", response_model=OrderSourceResponse)
async def get_order_source(
    order_source_id: str,
    service: Annotated[OrderSourceService, Depends(get_order_source_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> OrderSourceResponse:
    """Get an order source by ID."""
    return await service.get_by_id(order_source_id)


@router.post("", response_model=OrderSourceResponse, status_code=201)
async def create_order_source(
    data: OrderSourceCreate,
    service: Annotated[OrderSourceService, Depends(get_order_source_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> OrderSourceResponse:
    """Create a new order source."""
    return await service.create(data)


@router.patch("/{order_source_id}", response_model=OrderSourceResponse)
async def update_order_source(
    order_source_id: str,
    data: OrderSourceUpdate,
    service: Annotated[OrderSourceService, Depends(get_order_source_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> OrderSourceResponse:
    """Update an order source."""
    return await service.update(order_source_id, data)


@router.delete("/{order_source_id}", status_code=204)
async def delete_order_source(
    order_source_id: str,
    service: Annotated[OrderSourceService, Depends(get_order_source_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete an order source."""
    await service.delete(order_source_id)
