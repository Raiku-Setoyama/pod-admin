"""add source image replacement audit columns to manufacturing_data

Revision ID: add_src_img_replacement
Revises: 1cabebecdc5c
Create Date: 2026-07-26

製造データの元画像（PNGレイヤー）を管理画面から差し替えられるようにするための追加:
- source_images_replaced_at: 最後に差し替えた時刻（NULL = 外部受注のまま）
- source_images_replaced_by: 差し替えた管理ユーザーのメール

`source_images`（JSONB）自体はスキーマ変更なし。差し替え済みレイヤーは
`url` の代わりに `file_path`（FileStorage 上のキー）を持つ形式で保存する。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_src_img_replacement"
down_revision: str | None = "1cabebecdc5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "manufacturing_data",
        sa.Column("source_images_replaced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "manufacturing_data",
        sa.Column("source_images_replaced_by", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manufacturing_data", "source_images_replaced_by")
    op.drop_column("manufacturing_data", "source_images_replaced_at")
