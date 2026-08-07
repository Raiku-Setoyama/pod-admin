"""change shipment and order status values

Revision ID: change_status_001
Revises: add_order_items_001
Create Date: 2024-12-28

Changes:
- SHIPPING -> SHIPPED
- COMPLETED -> SHIPPED (merge into final status)
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'change_status_001'
down_revision: str | None = 'add_order_items_001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Update shipments table: SHIPPING -> SHIPPED, COMPLETED -> SHIPPED
    op.execute("UPDATE shipments SET status = 'shipped' WHERE status = 'shipping'")
    op.execute("UPDATE shipments SET status = 'shipped' WHERE status = 'completed'")

    # Update orders table: SHIPPING -> SHIPPED, COMPLETED -> SHIPPED
    op.execute("UPDATE orders SET status = 'shipped' WHERE status = 'shipping'")
    op.execute("UPDATE orders SET status = 'shipped' WHERE status = 'completed'")


def downgrade() -> None:
    # Revert SHIPPED -> SHIPPING (note: cannot fully restore COMPLETED)
    op.execute("UPDATE shipments SET status = 'shipping' WHERE status = 'shipped'")
    op.execute("UPDATE orders SET status = 'shipping' WHERE status = 'shipped'")
