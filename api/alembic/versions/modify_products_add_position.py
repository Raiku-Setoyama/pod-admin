"""Add position column and remove name column from products table.

Revision ID: modify_products_001
Revises: remove_po_001
Create Date: 2026-01-13

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "modify_products_001"
down_revision = "remove_po_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add position column (nullable)
    op.add_column(
        "products",
        sa.Column("position", sa.String(50), nullable=True),
    )

    # 2. Drop name column
    op.drop_column("products", "name")


def downgrade() -> None:
    # 1. Add name column back
    op.add_column(
        "products",
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
    )

    # 2. Drop position column
    op.drop_column("products", "position")
