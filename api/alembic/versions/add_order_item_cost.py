"""Add cost (manufacturer unit cost at creation) to order_items.

請求書 PDF・発注リスト CSV は製品マスタの原価（products.cost）を出力のたびに読んでいたため、
製品の原価を変えると過去の明細の金額まで変わっていた。明細の作成時点の原価を明細に残す（#207）。

既存の明細には、移行時点の製品の原価を入れる（それ以前の原価の履歴は残っていない）。

NOT NULL にはしない。デプロイは migrate Job の後に api を切り替えるため、その間に旧リビジョンが
原価なしで明細を登録すると落ちる。NULL の明細は読む側で製品の原価に戻す。

Revision ID: add_order_item_cost
Revises: add_mfg_dtf_print_record
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_order_item_cost"
down_revision: str | Sequence[str] | None = "add_mfg_dtf_print_record"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("cost", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE order_items SET cost = products.cost "
        "FROM products WHERE order_items.product_id = products.id"
    )


def downgrade() -> None:
    op.drop_column("order_items", "cost")
