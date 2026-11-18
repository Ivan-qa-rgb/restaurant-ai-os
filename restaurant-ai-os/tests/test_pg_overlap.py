"""Нужен PostgreSQL с применёнными миграциями (alembic upgrade head) и TEST_PG_URL."""
import os
from concurrent.futures import ProcessPoolExecutor
import pytest

PG = os.environ.get("TEST_PG_URL")
pytestmark = pytest.mark.skipif(not PG, reason="не задан TEST_PG_URL")


def _insert(args):
    url, oid, tid = args
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError
    try:
        with create_engine(url).begin() as conn:
            conn.execute(text(
                "INSERT INTO reservations (org_id, table_id, guest_name, party_size, start_at,"
                " end_at, status) VALUES (:o, :t, 'g', 2, '2040-01-01 19:00', '2040-01-01 20:30',"
                " 'confirmed')"), {"o": oid, "t": tid})
        return "ok"
    except IntegrityError:
        return "conflict"


def test_db_rejects_overlap_across_processes():
    from sqlalchemy import create_engine, text
    with create_engine(PG).begin() as conn:
        oid = conn.execute(text(
            "INSERT INTO organizations (name, timezone_name, open_time, close_time) "
            "VALUES ('pg', 'Europe/Moscow', '10:00', '23:00') RETURNING id")).scalar()
        tid = conn.execute(text(
            "INSERT INTO dining_tables (org_id, name, capacity, active) "
            "VALUES (:o, 'T', 4, true) RETURNING id"), {"o": oid}).scalar()
    with ProcessPoolExecutor(8) as ex:
        res = list(ex.map(_insert, [(PG, oid, tid)] * 8))
    assert res.count("ok") == 1 and res.count("conflict") == 7
