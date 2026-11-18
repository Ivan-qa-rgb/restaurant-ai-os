import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade():
    op.create_table("orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("table_id", sa.Integer, sa.ForeignKey("dining_tables.id")),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_by", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("idempotency_key", sa.String(80)),
        sa.UniqueConstraint("org_id", "idempotency_key", name="uq_order_idem"))
    op.create_index("ix_orders_org_id", "orders", ["org_id"])
    op.create_table("order_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("dish_id", sa.Integer, sa.ForeignKey("dishes.id"), nullable=False),
        sa.Column("dish_name", sa.String(120), nullable=False),
        sa.Column("unit_price_kop", sa.Integer, nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("idempotency_key", sa.String(80)),
        sa.UniqueConstraint("order_id", "idempotency_key", name="uq_item_idem"))
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_org_id", "order_items", ["org_id"])


def downgrade():
    op.drop_table("order_items")
    op.drop_table("orders")
