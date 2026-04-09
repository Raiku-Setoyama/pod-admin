"""Add expected_delivery_date to order_items and create company_holidays table.

Revision ID: add_expected_delivery_date
Revises: cleanup_dev_transaction_data
Create Date: 2026-04-09

OrderItem単位の納品予定日をDBに永続化するためのマイグレーション。
- order_itemsテーブルにexpected_delivery_dateカラムを追加（nullable）
- TOSYO独自休日管理用のcompany_holidaysテーブルを作成
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "add_expected_delivery_date"
down_revision = "cleanup_dev_transaction_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add expected_delivery_date column to order_items
    op.add_column(
        "order_items",
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
    )

    # Create company_holidays table
    op.create_table(
        "company_holidays",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Add index on company_holidays.date for fast lookups
    op.create_index("ix_company_holidays_date", "company_holidays", ["date"])


def downgrade() -> None:
    op.drop_index("ix_company_holidays_date", table_name="company_holidays")
    op.drop_table("company_holidays")
    op.drop_column("order_items", "expected_delivery_date")
