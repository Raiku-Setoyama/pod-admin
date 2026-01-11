"""add_order_items_table

Revision ID: add_order_items_001
Revises: 405ab0ea963e
Create Date: 2024-12-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_order_items_001'
down_revision: Union[str, None] = '405ab0ea963e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create order_items table
    op.create_table('order_items',
        sa.Column('order_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('product_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('product_name', sa.String(length=200), nullable=False),
        sa.Column('product_type', sa.String(length=50), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('size', sa.String(length=50), nullable=True),
        sa.Column('position', sa.String(length=50), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('design_image_url', sa.String(length=2048), nullable=True),
        sa.Column('thumbnail_image_url', sa.String(length=2048), nullable=True),
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)

    # 2. Add total_price column to orders table
    op.add_column('orders', sa.Column('total_price', sa.Integer(), nullable=True))

    # 3. Make existing product fields nullable in orders table for backward compatibility
    op.alter_column('orders', 'product_id', existing_type=sa.UUID(as_uuid=False), nullable=True)
    op.alter_column('orders', 'product_name', existing_type=sa.String(length=200), nullable=True)
    op.alter_column('orders', 'price', existing_type=sa.Integer(), nullable=True)
    op.alter_column('orders', 'quantity', existing_type=sa.Integer(), nullable=True)

    # 4. Migrate existing order data to order_items
    connection = op.get_bind()
    connection.execute(sa.text("""
        INSERT INTO order_items (id, order_id, product_id, product_name, product_type, price, quantity, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            o.id,
            o.product_id,
            o.product_name,
            COALESCE(p.product_type, 'unknown'),
            o.price,
            o.quantity,
            o.created_at,
            o.updated_at
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.id
        WHERE o.product_id IS NOT NULL
    """))

    # 5. Set total_price from existing price * quantity
    connection.execute(sa.text("""
        UPDATE orders SET total_price = COALESCE(price, 0) * COALESCE(quantity, 1)
    """))

    # 6. Set default value for total_price
    op.alter_column('orders', 'total_price', nullable=False, server_default='0')


def downgrade() -> None:
    # Remove total_price column
    op.drop_column('orders', 'total_price')

    # Restore non-nullable constraints on orders fields
    op.alter_column('orders', 'quantity', existing_type=sa.Integer(), nullable=False)
    op.alter_column('orders', 'price', existing_type=sa.Integer(), nullable=False)
    op.alter_column('orders', 'product_name', existing_type=sa.String(length=200), nullable=False)
    op.alter_column('orders', 'product_id', existing_type=sa.UUID(as_uuid=False), nullable=False)

    # Drop order_items table
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_table('order_items')
