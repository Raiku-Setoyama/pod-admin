"""External API router for external sales sites."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_external_service, verify_api_key
from app.models.product import ProductType
from app.schemas.external import (
    OrderCancelResponse,
    OrderStatusResponse,
    PriceCalculationRequest,
    PriceCalculationResponse,
    ProductOptionsResponse,
)
from app.services.external_service import ExternalService

router = APIRouter(prefix="/external", tags=["external"])


@router.get(
    "/product-options/{product_type}",
    response_model=ProductOptionsResponse,
)
async def get_product_options(
    product_type: ProductType,
    service: Annotated[ExternalService, Depends(get_external_service)],
    api_key: Annotated[str, Depends(verify_api_key)],
) -> ProductOptionsResponse:
    """Get available options for a product type.

    Returns the selectable attributes (size, color, position) for the specified product type.
    Currently only supports T-shirts.
    """
    return service.get_product_options(product_type)


@router.post(
    "/price-calculation",
    response_model=PriceCalculationResponse,
)
async def calculate_price(
    data: PriceCalculationRequest,
    service: Annotated[ExternalService, Depends(get_external_service)],
    api_key: Annotated[str, Depends(verify_api_key)],
) -> PriceCalculationResponse:
    """Calculate price for a product with given attributes.

    Returns the unit price and total price for the specified product configuration.
    Currently only supports T-shirts.
    """
    return await service.calculate_price(data)


@router.get(
    "/orders/{order_number}/status",
    response_model=OrderStatusResponse,
)
async def get_order_status(
    order_number: str,
    service: Annotated[ExternalService, Depends(get_external_service)],
    api_key: Annotated[str, Depends(verify_api_key)],
) -> OrderStatusResponse:
    """Get order status by order number.

    Returns the status and timestamps for the specified order.
    Returns 404 if the order is not found.
    """
    return await service.get_order_status_by_order_number(order_number)


@router.post(
    "/orders/{order_number}/cancel",
    response_model=OrderCancelResponse,
    status_code=200,
)
async def cancel_order(
    order_number: str,
    service: Annotated[ExternalService, Depends(get_external_service)],
    api_key: Annotated[str, Depends(verify_api_key)],
) -> OrderCancelResponse:
    """Cancel an order by order number."""
    return await service.cancel_order(order_number)
