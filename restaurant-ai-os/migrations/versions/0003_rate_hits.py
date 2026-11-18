import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    op.create_table("rate_hits",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("at", sa.DateTime, nullable=False))
    op.create_index("ix_rate_hits_key_at", "rate_hits", ["key", "at"])


def downgrade():
    op.drop_table("rate_hits")
