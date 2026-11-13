"""Hard guard that Postgres test connections are confined to the test schema.

``options=-c search_path=...`` is honoured only on an unpooled connection; a
pooled (PgBouncer) URL silently drops it, and unqualified statements would
then land in ``public``, which may be production. Fail hard, never skip.
"""


def assert_test_schema(conn, test_schema: str) -> None:
    """Raise unless ``current_schema()`` on ``conn`` is ``test_schema``."""
    row = conn.execute("SELECT current_schema()").fetchone()
    current = row["current_schema"] if isinstance(row, dict) else (row[0] if row else None)
    if current != test_schema:
        raise RuntimeError(
            f"DB test connection is not confined to the test schema "
            f"(current_schema={current!r}). TEST_DATABASE_URL must be an unpooled "
            f"URL (ideally a Neon test branch); refusing to run."
        )
