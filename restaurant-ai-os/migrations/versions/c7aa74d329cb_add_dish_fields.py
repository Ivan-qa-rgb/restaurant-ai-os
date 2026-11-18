"""add dish fields

Revision ID: c7aa74d329cb
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = 'c7aa74d329cb'
down_revision = '0005'


def upgrade():
    op.add_column('dishes', sa.Column('description', sa.Text(), nullable=False, server_default=''))
    op.add_column('dishes', sa.Column('category', sa.String(length=60), nullable=False, server_default='Другое'))
    op.add_column('dishes', sa.Column('image_url', sa.String(length=300), nullable=False, server_default=''))
    op.add_column('dishes', sa.Column('weight_g', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('dishes', sa.Column('is_vegetarian', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('dishes', sa.Column('is_spicy', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('dishes', 'is_spicy')
    op.drop_column('dishes', 'is_vegetarian')
    op.drop_column('dishes', 'weight_g')
    op.drop_column('dishes', 'image_url')
    op.drop_column('dishes', 'category')
    op.drop_column('dishes', 'description')
