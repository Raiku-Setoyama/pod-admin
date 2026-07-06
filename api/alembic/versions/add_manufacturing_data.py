"""Add manufacturing_data table and order_items manufacturing fields.

Revision ID: add_manufacturing_data
Revises: add_ext_order_notif_settings
Create Date: 2026-07-05

外部注文(v2)の製造データ生成・キャッシュ用テーブル manufacturing_data を追加し、
order_items に v2 用カラム（product_code / variant / source_images / manufacturing_data_id）を追加する。
旧v1明細では新カラムは全て NULL となり、既存の発注挙動は不変。
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_manufacturing_data"
down_revision = "add_ext_order_notif_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. manufacturing_data テーブル（製造データ生成キャッシュ）
    op.create_table(
        "manufacturing_data",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("order_source_id", UUID(as_uuid=False), nullable=False),
        sa.Column("product_code", sa.String(100), nullable=False),
        sa.Column("product_type", sa.String(50), nullable=False),
        sa.Column("size", sa.String(50), nullable=False),
        sa.Column("variant", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source_images", JSONB, nullable=True),
        sa.Column("vm_job_id", sa.String(100), nullable=True),
        sa.Column("output_filename", sa.String(255), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_source_id"], ["order_sources.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_manufacturing_data_order_source_id",
        "manufacturing_data",
        ["order_source_id"],
    )
    op.create_index("ix_manufacturing_data_product_code", "manufacturing_data", ["product_code"])
    op.create_index("ix_manufacturing_data_status", "manufacturing_data", ["status"])
    # キャッシュキー: 受注元×商品×サイズ×バリアント。variant は NULL 可のため
    # NULLS NOT DISTINCT (PostgreSQL 15+) で「バリアントなし」同士も一意に扱う。
    op.create_index(
        "uq_manufacturing_data_cache",
        "manufacturing_data",
        ["order_source_id", "product_code", "size", "variant"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )

    # 2. order_items に v2 用カラムを追加（旧明細は NULL）
    op.add_column("order_items", sa.Column("product_code", sa.String(100), nullable=True))
    op.add_column("order_items", sa.Column("variant", sa.String(50), nullable=True))
    op.add_column("order_items", sa.Column("source_images", JSONB, nullable=True))
    op.add_column(
        "order_items",
        sa.Column("manufacturing_data_id", UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_order_items_product_code", "order_items", ["product_code"])
    op.create_index(
        "ix_order_items_manufacturing_data_id",
        "order_items",
        ["manufacturing_data_id"],
    )
    op.create_foreign_key(
        "fk_order_items_manufacturing_data_id",
        "order_items",
        "manufacturing_data",
        ["manufacturing_data_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_order_items_manufacturing_data_id", "order_items", type_="foreignkey")
    op.drop_index("ix_order_items_manufacturing_data_id", table_name="order_items")
    op.drop_index("ix_order_items_product_code", table_name="order_items")
    op.drop_column("order_items", "manufacturing_data_id")
    op.drop_column("order_items", "source_images")
    op.drop_column("order_items", "variant")
    op.drop_column("order_items", "product_code")

    op.drop_index("uq_manufacturing_data_cache", table_name="manufacturing_data")
    op.drop_index("ix_manufacturing_data_status", table_name="manufacturing_data")
    op.drop_index("ix_manufacturing_data_product_code", table_name="manufacturing_data")
    op.drop_index("ix_manufacturing_data_order_source_id", table_name="manufacturing_data")
    op.drop_table("manufacturing_data")
