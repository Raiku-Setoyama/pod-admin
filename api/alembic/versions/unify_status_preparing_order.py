"""Backfill 発注準備中(preparing_order) status for unmet v2 manufacturing items.

Revision ID: unify_status_preparing_order
Revises: add_manufacturing_data
Create Date: 2026-07-11

発注ステータスと製造データステータスを統合し、発注前で製造データが未準備の明細に
「発注準備中(preparing_order)」を新設する（Issue #88）。

ステータスは String(20) のため DB の型変更は不要。既存 v2 明細のうち、製造データが
ready でないもの（status = 'ordered'）を 'preparing_order' に更新し、その注文の
Order.status を再導出する。v1 明細（manufacturing_data_id が NULL）は影響を受けない。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "unify_status_preparing_order"
down_revision = "add_manufacturing_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) v2 明細で製造データが未 ready（ready 以外）のものを preparing_order にする。
    #    v1 明細は manufacturing_data_id が NULL なので JOIN で自然に対象外。
    op.execute(
        sa.text(
            """
            UPDATE order_items AS oi
            SET status = 'preparing_order'
            FROM manufacturing_data AS md
            WHERE oi.manufacturing_data_id = md.id
              AND oi.status = 'ordered'
              AND md.status <> 'ready'
            """
        )
    )

    # 2) Order.status を再導出する。優先順位は
    #    delivered(all) > manufacturing(any) > preparing_order(any) > ordered。
    #    status = 'ordered' の注文（manufacturing/delivered/shipped/cancelled 以外）だけが
    #    対象で、preparing_order 明細を持つものを 'preparing_order' に更新する。
    op.execute(
        sa.text(
            """
            UPDATE orders AS o
            SET status = 'preparing_order'
            WHERE o.status = 'ordered'
              AND EXISTS (
                  SELECT 1 FROM order_items oi
                  WHERE oi.order_id = o.id AND oi.status = 'preparing_order'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM order_items oi
                  WHERE oi.order_id = o.id AND oi.status = 'manufacturing'
              )
            """
        )
    )


def downgrade() -> None:
    # preparing_order を ordered に戻す（統合ステータス導入前の状態へ）。
    op.execute(sa.text("UPDATE order_items SET status = 'ordered' WHERE status = 'preparing_order'"))
    op.execute(sa.text("UPDATE orders SET status = 'ordered' WHERE status = 'preparing_order'"))
