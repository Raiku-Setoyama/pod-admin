"""merge mfr_notif_settings and order_deadline_time heads

Revision ID: 1cabebecdc5c
Revises: add_mfr_notif_settings, add_order_deadline_time
Create Date: 2026-07-17 18:45:48.449613

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '1cabebecdc5c'
down_revision: str | None = ('add_mfr_notif_settings', 'add_order_deadline_time')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
