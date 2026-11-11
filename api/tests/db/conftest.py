"""Fixtures for Postgres tests.

These run only when TEST_DATABASE_URL is set, and never read DATABASE_URL.
The target database may also be a production database, so every fixture works
exclusively inside a throwaway ``test_<random>`` schema it creates itself:
each statement is either schema-qualified or runs on a connection whose
search_path contains only that schema. Nothing here touches ``public``.
"""

import os
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT / "scripts"))

from migrate import apply_migrations  # noqa: E402


@pytest.fixture(scope="session")
def migrations_dir() -> Path:
    return API_ROOT / "migrations"


@pytest.fixture(scope="session")
def test_schema():
    # Hex only, so interpolating into SQL identifiers is safe.
    return f"test_{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="session")
def raw_conn(migrations_dir, test_schema):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    conn = psycopg.connect(url, row_factory=dict_row, autocommit=True)
    try:
        conn.execute(f"CREATE SCHEMA {test_schema}")
        # Only the test schema: unqualified names can never resolve to public.
        conn.execute(f"SET search_path TO {test_schema}")
        apply_migrations(conn, migrations_dir)
        yield conn
    finally:
        conn.execute(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE")
        conn.close()


@pytest.fixture
def db(raw_conn, test_schema):
    """A ``connect`` callable bound to the test schema, with tables emptied."""
    url = os.environ["TEST_DATABASE_URL"]
    raw_conn.execute(f"TRUNCATE {test_schema}.messages, {test_schema}.threads")

    def connect() -> psycopg.Connection:
        return psycopg.connect(
            url,
            row_factory=dict_row,
            options=f"-c search_path={test_schema}",
        )

    return connect
