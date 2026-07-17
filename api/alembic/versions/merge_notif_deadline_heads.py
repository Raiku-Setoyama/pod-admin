"""merge mfr_notif_settings and order_deadline_time heads

Revision ID: merge_notif_deadline_heads
Revises: add_mfr_notif_settings, add_order_deadline_time
Create Date: 2026-07-17 08:34:20.545256

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_notif_deadline_heads'
down_revision: Union[str, None] = ('add_mfr_notif_settings', 'add_order_deadline_time')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
