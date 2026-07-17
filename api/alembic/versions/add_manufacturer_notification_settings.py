"""Add manufacturer notification settings.

Revision ID: add_mfr_notif_settings
Revises: add_manufacturing_data
Create Date: 2026-07-09

メーカー別 日次発注ダイジェストメール機能のためのスキーマ追加。
- manufacturer_notification_settings テーブル
  （メーカー別 To/CC・ON/OFF・last_notified_at ウォーターマーク）
- app_settings キーの seed（全社共通の送信時刻・日次ガード・マスタスイッチ）
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_mfr_notif_settings"
down_revision = "add_manufacturing_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manufacturer_notification_settings",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("manufacturer_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "daily_digest_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "to_emails",
            postgresql.ARRAY(sa.String()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "cc_emails",
            postgresql.ARRAY(sa.String()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["manufacturer_id"], ["manufacturers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_manufacturer_notification_settings_manufacturer_id"),
        "manufacturer_notification_settings",
        ["manufacturer_id"],
        unique=True,
    )

    # app_settings のシード（GET /settings に説明付きで並ぶ）
    op.execute(
        "INSERT INTO app_settings (key, value, description) "
        "VALUES ('manufacturer_daily_digest_enabled', 'false', "
        "'メーカー日次発注通知メールの有効/無効（マスタスイッチ）') "
        "ON CONFLICT (key) DO NOTHING"
    )
    op.execute(
        "INSERT INTO app_settings (key, value, description) "
        "VALUES ('manufacturer_daily_digest_send_time', '09:00', "
        "'メーカー日次発注通知メールの送信時刻（JST・全社共通・HH:MM）') "
        "ON CONFLICT (key) DO NOTHING"
    )
    op.execute(
        "INSERT INTO app_settings (key, value, description) "
        "VALUES ('manufacturer_daily_digest_last_run_date', '', "
        "'メーカー日次発注通知メールの最終実行日（JST・YYYY-MM-DD・日次ガード用）') "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM app_settings WHERE key IN ("
        "'manufacturer_daily_digest_enabled', "
        "'manufacturer_daily_digest_send_time', "
        "'manufacturer_daily_digest_last_run_date')"
    )
    op.drop_index(
        op.f("ix_manufacturer_notification_settings_manufacturer_id"),
        table_name="manufacturer_notification_settings",
    )
    op.drop_table("manufacturer_notification_settings")
