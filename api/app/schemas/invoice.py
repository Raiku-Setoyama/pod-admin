"""Invoice schemas."""

from pydantic import BaseModel, Field


class InvoiceItemRequest(BaseModel):
    """Invoice item request (order item selection)."""

    order_item_ids: list[str] = Field(..., min_length=1)
