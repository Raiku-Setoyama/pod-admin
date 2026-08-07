"""Remove purchase_orders tables and PENDING status.

This migration:
1. Updates all orders with 'pending' status to 'ordered'
2. Changes the default status for orders table to 'ordered'
3. Drops purchase_order_status_history table
4. Drops purchase_order_items table
5. Drops purchase_orders table

Revision ID: remove_po_001
Revises: add_uid_001
Create Date: 2026-01-10

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "remove_po_001"
down_revision = "add_uid_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Update all orders with 'pending' status to 'ordered'
    op.execute("UPDATE orders SET status = 'ordered' WHERE status = 'pending'")

    # 2. Change the default status for orders table to 'ordered'
    # Note: In PostgreSQL, we need to drop and recreate the default
    op.alter_column(
        "orders",
        "status",
        server_default="ordered",
        existing_type=sa.String(20),
        existing_nullable=False,
    )

    # 3. Drop purchase_order_status_history table
    op.drop_table("purchase_order_status_history")

    # 4. Drop purchase_order_items table
    op.drop_table("purchase_order_items")

    # 5. Drop purchase_orders table
    op.drop_table("purchase_orders")


def downgrade() -> None:
    # Recreate purchase_orders table
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "manufacturer_id",
            sa.String(36),
            sa.ForeignKey("manufacturers.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="ordered"),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_delivery_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_purchase_orders_manufacturer_id",
        "purchase_orders",
        ["manufacturer_id"],
    )
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])

    # Recreate purchase_order_items table
    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "purchase_order_id",
            sa.String(36),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_purchase_order_items_purchase_order_id",
        "purchase_order_items",
        ["purchase_order_id"],
    )
    op.create_index(
        "ix_purchase_order_items_order_id",
        "purchase_order_items",
        ["order_id"],
    )

    # Recreate purchase_order_status_history table
    op.create_table(
        "purchase_order_status_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "purchase_order_id",
            sa.String(36),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("changed_by", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_purchase_order_status_history_purchase_order_id",
        "purchase_order_status_history",
        ["purchase_order_id"],
    )

    # Revert the default status back to 'pending'
    op.alter_column(
        "orders",
        "status",
        server_default="pending",
        existing_type=sa.String(20),
        existing_nullable=False,
    )
