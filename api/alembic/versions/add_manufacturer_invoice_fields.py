"""Add invoice-related fields to manufacturers table.

Revision ID: add_invoice_fields_001
Revises: add_source_001
Create Date: 2026-02-13

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_invoice_fields_001"
down_revision = "add_source_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add invoice-related fields to manufacturers table
    op.add_column(
        "manufacturers",
        sa.Column("postal_code", sa.String(10), nullable=True),
    )
    op.add_column(
        "manufacturers",
        sa.Column("address", sa.String(500), nullable=True),
    )
    op.add_column(
        "manufacturers",
        sa.Column("bank_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "manufacturers",
        sa.Column("bank_branch", sa.String(100), nullable=True),
    )
    op.add_column(
        "manufacturers",
        sa.Column("bank_account_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "manufacturers",
        sa.Column("bank_account_number", sa.String(20), nullable=True),
    )
    op.add_column(
        "manufacturers",
        sa.Column("bank_account_holder", sa.String(100), nullable=True),
    )
    op.add_column(
        "manufacturers",
        sa.Column("representative_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "manufacturers",
        sa.Column("invoice_notes", sa.String(1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manufacturers", "invoice_notes")
    op.drop_column("manufacturers", "representative_name")
    op.drop_column("manufacturers", "bank_account_holder")
    op.drop_column("manufacturers", "bank_account_number")
    op.drop_column("manufacturers", "bank_account_type")
    op.drop_column("manufacturers", "bank_branch")
    op.drop_column("manufacturers", "bank_name")
    op.drop_column("manufacturers", "address")
    op.drop_column("manufacturers", "postal_code")
