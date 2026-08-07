"""Add status column to order_items table.

Revision ID: add_order_item_status
Revises: add_product_uq_001
Create Date: 2026-02-25

製品単位でのステータス管理を実現するため、order_itemsテーブルにstatusカラムを追加。
既存データは紐づくOrderのstatusをコピーして移行する。
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_order_item_status"
down_revision = "add_product_uq_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add status column to order_items table with default value
    # Note: index=True is not used because we create the index explicitly later
    op.add_column(
        "order_items",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="ordered",
        ),
    )

    # Step 2: Migrate existing data - copy Order.status to OrderItem.status
    # Only copy ordered/manufacturing/delivered (not shipped, as shipped is Order-level only)
    op.execute(
        sa.text("""
            UPDATE order_items oi
            SET status = CASE
                WHEN o.status IN ('ordered', 'manufacturing', 'delivered') THEN o.status
                ELSE 'delivered'
            END
            FROM orders o
            WHERE o.id = oi.order_id
        """)
    )

    # Step 3: Create index on status column for efficient filtering
    op.create_index(
        "ix_order_items_status",
        "order_items",
        ["status"],
    )


def downgrade() -> None:
    # Drop the index
    op.drop_index("ix_order_items_status", table_name="order_items")

    # Drop the status column
    op.drop_column("order_items", "status")
