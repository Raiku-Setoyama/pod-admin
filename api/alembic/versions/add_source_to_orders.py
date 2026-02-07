"""Add source column to orders table.

Revision ID: add_source_001
Revises: modify_products_001
Create Date: 2026-02-07

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_source_001"
down_revision = "modify_products_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source column to orders table
    op.add_column(
        "orders",
        sa.Column("source", sa.String(50), nullable=True),
    )
    op.create_index("ix_orders_source", "orders", ["source"])

    # Set default value for existing data
    op.execute("UPDATE orders SET source = 'LEGACY' WHERE source IS NULL")


def downgrade() -> None:
    op.drop_index("ix_orders_source", table_name="orders")
    op.drop_column("orders", "source")
