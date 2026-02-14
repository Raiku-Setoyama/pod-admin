"""Add order_sources table, normalize address fields.

This migration:
1. Creates order_sources table for API key management
2. Adds split address fields to orders table (prefecture, city, building)
3. Removes customer fields from shipments table (customer info accessed via Order)

Revision ID: add_order_sources_001
Revises: add_invoice_fields_001
Create Date: 2026-02-14

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_order_sources_001"
down_revision = "add_invoice_fields_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === 1. Create order_sources table ===
    op.create_table(
        "order_sources",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("api_key", sa.String(100), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("postal_code", sa.String(10), nullable=False),
        sa.Column("address_prefecture", sa.String(50), nullable=False),
        sa.Column("address_city", sa.Text, nullable=False),
        sa.Column("address_building", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
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
    )
    op.create_index("ix_order_sources_code", "order_sources", ["code"])
    op.create_index("ix_order_sources_api_key", "order_sources", ["api_key"])
    op.create_index("ix_order_sources_is_active", "order_sources", ["is_active"])

    # === 2. Update orders table: add split address fields, drop combined field ===
    # Add new split address columns (temporarily nullable for data migration)
    op.add_column(
        "orders",
        sa.Column("customer_address_prefecture", sa.String(50), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("customer_address_city", sa.Text, nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("customer_address_building", sa.String(200), nullable=True),
    )

    # Migrate existing data: copy customer_address to customer_address_city
    op.execute(
        "UPDATE orders SET customer_address_city = customer_address WHERE customer_address IS NOT NULL"
    )
    # Set default prefecture for existing data
    op.execute(
        "UPDATE orders SET customer_address_prefecture = '' WHERE customer_address_prefecture IS NULL"
    )

    # Make required fields NOT NULL
    op.alter_column("orders", "customer_address_prefecture", nullable=False)
    op.alter_column("orders", "customer_address_city", nullable=False)

    # Drop the combined address field
    op.drop_column("orders", "customer_address")

    # === 3. Remove customer fields from shipments table ===
    # Customer info is now accessed via shipment.items[0].order
    op.drop_column("shipments", "customer_name")
    op.drop_column("shipments", "customer_postal_code")
    op.drop_column("shipments", "customer_address")
    op.drop_column("shipments", "customer_phone")


def downgrade() -> None:
    # === Restore shipments customer fields ===
    op.add_column(
        "shipments",
        sa.Column("customer_phone", sa.String(20), nullable=False, server_default=""),
    )
    op.add_column(
        "shipments",
        sa.Column("customer_address", sa.Text, nullable=False, server_default=""),
    )
    op.add_column(
        "shipments",
        sa.Column("customer_postal_code", sa.String(10), nullable=False, server_default=""),
    )
    op.add_column(
        "shipments",
        sa.Column("customer_name", sa.String(100), nullable=False, server_default=""),
    )
    # Remove server defaults after adding columns
    op.alter_column("shipments", "customer_phone", server_default=None)
    op.alter_column("shipments", "customer_address", server_default=None)
    op.alter_column("shipments", "customer_postal_code", server_default=None)
    op.alter_column("shipments", "customer_name", server_default=None)

    # === Restore orders combined address field ===
    op.add_column(
        "orders",
        sa.Column("customer_address", sa.Text, nullable=True),
    )
    # Migrate data back: combine prefecture + city + building
    op.execute(
        """
        UPDATE orders SET customer_address = COALESCE(customer_address_prefecture, '')
            || COALESCE(customer_address_city, '')
            || COALESCE(customer_address_building, '')
        """
    )
    op.alter_column("orders", "customer_address", nullable=False)

    # Remove split address fields from orders
    op.drop_column("orders", "customer_address_building")
    op.drop_column("orders", "customer_address_city")
    op.drop_column("orders", "customer_address_prefecture")

    # === Drop order_sources table ===
    op.drop_index("ix_order_sources_is_active", table_name="order_sources")
    op.drop_index("ix_order_sources_api_key", table_name="order_sources")
    op.drop_index("ix_order_sources_code", table_name="order_sources")
    op.drop_table("order_sources")
