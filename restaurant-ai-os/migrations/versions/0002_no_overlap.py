"""PostgreSQL: запрет пересекающихся подтверждённых броней одного стола."""
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("ALTER TABLE reservations ADD CONSTRAINT res_no_overlap EXCLUDE USING gist "
               "(table_id WITH =, tsrange(start_at, end_at, '[)') WITH &&) "
               "WHERE (status = 'confirmed')")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE reservations DROP CONSTRAINT res_no_overlap")
