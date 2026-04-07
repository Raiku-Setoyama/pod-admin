"""Add estimated_shipping_date column to shipments table.

Revision ID: add_est_ship_date_001
Revises: add_sys_settings_001
Create Date: 2026-04-07

Shipment作成時に計算した納品予定日を永続化する。
"""

from alembic import op
import sqlalchemy as sa


revision = "add_est_ship_date_001"
down_revision = "add_sys_settings_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column("estimated_shipping_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shipments", "estimated_shipping_date")
