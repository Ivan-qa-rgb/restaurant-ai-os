"""Базовая схема (явные операции). Id ревизии прежний: базы, уже прошедшие старую 0001
(create_all), имеют ту же схему и не затрагиваются."""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.create_table("organizations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("timezone_name", sa.String(64), nullable=False),
        sa.Column("open_time", sa.Time, nullable=False),
        sa.Column("close_time", sa.Time, nullable=False))
    op.create_table("users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("pw_hash", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False))
    op.create_index("ix_users_org_id", "users", ["org_id"])
    op.create_table("sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False))
    op.create_table("dining_tables",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False))
    op.create_index("ix_dining_tables_org_id", "dining_tables", ["org_id"])
    op.create_table("reservations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("table_id", sa.Integer, sa.ForeignKey("dining_tables.id"), nullable=False),
        sa.Column("guest_name", sa.String(100), nullable=False),
        sa.Column("party_size", sa.Integer, nullable=False),
        sa.Column("start_at", sa.DateTime, nullable=False),
        sa.Column("end_at", sa.DateTime, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("idempotency_key", sa.String(80)),
        sa.UniqueConstraint("org_id", "idempotency_key", name="uq_res_idem"))
    op.create_index("ix_reservations_org_id", "reservations", ["org_id"])
    op.create_index("ix_res_table_time", "reservations", ["table_id", "start_at", "end_at"])
    op.create_table("audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("at", sa.DateTime, nullable=False),
        sa.Column("org_id", sa.Integer), sa.Column("user_id", sa.Integer),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("object_id", sa.Integer))
    op.create_table("dishes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_kop", sa.Integer, nullable=False),
        sa.Column("available", sa.Boolean, nullable=False),
        sa.Column("ingredients", sa.Text, nullable=False),
        sa.Column("allergens", sa.String(200), nullable=False),
        sa.Column("card_status", sa.String(10), nullable=False),
        sa.Column("verified_by", sa.Integer),
        sa.Column("verified_at", sa.DateTime),
        sa.Column("version", sa.Integer, nullable=False))
    op.create_index("ix_dishes_org_id", "dishes", ["org_id"])


def downgrade():
    for t in ("dishes", "audit_log", "reservations", "dining_tables", "sessions",
              "users", "organizations"):
        op.drop_table(t)
