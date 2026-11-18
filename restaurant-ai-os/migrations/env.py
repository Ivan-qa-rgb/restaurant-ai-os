import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context
from sqlalchemy import create_engine
from app.db import Base, DATABASE_URL
import app.models  # noqa: F401  (регистрация таблиц)

with create_engine(DATABASE_URL).connect() as conn:
    context.configure(connection=conn, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
