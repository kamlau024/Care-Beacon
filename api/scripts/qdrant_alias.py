"""Show Qdrant collections and aliases, or point an alias at a collection.

    python scripts/qdrant_alias.py show
    python scripts/qdrant_alias.py point care-beacon-live care-beacon-medical-v2

``point`` is atomic: the app never sees the alias missing. To roll back, point
the alias at the previous collection (printed by ``point``). After switching,
clear the answer cache (``POST /api/v1/cache/clear``), since cached answers
were built from the old chunks.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import get_config  # noqa: E402
from src.storage.qdrant_admin import (  # noqa: E402
    UnsafeTargetError,
    alias_map,
    collection_counts,
    point_alias,
)
from src.storage.qdrant_db import QdrantVectorDatabase  # noqa: E402


def show(client, serving_name: str) -> None:
    aliases = alias_map(client)
    counts = collection_counts(client)
    print("Collections:")
    for name, count in sorted(counts.items()):
        behind = sorted(a for a, c in aliases.items() if c == name)
        print(f"  {name:<32}{count:>10,} points" + (f"   <- {', '.join(behind)}" if behind else ""))
    print(f"App serves: {serving_name} -> {aliases.get(serving_name, serving_name)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    pt = sub.add_parser("point")
    pt.add_argument("alias")
    pt.add_argument("collection")
    pt.add_argument("--allow-empty", action="store_true", help="Allow pointing at an empty collection")
    pt.add_argument("--yes", action="store_true", help="Don't ask for confirmation")
    args = ap.parse_args(argv)

    serving_name = get_config().get("vector_db.collection_name")
    client = QdrantVectorDatabase(create_if_missing=False).client

    if args.command == "show":
        show(client, serving_name)
        return 0

    current = alias_map(client).get(args.alias)
    print(f"{args.alias}: {current or '(none)'} -> {args.collection}")
    if args.alias == serving_name:
        print("⚠️  The app reads this alias: production and previews switch immediately.")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        print("Aborted.")
        return 1
    try:
        previous = point_alias(client, args.alias, args.collection, allow_empty=args.allow_empty)
    except UnsafeTargetError as e:
        print(f"❌ {e}")
        return 2
    print(f"✅ {args.alias} -> {args.collection}")
    if previous:
        print(f"   Roll back with: python scripts/qdrant_alias.py point {args.alias} {previous}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
