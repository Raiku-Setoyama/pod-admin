"""Add system_settings and company_holidays tables.

Revision ID: add_sys_settings_001
Revises: cleanup_dev_transaction_data
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_sys_settings_001"
down_revision = "cleanup_dev_transaction_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_system_settings_key"), "system_settings", ["key"], unique=True)

    op.create_table(
        "company_holidays",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date"),
    )
    op.create_index(op.f("ix_company_holidays_date"), "company_holidays", ["date"], unique=True)

    # Insert default shipping preparation days
    op.execute(
        "INSERT INTO system_settings (id, key, value, description, created_at, updated_at) "
        "VALUES (gen_random_uuid(), 'shipping_preparation_days', '5', '発送準備日数', now(), now())"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_company_holidays_date"), table_name="company_holidays")
    op.drop_table("company_holidays")
    op.drop_index(op.f("ix_system_settings_key"), table_name="system_settings")
    op.drop_table("system_settings")
