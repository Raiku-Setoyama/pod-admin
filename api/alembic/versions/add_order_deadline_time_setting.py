"""Seed order deadline time setting.

Revision ID: add_order_deadline_time
Revises: unify_status_preparing_order
Create Date: 2026-07-14

メーカーへの発注締切時刻（注文〆切時間）の設定キーを app_settings に追加する
マイグレーション。
- order_deadline_time: "HH:MM"（JST・24h）。これ以降(JST)に着信した受注は翌営業日
  起算で納品予定日・配送予定日を計算する。初期値は空文字（無効＝当日起算のまま）で、
  既存挙動を完全に維持したままリリースできる。

既存設定一覧（GET /settings）に説明付きで並ぶように seed する。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_order_deadline_time"
down_revision = "unify_status_preparing_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO app_settings (key, value, description) "
        "VALUES ('order_deadline_time', '', "
        "'注文〆切時間（HH:MM・JST）。これ以降の受注は翌営業日起算で予定日を計算。空欄で無効') "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'order_deadline_time'")
