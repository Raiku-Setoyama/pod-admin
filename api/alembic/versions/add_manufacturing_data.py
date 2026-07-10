"""add manufacturing_data table and order_items generation columns

Revision ID: add_manufacturing_data
Revises: add_ext_order_notif_settings
Create Date: 2026-07-01

外部注文 v2（製造データ生成）用のスキーマ追加:
- 新テーブル manufacturing_data（商品×サイズ×バリアント単位の製造データキャッシュ）
- order_items に product_code / source_images / manufacturing_data_id を追加

既存 v1 明細は全て NULL のまま → 旧挙動を完全維持（発注ゲートの対象外）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_manufacturing_data"
down_revision: str | None = "add_ext_order_notif_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. manufacturing_data テーブルを作成
    op.create_table(
        "manufacturing_data",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("order_source_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("product_code", sa.String(length=255), nullable=False),
        sa.Column("product_type", sa.String(length=50), nullable=False),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("variant", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("source_images", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("vm_job_id", sa.String(length=100), nullable=True),
        sa.Column("output_filename", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_source_id"], ["order_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_manufacturing_data_order_source_id"),
        "manufacturing_data",
        ["order_source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manufacturing_data_product_code"),
        "manufacturing_data",
        ["product_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manufacturing_data_status"),
        "manufacturing_data",
        ["status"],
        unique=False,
    )
    # キャッシュキーの一意制約（NULLS NOT DISTINCT で size/variant が NULL でも一意）
    op.create_index(
        "uq_manufacturing_data_cache_key",
        "manufacturing_data",
        ["order_source_id", "product_code", "size", "variant"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )

    # 2. order_items に生成用の列を追加
    op.add_column(
        "order_items",
        sa.Column("product_code", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column("source_images", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column("manufacturing_data_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.create_index(
        op.f("ix_order_items_product_code"),
        "order_items",
        ["product_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_items_manufacturing_data_id"),
        "order_items",
        ["manufacturing_data_id"],
        unique=False,
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
    op.drop_constraint(
        "fk_order_items_manufacturing_data_id", "order_items", type_="foreignkey"
    )
    op.drop_index(op.f("ix_order_items_manufacturing_data_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_product_code"), table_name="order_items")
    op.drop_column("order_items", "manufacturing_data_id")
    op.drop_column("order_items", "source_images")
    op.drop_column("order_items", "product_code")

    op.drop_index("uq_manufacturing_data_cache_key", table_name="manufacturing_data")
    op.drop_index(op.f("ix_manufacturing_data_status"), table_name="manufacturing_data")
    op.drop_index(op.f("ix_manufacturing_data_product_code"), table_name="manufacturing_data")
    op.drop_index(
        op.f("ix_manufacturing_data_order_source_id"), table_name="manufacturing_data"
    )
    op.drop_table("manufacturing_data")
