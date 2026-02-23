"""Add unique constraint on (product_type, size, position, color) to products table.

Revision ID: add_product_uq_001
Revises: migrate_order_source_fk
Create Date: 2026-02-23

FEAT-0008: 商品マスタに4カラム複合ユニーク制約を追加

既存の重複データがある場合は古い方を is_active=false にして解消した後、
NULLS NOT DISTINCT を使ったユニークインデックスを作成する。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_product_uq_001"
down_revision = "migrate_order_source_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Resolve existing duplicate data
    # For each set of duplicates (same product_type, size, position, color),
    # keep the newest one (by created_at) and mark older ones as is_active=false.
    #
    # This uses a CTE to find duplicates and update them.
    op.execute(
        sa.text("""
            UPDATE products
            SET is_active = false
            WHERE id IN (
                SELECT id FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY
                                product_type,
                                COALESCE(size, ''),
                                COALESCE(position, ''),
                                COALESCE(color, '')
                            ORDER BY created_at DESC
                        ) AS rn
                    FROM products
                ) ranked
                WHERE rn > 1
            )
        """)
    )

    # Step 2: Create unique index with NULLS NOT DISTINCT (PostgreSQL 15+)
    # This ensures NULL values are treated as equal for uniqueness checks.
    op.execute(
        sa.text("""
            CREATE UNIQUE INDEX uq_products_type_size_position_color
            ON products (product_type, size, position, color)
            NULLS NOT DISTINCT
            WHERE is_active = true
        """)
    )


def downgrade() -> None:
    # Drop the unique index
    op.drop_index(
        "uq_products_type_size_position_color",
        table_name="products",
    )
