"""Add retry scheduling column to manufacturing_data.

到達不能（VM が落ちている・応答しない）で失敗した生成を、`failed` で終端させずに
`pending` へ戻して後で再試行する。その「いつから再試行してよいか」を持つ列である。

**なぜ列が要るのか。** 戻すだけでは、同じワーカーの周回が即座に同じ行を取り直し、
VM が落ちている間に試行回数を数秒で使い切る。かといって「到達不能なら周回を止める」
だけで済ませると、特定の入力でだけ VM が 5xx を返す行が待ち行列の先頭に居座り、
**その 1 行が後続すべてを止める。** 予定時刻を持たせれば、落ちている VM は待たれ、
問題のある行は後ろに下がり、どちらも他の行を止めない。

Revision ID: add_mfg_generation_retry
Revises: add_mfg_generation_lease
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_mfg_generation_retry"
down_revision: str | Sequence[str] | None = "add_mfg_generation_lease"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "manufacturing_data",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 既存の pending 行は NULL のまま＝「今すぐ対象」になる。移行のための詰め直しは要らない。
    #
    # 索引は張らない。取り出しは status='pending'（既存の索引が効く）で先に絞られ、
    # そのうえでこの列を見る。待ち行列は常に小さい（VM が 1 件ずつしか捌けないため、
    # 溜まっても数百件の桁）。**先に (status, created_at) を張るべき状況のほうが先に来る。**


def downgrade() -> None:
    op.drop_column("manufacturing_data", "next_attempt_at")
