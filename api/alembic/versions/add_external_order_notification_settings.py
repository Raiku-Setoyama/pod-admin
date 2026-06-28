"""Seed external order notification settings.

Revision ID: add_ext_order_notif_settings
Revises: add_est_ship_date_settings
Create Date: 2026-06-28

外部注文の受付通知メールの設定キーを app_settings に追加するマイグレーション。
- external_order_notification_enabled: 通知の ON/OFF（初期値 "false"）
- external_order_notification_recipients: 通知先メールアドレス（カンマ区切り、初期値 空文字）

既存設定一覧（GET /settings）に説明付きで並ぶように seed する。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_ext_order_notif_settings"
down_revision = "add_est_ship_date_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO app_settings (key, value, description) "
        "VALUES ('external_order_notification_enabled', 'false', "
        "'外部注文の受付通知メールの有効/無効') "
        "ON CONFLICT (key) DO NOTHING"
    )
    op.execute(
        "INSERT INTO app_settings (key, value, description) "
        "VALUES ('external_order_notification_recipients', '', "
        "'外部注文の受付通知メールの送信先（カンマ区切り）') "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM app_settings WHERE key IN ("
        "'external_order_notification_enabled', "
        "'external_order_notification_recipients')"
    )
