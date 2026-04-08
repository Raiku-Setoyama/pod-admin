"""Add expected_delivery_date column to order_items table.

Revision ID: add_exp_deliv_date_001
Revises: add_est_ship_date_001
Create Date: 2026-04-08

注文明細ごとの納品予定日を永続化する。
"""

from alembic import op
import sqlalchemy as sa


revision = "add_exp_deliv_date_001"
down_revision = "add_est_ship_date_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_items", "expected_delivery_date")
