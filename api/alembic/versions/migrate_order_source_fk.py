"""Migrate Order.source to Order.order_source_id FK.

This migration:
1. Creates LEGACY/TEST OrderSource records for existing orders
2. Adds order_source_id FK column to orders
3. Migrates existing data (source code -> order_source_id)
4. Removes the source column from orders

Revision ID: migrate_order_source_fk
Revises: add_order_sources_001
Create Date: 2026-02-14

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "migrate_order_source_fk"
down_revision = "add_order_sources_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === 1. Create LEGACY/TEST OrderSource records for existing orders ===
    op.execute("""
        INSERT INTO order_sources (id, code, api_key, name, phone, postal_code,
            address_prefecture, address_city, is_active, created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'LEGACY', 'legacy-disabled-key', 'レガシー注文',
             '000-0000-0000', '000-0000', '東京都', 'レガシー', false, now(), now()),
            (gen_random_uuid(), 'TEST', 'test-api-key', 'テスト配送元',
             '03-0000-0000', '000-0000', '東京都', 'テスト市1-1-1', true, now(), now())
        ON CONFLICT (code) DO NOTHING
    """)

    # === 2. Add order_source_id FK column ===
    op.add_column(
        "orders",
        sa.Column("order_source_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "fk_orders_order_source_id",
        "orders",
        "order_sources",
        ["order_source_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_orders_order_source_id", "orders", ["order_source_id"])

    # === 3. Migrate existing data (source code -> order_source_id) ===
    op.execute("""
        UPDATE orders o
        SET order_source_id = os.id
        FROM order_sources os
        WHERE o.source = os.code
    """)

    # === 4. Remove source column ===
    op.drop_index("ix_orders_source", table_name="orders")
    op.drop_column("orders", "source")


def downgrade() -> None:
    # === 1. Add source column back ===
    op.add_column(
        "orders",
        sa.Column("source", sa.String(50), nullable=True),
    )
    op.create_index("ix_orders_source", "orders", ["source"])

    # === 2. Migrate data back (order_source_id -> source code) ===
    op.execute("""
        UPDATE orders o
        SET source = os.code
        FROM order_sources os
        WHERE o.order_source_id = os.id
    """)

    # === 3. Remove order_source_id FK column ===
    op.drop_index("ix_orders_order_source_id", table_name="orders")
    op.drop_constraint("fk_orders_order_source_id", "orders", type_="foreignkey")
    op.drop_column("orders", "order_source_id")

    # === 4. Remove LEGACY/TEST OrderSource records ===
    op.execute("""
        DELETE FROM order_sources
        WHERE code IN ('LEGACY', 'TEST')
    """)
