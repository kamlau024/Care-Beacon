"""Collection and alias management for re-ingesting Qdrant without downtime.

The app reads through an alias (``vector_db.collection_name``, e.g.
``care-beacon-live``). A re-ingest writes a brand-new collection, gets checked,
and then the alias is switched to it in one atomic call. Rolling back is
switching the alias back. Nothing here runs inside the API; it is used by
``scripts/ingest.py`` and ``scripts/qdrant_alias.py``.
"""

from typing import Dict, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
)


class UnsafeTargetError(RuntimeError):
    """Raised when an operation would change the data the app is serving."""


def alias_map(client: QdrantClient) -> Dict[str, str]:
    """Every alias and the collection it points to."""
    return {a.alias_name: a.collection_name for a in client.get_aliases().aliases}


def collection_counts(client: QdrantClient) -> Dict[str, int]:
    """Every collection and its point count."""
    return {
        c.name: client.get_collection(c.name).points_count or 0
        for c in client.get_collections().collections
    }


def serving_collection(serving_name: str, aliases: Dict[str, str]) -> str:
    """The collection the app actually reads: the alias target, or the name itself."""
    return aliases.get(serving_name, serving_name)


def check_ingest_target(
    target: str,
    serving_name: str,
    aliases: Dict[str, str],
    counts: Dict[str, int],
    reset: bool = False,
    resume: bool = False,
) -> None:
    """Refuse an ingest that could touch the collection the app is serving.

    Args:
        target: Collection the ingest would write to.
        serving_name: ``vector_db.collection_name`` from config (an alias or a
            collection) -- what the API reads.
        aliases: ``alias_map()`` output.
        counts: ``collection_counts()`` output.
        reset: The caller asked to delete and recreate ``target`` first.
        resume: The caller is continuing an earlier, interrupted run into
            ``target`` (upserts are idempotent, so rewriting points is safe).

    Raises:
        UnsafeTargetError: If the ingest must not go ahead.
    """
    if serving_name not in aliases and serving_name not in counts:
        # Without this the live collection can't be identified, and a --reset
        # could delete it while the app (or an older deploy) still reads it.
        raise UnsafeTargetError(
            f"The app's {serving_name!r} is neither an alias nor a collection in Qdrant. "
            f"Create it first: scripts/qdrant_alias.py point {serving_name} <collection being served>."
        )
    if target in aliases:
        raise UnsafeTargetError(
            f"{target!r} is an alias (-> {aliases[target]!r}). Ingest into a concrete, "
            "new collection, then switch the alias with scripts/qdrant_alias.py."
        )
    live = serving_collection(serving_name, aliases)
    if target in (serving_name, live):
        raise UnsafeTargetError(
            f"{target!r} is the collection the app serves ({serving_name!r} -> {live!r}). "
            "Ingest into a new collection instead."
        )
    if target in aliases.values():
        others = sorted(a for a, c in aliases.items() if c == target)
        raise UnsafeTargetError(
            f"{target!r} is behind alias(es) {others}. Switch them away before reusing it."
        )
    if counts.get(target, 0) > 0 and not (reset or resume):
        raise UnsafeTargetError(
            f"{target!r} already holds {counts[target]:,} points. Pass --reset to rebuild "
            "it from scratch or --resume to continue an interrupted run."
        )


def point_alias(
    client: QdrantClient,
    alias: str,
    collection: str,
    allow_empty: bool = False,
) -> Optional[str]:
    """Point ``alias`` at ``collection`` atomically and return its previous target.

    Raises:
        UnsafeTargetError: If ``collection`` is missing, empty (unless
            ``allow_empty``), or ``alias`` is already a collection's name.
    """
    counts = collection_counts(client)
    if alias in counts:
        raise UnsafeTargetError(f"{alias!r} is a collection, so it can't also be an alias.")
    if collection not in counts:
        raise UnsafeTargetError(f"Collection {collection!r} does not exist.")
    if counts[collection] == 0 and not allow_empty:
        raise UnsafeTargetError(f"Collection {collection!r} is empty.")

    previous = alias_map(client).get(alias)
    operations = []
    if previous is not None:
        operations.append(DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=alias)))
    operations.append(
        CreateAliasOperation(create_alias=CreateAlias(collection_name=collection, alias_name=alias))
    )
    # One request: Qdrant applies both operations together, so readers never
    # see the alias missing.
    client.update_collection_aliases(change_aliases_operations=operations)
    return previous
