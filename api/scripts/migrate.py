"""Apply SQL migrations from api/migrations/ in filename order.

Usage: python scripts/migrate.py   (from api/; see `make migrate`)
Connects with DATABASE_URL_UNPOOLED when set (DDL should bypass the pooler),
else DATABASE_URL. Prints the filenames it applied.
"""

import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path) -> list[str]:
    """Apply unapplied *.sql files in order; return the filenames applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    conn.commit()
    done = {r[0] if isinstance(r, tuple) else r["filename"]
            for r in conn.execute("SELECT filename FROM schema_migrations")}
    conn.commit()
    applied = []
    for path in sorted(Path(migrations_dir).glob("*.sql")):
        if path.name in done:
            continue
        # One transaction per file: the DDL and its record commit together.
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
            )
        applied.append(path.name)
    return applied


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    url = os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("DATABASE_URL")
    if not url:
        print("Neither DATABASE_URL_UNPOOLED nor DATABASE_URL is set", file=sys.stderr)
        return 1
    with psycopg.connect(url) as conn:
        for name in apply_migrations(conn, MIGRATIONS_DIR):
            print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
