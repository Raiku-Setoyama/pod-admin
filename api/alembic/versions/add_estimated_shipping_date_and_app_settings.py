"""Add estimated_shipping_date to orders and create app_settings table.

Revision ID: add_est_ship_date_settings
Revises: add_expected_delivery_date
Create Date: 2026-04-09

注文レベルの配送予定日とアプリケーション設定テーブルを追加するマイグレーション。
- ordersテーブルにestimated_shipping_dateカラムを追加
- app_settingsテーブルを作成
- 初期データとしてshipping_preparation_days=5を挿入
- 既存注文のestimated_shipping_dateをバックフィル
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_est_ship_date_settings"
down_revision = "add_expected_delivery_date"
branch_labels = None
depends_on = None

# Default shipping preparation days
DEFAULT_SHIPPING_DAYS = 5


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

    # Backfill estimated_shipping_date for existing orders
    _backfill_estimated_shipping_dates()


def _backfill_estimated_shipping_dates() -> None:
    """既存注文のestimated_shipping_dateをバックフィルする.

    各注文について MAX(items.expected_delivery_date) + 発送準備日数(営業日) を計算する。
    営業日計算にはjpholidayとcompany_holidaysテーブルを使用する。
    """
    from app.utils.business_day_calculator import add_business_days

    conn = op.get_bind()

    # Fetch company holidays
    holidays_result = conn.execute(sa.text("SELECT date FROM company_holidays"))
    company_holidays = {row[0] for row in holidays_result}

    # Fetch orders with their max expected_delivery_date
    # Only process orders that have at least one item with expected_delivery_date
    orders_result = conn.execute(sa.text("""
        SELECT o.id, MAX(oi.expected_delivery_date) as max_delivery_date
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        WHERE oi.expected_delivery_date IS NOT NULL
          AND o.estimated_shipping_date IS NULL
        GROUP BY o.id
    """))

    for order_id, max_delivery_date in orders_result:
        if max_delivery_date is None:
            continue

        estimated_date = add_business_days(
            max_delivery_date,
            DEFAULT_SHIPPING_DAYS,
            company_holidays,
        )

        conn.execute(
            sa.text(
                "UPDATE orders SET estimated_shipping_date = :date WHERE id = :id"
            ),
            {"date": estimated_date, "id": order_id},
        )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("orders", "estimated_shipping_date")
