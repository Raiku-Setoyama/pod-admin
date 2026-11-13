"""Add DTF print record columns to manufacturing_data.

T シャツ・トートの DTF 版の製造データ（#187・#188）について、生成の結果を記録する。
発注リスト（#189）と管理画面（#190）が使う。インクジェット版・アクリル系は NULL のまま。

Revision ID: add_mfg_dtf_print_record
Revises: add_item_mfr_notified_at
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_mfg_dtf_print_record"
down_revision: str | Sequence[str] | None = "add_item_mfr_notified_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 元画像の実寸解像度（dpi）
    op.add_column("manufacturing_data", sa.Column("source_dpi", sa.Float(), nullable=True))
    # 絵柄の幅・高さ（mm）
    op.add_column("manufacturing_data", sa.Column("art_width_mm", sa.Float(), nullable=True))
    op.add_column("manufacturing_data", sa.Column("art_height_mm", sa.Float(), nullable=True))
    # リブ下から絵柄の最上部まで（mm）
    op.add_column(
        "manufacturing_data", sa.Column("art_top_below_rib_mm", sa.Float(), nullable=True)
    )
    # 白版の種類（color_only / white_only / mixed）
    op.add_column(
        "manufacturing_data", sa.Column("white_plate", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("manufacturing_data", "white_plate")
    op.drop_column("manufacturing_data", "art_top_below_rib_mm")
    op.drop_column("manufacturing_data", "art_height_mm")
    op.drop_column("manufacturing_data", "art_width_mm")
    op.drop_column("manufacturing_data", "source_dpi")
