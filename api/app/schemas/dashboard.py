"""Dashboard schemas."""

from pydantic import BaseModel


class StatusCount(BaseModel):
    """Status count schema."""

    status: str
    count: int


class DashboardSummary(BaseModel):
    """Dashboard summary schema."""

    # Today's counts
    orders_today: int
    shipments_today: int

    # Order status breakdown
    order_status_counts: list[StatusCount]

    # Shipment status breakdown
    shipment_status_counts: list[StatusCount]

    # Alerts
    ordered_count: int  # Orders in ORDERED status (waiting for manufacturing)
    manufacturing_count: int  # Orders in MANUFACTURING status
