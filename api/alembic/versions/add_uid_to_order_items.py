"""Add uid to order_items table.

Revision ID: add_uid_001
Revises: add_order_items_001
Create Date: 2024-01-15

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_uid_001"
down_revision = "change_status_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add uid column to order_items table
    op.add_column(
        "order_items",
        sa.Column("uid", sa.String(100), nullable=True, index=True),
    )

    # Migrate existing data: copy product_id to uid for existing records
    op.execute("UPDATE order_items SET uid = product_id WHERE uid IS NULL")

    # Make uid non-nullable after data migration
    op.alter_column("order_items", "uid", nullable=False)


def downgrade() -> None:
    op.drop_column("order_items", "uid")
