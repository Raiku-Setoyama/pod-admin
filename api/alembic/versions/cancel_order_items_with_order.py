"""Backfill キャンセル済み(cancelled) status for items of cancelled orders.

Revision ID: cancel_order_items
Revises: add_src_img_replacement
Create Date: 2026-07-28

注文がキャンセルされても明細（order_items）のステータスが更新されず、メーカー画面・
メーカーポータルで「発注済み」のまま残ってしまっていた。以降は注文のキャンセルが明細へ
波及するが、既存のキャンセル済み注文の明細は取り残されているためここで backfill する。

ステータスは String(20) のため DB の型変更は不要。
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "cancel_order_items"
down_revision = "add_src_img_replacement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE order_items AS oi
            SET status = 'cancelled'
            FROM orders AS o
            WHERE oi.order_id = o.id
              AND o.status = 'cancelled'
              AND oi.status <> 'cancelled'
            """
        )
    )


def downgrade() -> None:
    # 波及前の状態（明細はライフサイクル上のステータスのまま）へ戻す。
    # 製造データが未 ready の明細は「発注準備中」、それ以外は「発注済み」。
    # 元の値は upgrade で失われているため、製造中/納入済みだった明細も発注済みに戻る
    # （app.models.order.item_status_for_manufacturing_ready と同じ判定の SQL 版）。
    op.execute(
        sa.text(
            """
            UPDATE order_items AS oi
            SET status = CASE
                WHEN EXISTS (
                    SELECT 1 FROM manufacturing_data md
                    WHERE md.id = oi.manufacturing_data_id AND md.status <> 'ready'
                ) THEN 'preparing_order'
                ELSE 'ordered'
            END
            FROM orders AS o
            WHERE oi.order_id = o.id
              AND o.status = 'cancelled'
              AND oi.status = 'cancelled'
            """
        )
    )
