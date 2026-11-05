"""Add manufacturer_notified_at column to order_items.

メーカー宛の日次発注メールで、明細ごとに通知済みかを持つ。これまでは「送信処理の時点で
発注済み」かつ「前回送信より後に作られた」明細を数えていたため、送信処理より先に製造中へ
進んだ明細や、その時点で発注準備中だった明細が二度と通知されなかった。

Revision ID: add_item_mfr_notified_at
Revises: add_mfg_generation_lease
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_item_mfr_notified_at"
down_revision: str | Sequence[str] | None = "add_mfg_generation_lease"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column("manufacturer_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 索引は張らない。この列はメーカーの絞り込み（products 経由）と組み合わせてしか使わず、
    # 送信処理は 1 日 1 回である。

    # 既存の明細は、これまでの基準で「対象外」だったものを通知済みにする。
    # 切り替えの直後に、過去の明細がまとめてメールに載らないようにするため。
    # - メーカーに前回の送信がある: それ以前に作られた明細（前回の送信時刻を入れる）
    # - 前回の送信が無い・通知設定が無い: すべての明細（切り替え時刻を入れる）
    # 前回の送信より後に作られた明細は未通知のまま残し、次の送信で数える。
    op.execute(
        """
        UPDATE order_items AS oi
        SET manufacturer_notified_at = COALESCE(s.last_notified_at, NOW())
        FROM products AS p
        LEFT JOIN manufacturer_notification_settings AS s
            ON s.manufacturer_id = p.manufacturer_id
        WHERE oi.product_id = p.id
          AND (s.last_notified_at IS NULL OR oi.created_at <= s.last_notified_at)
        """
    )


def downgrade() -> None:
    op.drop_column("order_items", "manufacturer_notified_at")
