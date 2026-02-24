"""Add order_status_history table.

Revision ID: add_status_hist_001
Revises: add_product_uq_001
Create Date: 2026-02-24

Creates:
- order_status_history table with FK to orders.id
- Index on order_id column
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "add_order_status_history_001"
down_revision = "add_product_uq_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_status_history",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "order_id",
            UUID(as_uuid=False),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by", sa.String(100), nullable=True),
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
        "ix_order_status_history_order_id",
        "order_status_history",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_status_history_order_id", table_name="order_status_history")
    op.drop_table("order_status_history")
