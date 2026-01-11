"""Dashboard router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_current_admin, get_dashboard_service
from app.models.user import User
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    current_user: Annotated[User, Depends(get_current_admin)],
) -> DashboardSummary:
    """Get dashboard summary with order, purchase order, and shipment statistics."""
    return await service.get_summary()
