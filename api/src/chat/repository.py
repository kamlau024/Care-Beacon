"""Owner-scoped Postgres repository for threads and messages.

Every owner-scoped method matches on ``owner_key``; a thread owned by someone
else is indistinguishable from a missing one (None / False / ThreadNotFound).
Each method opens its own connection.
"""

import uuid
from typing import Callable, Optional

import psycopg
from psycopg.types.json import Jsonb

from src.chat.models import Message, Thread, ThreadSettings, ThreadSummary


class ThreadNotFound(Exception):
    """The thread does not exist or does not belong to the caller."""


def new_thread_id() -> str:
    return "thr_" + uuid.uuid4().hex


def new_message_id() -> str:
    return "msg_" + uuid.uuid4().hex


def _thread(row: dict) -> Thread:
    return Thread(
        id=row["id"],
        owner_key=row["owner_key"],
        title=row["title"],
        settings=ThreadSettings(**row["settings"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message(row: dict) -> Message:
    return Message(
        id=row["id"],
        thread_id=row["thread_id"],
        role=row["role"],
        content=row["content"],
        citations=row["citations"],
        settings_delta=row["settings_delta"],
        status=row["status"],
        tokens=row["tokens"],
        cost=float(row["cost"]) if row["cost"] is not None else None,
        created_at=row["created_at"],
    )


def _jsonb(value):
    return Jsonb(value) if value is not None else None


_INSERT_MESSAGE = """
    INSERT INTO messages
        (id, thread_id, role, content, citations, settings_delta, status, tokens, cost)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING *
"""


class ThreadRepository:
    def __init__(self, connect: Callable[[], psycopg.Connection]):
        self._connect = connect

    def create_thread(self, owner_key: str, settings: ThreadSettings) -> Thread:
        with self._connect() as conn:
            row = conn.execute(
                "INSERT INTO threads (id, owner_key, settings) VALUES (%s, %s, %s) RETURNING *",
                (new_thread_id(), owner_key, Jsonb(settings.model_dump())),
            ).fetchone()
        return _thread(row)

    def get_thread(self, thread_id: str, owner_key: str) -> Optional[Thread]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM threads WHERE id = %s AND owner_key = %s",
                (thread_id, owner_key),
            ).fetchone()
        return _thread(row) if row else None

    def list_threads(self, owner_key: str) -> list[ThreadSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.id, t.title,
                       coalesce(max(m.created_at), t.created_at) AS last_activity_at,
                       count(m.id)::int AS message_count
                FROM threads t
                LEFT JOIN messages m ON m.thread_id = t.id
                WHERE t.owner_key = %s
                GROUP BY t.id
                ORDER BY last_activity_at DESC, t.id
                """,
                (owner_key,),
            ).fetchall()
        return [ThreadSummary(**r) for r in rows]

    def list_messages(self, thread_id: str) -> list[Message]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE thread_id = %s ORDER BY created_at, id",
                (thread_id,),
            ).fetchall()
        return [_message(r) for r in rows]

    def append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        *,
        citations=None,
        settings_delta=None,
        status: str = "complete",
        tokens=None,
        cost=None,
    ) -> Message:
        with self._connect() as conn:
            row = self._insert_message(
                conn, thread_id, role, content, citations, settings_delta, status, tokens, cost
            )
        return _message(row)

    @staticmethod
    def _insert_message(
        conn, thread_id, role, content, citations, settings_delta, status, tokens, cost
    ) -> dict:
        row = conn.execute(
            _INSERT_MESSAGE,
            (
                new_message_id(),
                thread_id,
                role,
                content,
                _jsonb(citations),
                _jsonb(settings_delta),
                status,
                tokens,
                cost,
            ),
        ).fetchone()
        conn.execute("UPDATE threads SET updated_at = now() WHERE id = %s", (thread_id,))
        return row

    def rename_thread(self, thread_id: str, owner_key: str, title: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE threads SET title = %s WHERE id = %s AND owner_key = %s",
                (title, thread_id, owner_key),
            )
            return cur.rowcount > 0

    def set_title_if_empty(self, thread_id: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE threads SET title = %s WHERE id = %s AND title IS NULL",
                (title, thread_id),
            )

    def delete_thread(self, thread_id: str, owner_key: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM threads WHERE id = %s AND owner_key = %s",
                (thread_id, owner_key),
            )
            return cur.rowcount > 0

    def update_settings(
        self, thread_id: str, owner_key: str, settings: ThreadSettings
    ) -> Optional[Message]:
        # One transaction (the connection context manager commits on success,
        # rolls back on error): the settings change and its marker land together.
        with self._connect() as conn:
            row = conn.execute(
                "SELECT settings FROM threads WHERE id = %s AND owner_key = %s FOR UPDATE",
                (thread_id, owner_key),
            ).fetchone()
            if row is None:
                raise ThreadNotFound(thread_id)
            before = ThreadSettings(**row["settings"])
            if before == settings:
                return None
            conn.execute(
                "UPDATE threads SET settings = %s WHERE id = %s",
                (Jsonb(settings.model_dump()), thread_id),
            )
            msg = self._insert_message(
                conn,
                thread_id,
                "settings",
                "",
                None,
                {"before": before.model_dump(), "after": settings.model_dump()},
                "complete",
                None,
                None,
            )
        return _message(msg)
