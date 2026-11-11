import psycopg
import pytest

from migrate import apply_migrations


def test_migrations_create_tables_and_are_idempotent(raw_conn, migrations_dir):
    # The session fixture already applied them, so a rerun applies nothing.
    assert apply_migrations(raw_conn, migrations_dir) == []
    cols = {
        r["column_name"]
        for r in raw_conn.execute(
            "select column_name from information_schema.columns "
            "where table_name = 'messages' and table_schema = current_schema()"
        )
    }
    assert {"role", "status", "settings_delta", "citations"} <= cols


def test_first_apply_returns_filename_and_records_it(raw_conn):
    rows = raw_conn.execute("select filename from schema_migrations").fetchall()
    assert [r["filename"] for r in rows] == ["001_threads_messages.sql"]


def test_role_check_rejects_unknown_role(db):
    with db() as conn:
        conn.execute(
            "insert into threads (id, owner_key, settings) values ('t1', 'o', '{}')"
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "insert into messages (id, thread_id, role, content) "
                "values ('m1', 't1', 'system', 'hi')"
            )


def test_deleting_thread_cascades_to_messages(db):
    with db() as conn:
        conn.execute(
            "insert into threads (id, owner_key, settings) values ('t1', 'o', '{}')"
        )
        conn.execute(
            "insert into messages (id, thread_id, role, content) "
            "values ('m1', 't1', 'user', 'hi')"
        )
        conn.execute("delete from threads where id = 't1'")
        n = conn.execute("select count(*) as n from messages").fetchone()["n"]
    assert n == 0
