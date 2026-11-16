"""Collection and alias management for re-ingesting Qdrant without downtime.

The app reads through an alias (``vector_db.collection_name``, e.g.
``care-beacon-live``). A re-ingest writes a brand-new collection, gets checked,
and then the alias is switched to it in one atomic call. Rolling back is
switching the alias back. Nothing here runs inside the API; it is used by
``scripts/ingest.py``, ``scripts/qdrant_alias.py`` and ``scripts/qdrant_copy.py``.

When the cloud cluster has no room for a second collection, the new one is
built in a local Qdrant (``make qdrant-local``) and copied up with
``scripts/qdrant_copy.py``; see docs/INGESTION_CONFIGURATION.md.
"""

import os
import time
from typing import Callable, Dict, List, Optional, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    PointStruct,
)

# The local Qdrant started by `make qdrant-local` (Docker, bound to 127.0.0.1).
LOCAL_QDRANT_URL = "http://127.0.0.1:6333"
LOCAL_QDRANT_API_KEY = "local-dev-key"
TARGETS = ("cloud", "local")


class UnsafeTargetError(RuntimeError):
    """Raised when an operation would change the data the app is serving."""


def endpoint(target: str) -> Tuple[Optional[str], Optional[str]]:
    """(url, api_key) for ``target``. ``cloud`` returns (None, None), which
    makes ``QdrantVectorDatabase`` use its usual config / QDRANT_URL lookup."""
    if target == "local":
        return (
            os.getenv("QDRANT_LOCAL_URL", LOCAL_QDRANT_URL),
            os.getenv("QDRANT_LOCAL_API_KEY", LOCAL_QDRANT_API_KEY),
        )
    if target == "cloud":
        return None, None
    raise ValueError(f"Unknown Qdrant target {target!r}; expected one of {TARGETS}")


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
    require_serving: bool = True,
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
        require_serving: Refuse unless ``serving_name`` exists. False only for
            a local Qdrant, which serves nothing.

    Raises:
        UnsafeTargetError: If the ingest must not go ahead.
    """
    if require_serving and serving_name not in aliases and serving_name not in counts:
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


def check_copy_target(
    target: str,
    aliases: Dict[str, str],
    counts: Dict[str, int],
    resume: bool = False,
) -> None:
    """Refuse a copy into an alias, a collection behind an alias, or a
    non-empty collection (unless continuing an interrupted copy)."""
    if target in aliases:
        raise UnsafeTargetError(f"{target!r} is an alias (-> {aliases[target]!r}). Copy into a collection.")
    if target in aliases.values():
        others = sorted(a for a, c in aliases.items() if c == target)
        raise UnsafeTargetError(f"{target!r} is behind alias(es) {others}; it may be serving traffic.")
    if counts.get(target, 0) > 0 and not resume:
        raise UnsafeTargetError(
            f"{target!r} already holds {counts[target]:,} points. Pass --resume-from to continue "
            "an interrupted copy, or pick a new collection name."
        )


def copy_points(
    source: QdrantClient,
    source_collection: str,
    dest: QdrantClient,
    dest_collection: str,
    batch_size: int = 256,
    offset=None,
    on_batch: Optional[Callable[[int, object], None]] = None,
    stop=None,
    retries: int = 5,
    retry_wait: float = 5.0,
) -> int:
    """Copy every point (id, vector, payload) from one collection to another.

    Ids are kept, so a copy can be restarted from any scroll offset and points
    already copied are simply overwritten. ``on_batch(copied_so_far,
    next_offset)`` is called after each batch; ``next_offset`` is what to pass
    as ``offset`` to continue after a failure (None once finished).
    ``stop`` (a point id) ends the copy just before that id, so several
    copies can split one collection (see ``partition_offsets``). A failed
    upsert is retried ``retries`` times: a nearly full cluster returns 500s
    while its optimizer holds temporary disk, then recovers.

    Returns:
        Number of points copied in this call.
    """
    copied = 0
    while True:
        records, next_offset = source.scroll(
            collection_name=source_collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        if stop is not None:
            ids = [str(r.id) for r in records]
            if str(stop) in ids:
                records, next_offset = records[: ids.index(str(stop))], None
            elif next_offset is not None and str(next_offset) == str(stop):
                next_offset = None
        if records:
            points = [PointStruct(id=r.id, vector=r.vector, payload=r.payload) for r in records]
            for attempt in range(retries + 1):
                try:
                    dest.upsert(collection_name=dest_collection, points=points, wait=True)
                    break
                except Exception:
                    if attempt == retries:
                        raise
                    time.sleep(retry_wait * (attempt + 1))
            copied += len(records)
        if on_batch:
            on_batch(copied, next_offset)
        if next_offset is None:
            return copied
        offset = next_offset


def partition_offsets(client: QdrantClient, collection: str, parts: int) -> List[Tuple[object, object]]:
    """Split a collection into ``parts`` (start, stop) id ranges in scroll
    order, for ``copy_points(offset=start, stop=stop)``. Reads ids only."""
    ids, offset = [], None
    while True:
        records, offset = client.scroll(
            collection_name=collection, limit=10_000, offset=offset, with_payload=False, with_vectors=False
        )
        ids.extend(r.id for r in records)
        if offset is None:
            break
    parts = max(1, min(parts, len(ids) or 1))
    step = len(ids) // parts
    starts = [None] + [ids[i * step] for i in range(1, parts)]
    return list(zip(starts, starts[1:] + [None]))


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
