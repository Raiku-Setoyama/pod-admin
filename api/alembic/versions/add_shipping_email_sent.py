"""Add shipping_email_sent column to shipments table.

Revision ID: add_shipping_email_sent
Revises: add_order_item_status
Create Date: 2026-03-18

配送通知メール送信済みフラグを追加。
重複送信防止のために使用する。
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_shipping_email_sent"
down_revision = "add_order_item_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column(
            "shipping_email_sent",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("shipments", "shipping_email_sent")
