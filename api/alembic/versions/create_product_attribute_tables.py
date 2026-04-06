"""Create product attribute tables and seed data from existing ENUMs.

Revision ID: create_product_attr_001
Revises: cleanup_dev_transaction_data
Create Date: 2026-04-06
"""

import sqlalchemy as sa
from alembic import op
from uuid import uuid4

revision = "create_product_attr_001"
down_revision = "cleanup_dev_transaction_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create product_attribute_options table
    op.create_table(
        "product_attribute_options",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("product_type", sa.String(50), nullable=False, index=True),
        sa.Column("attribute_name", sa.String(20), nullable=False),
        sa.Column("attribute_value", sa.String(50), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "product_type",
            "attribute_name",
            "attribute_value",
            name="uq_product_attr_type_name_value",
        ),
    )

    # Create product_attribute_requirements table
    op.create_table(
        "product_attribute_requirements",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("product_type", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("required_size", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("required_color", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("required_position", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Seed data: existing ENUM values
    options = []

    # Tシャツ
    for order, value in enumerate(["S", "M", "L", "XL"], 1):
        options.append(("tshirt", "size", value, order))
    options.append(("tshirt", "color", "白", 1))
    options.append(("tshirt", "position", "正面", 1))

    # アクリルキーホルダー
    for order, value in enumerate(["50x50mm", "70x70mm", "100x100mm"], 1):
        options.append(("acrylic_keychain", "size", value, order))
    options.append(("acrylic_keychain", "color", "アクリル", 1))

    # アクリルスタンド
    for order, value in enumerate(["50x50mm", "70x70mm", "100x100mm"], 1):
        options.append(("acrylic_stand", "size", value, order))
    options.append(("acrylic_stand", "color", "アクリル", 1))

    # ステッカー
    for order, value in enumerate(["50x50mm", "70x70mm", "100x100mm"], 1):
        options.append(("sticker", "size", value, order))
    options.append(("sticker", "color", "ホワイト", 1))

    # トートバッグ
    options.append(("tote_bag", "size", "M", 1))
    options.append(("tote_bag", "color", "ナチュラル", 1))
    options.append(("tote_bag", "position", "正面", 1))

    # Insert options (created_at/updated_at use server_default)
    attr_table = sa.table(
        "product_attribute_options",
        sa.column("id", sa.String),
        sa.column("product_type", sa.String),
        sa.column("attribute_name", sa.String),
        sa.column("attribute_value", sa.String),
        sa.column("display_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        attr_table,
        [
            {
                "id": str(uuid4()),
                "product_type": pt,
                "attribute_name": an,
                "attribute_value": av,
                "display_order": do,
                "is_active": True,
            }
            for pt, an, av, do in options
        ],
    )

    # Insert requirements (created_at/updated_at use server_default)
    req_table = sa.table(
        "product_attribute_requirements",
        sa.column("id", sa.String),
        sa.column("product_type", sa.String),
        sa.column("required_size", sa.Boolean),
        sa.column("required_color", sa.Boolean),
        sa.column("required_position", sa.Boolean),
    )
    requirements = [
        ("tshirt", True, True, True),
        ("acrylic_keychain", True, False, False),
        ("acrylic_stand", True, False, False),
        ("sticker", True, True, False),
        ("tote_bag", True, True, True),
    ]
    op.bulk_insert(
        req_table,
        [
            {
                "id": str(uuid4()),
                "product_type": pt,
                "required_size": rs,
                "required_color": rc,
                "required_position": rp,
            }
            for pt, rs, rc, rp in requirements
        ],
    )


def downgrade() -> None:
    op.drop_table("product_attribute_requirements")
    op.drop_table("product_attribute_options")
