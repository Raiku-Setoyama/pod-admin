"""Delete development transaction data for production readiness.

Revision ID: cleanup_dev_transaction_data
Revises: add_shipping_email_sent
Create Date: 2026-03-23

本番運用に向けて、開発中に作成されたトランザクションデータを削除する。
マスタデータ（users, manufacturers, products, order_sources）は保持する。

削除対象:
- chat_attachments
- chat_messages
- shipment_items
- shipments
- order_items
- orders
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "cleanup_dev_transaction_data"
down_revision = "add_shipping_email_sent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FK依存順に削除（子テーブル → 親テーブル）
    op.execute("DELETE FROM chat_attachments")
    op.execute("DELETE FROM chat_messages")
    op.execute("DELETE FROM shipment_items")
    op.execute("DELETE FROM shipments")
    op.execute("DELETE FROM order_items")
    op.execute("DELETE FROM orders")


def downgrade() -> None:
    # データ削除は不可逆のため、downgradeでは何もしない
    pass
