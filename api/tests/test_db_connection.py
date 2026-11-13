"""Unit tests for src.db.connection (no database needed)."""

from unittest.mock import MagicMock, patch

import psycopg
import pytest
from loguru import logger

from src.db.connection import DatabaseUnavailable, connect, database_url, db_healthy

SECRET_ERR = 'invalid connection option "x" near "password=hunter2 host=h.example"'


def test_database_url_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url() is None


def test_connect_raises_when_url_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseUnavailable):
        connect()


def test_connect_error_message_does_not_leak_psycopg_text(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:hunter2@h.example/db")
    with patch("src.db.connection.psycopg.connect", side_effect=psycopg.OperationalError(SECRET_ERR)):
        with pytest.raises(DatabaseUnavailable) as exc:
            connect()
    assert "hunter2" not in str(exc.value)
    assert "h.example" not in str(exc.value)
    assert "OperationalError" in str(exc.value)


def test_db_healthy_false_and_log_does_not_leak(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:hunter2@h.example/db")
    lines = []
    sink = logger.add(lambda m: lines.append(str(m)), level="DEBUG")
    try:
        with patch("src.db.connection.psycopg.connect", side_effect=psycopg.OperationalError(SECRET_ERR)):
            assert db_healthy() is False
    finally:
        logger.remove(sink)
    assert lines
    assert "hunter2" not in "".join(lines)
    assert "h.example" not in "".join(lines)


def test_db_healthy_true_on_select_1(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    conn = MagicMock()
    conn.__enter__.return_value = conn
    with patch("src.db.connection.psycopg.connect", return_value=conn):
        assert db_healthy() is True
    conn.execute.assert_called_once_with("SELECT 1")
