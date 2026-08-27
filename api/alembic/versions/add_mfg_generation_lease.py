"""Add generation lease column to manufacturing_data.

製造データ生成の所有権をリース（期限つき）で表す。generating へ確保するときに期限を打ち、
ready/failed で NULL に戻す。期限切れの generating は、処理していたワーカーが落ちたものと
見なして pending へ戻す（復旧処理がワーカーの本数に依存しなくなる）。

Revision ID: add_mfg_generation_lease
Revises: cancel_order_items
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_mfg_generation_lease"
down_revision: str | Sequence[str] | None = "cancel_order_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "manufacturing_data",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 索引は張らない。この列を単独条件にするクエリは無く、復旧は status='generating'
    # （既存の索引が効く。generating は常にごく少数）で先に絞られる。
    # 取り出しを速くしたくなったら、張るべきは (status, created_at) の複合索引である。
    #
    # 既存の generating 行はリースを持たない。復旧処理は「リースが無い generating」も
    # 期限切れとして扱うため、ここでの詰め直しは不要。


def downgrade() -> None:
    op.drop_column("manufacturing_data", "lease_expires_at")
