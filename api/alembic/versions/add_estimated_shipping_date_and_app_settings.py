"""Add estimated_shipping_date to orders and create app_settings table.

Revision ID: add_estimated_shipping_date_settings
Revises: add_expected_delivery_date
Create Date: 2026-04-09

注文レベルの配送予定日とアプリケーション設定テーブルを追加するマイグレーション。
- ordersテーブルにestimated_shipping_dateカラムを追加
- app_settingsテーブルを作成
- 初期データとしてshipping_preparation_days=5を挿入
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_estimated_shipping_date_settings"
down_revision = "add_expected_delivery_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add estimated_shipping_date column to orders
    op.add_column(
        "orders",
        sa.Column("estimated_shipping_date", sa.Date(), nullable=True),
    )

    # Create app_settings table
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Insert default shipping_preparation_days
    op.execute(
        "INSERT INTO app_settings (key, value, description) "
        "VALUES ('shipping_preparation_days', '5', '発送準備日数')"
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("orders", "estimated_shipping_date")
