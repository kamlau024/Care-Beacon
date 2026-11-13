"""Postgres connection helpers.

DATABASE_URL must be Neon's *pooled* connection string: serverless functions
open many short-lived connections, which the pooler absorbs.
"""

import os

import psycopg
from loguru import logger
from psycopg.rows import dict_row


class DatabaseUnavailable(Exception):
    """Postgres is not configured or cannot be reached."""


def database_url() -> str | None:
    return os.getenv("DATABASE_URL") or None


def connect() -> psycopg.Connection:
    url = database_url()
    if not url:
        raise DatabaseUnavailable("DATABASE_URL is not set")
    try:
        return psycopg.connect(url, row_factory=dict_row, connect_timeout=5)
    except psycopg.Error as e:
        # Never include str(e): psycopg messages can quote the conninfo
        # (password, host, user). Log/raise the exception type only.
        raise DatabaseUnavailable(f"Postgres unreachable ({type(e).__name__})") from e


def db_healthy() -> bool:
    """Run SELECT 1; never raises."""
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"Health check: Postgres unavailable ({type(e).__name__})")
        return False
