"""Tests for the re-ingest safety checks and atomic alias switch."""

from unittest.mock import MagicMock

import pytest

from src.storage.qdrant_admin import UnsafeTargetError, check_ingest_target, point_alias

ALIASES = {"care-beacon-live": "care-beacon-medical"}
COUNTS = {"care-beacon-medical": 524_570, "care-beacon-medical-v2": 0, "scratch": 10}


def check(target, reset=False, resume=False, aliases=ALIASES, counts=COUNTS):
    check_ingest_target(target, "care-beacon-live", aliases, counts, reset=reset, resume=resume)


def test_new_or_empty_collection_is_allowed():
    check("care-beacon-medical-v2")
    check("brand-new")


@pytest.mark.parametrize("flags", [{}, {"reset": True}, {"resume": True}])
def test_refuses_the_served_alias_and_its_collection(flags):
    with pytest.raises(UnsafeTargetError, match="alias"):
        check("care-beacon-live", **flags)
    with pytest.raises(UnsafeTargetError, match="app serves"):
        check("care-beacon-medical", **flags)


def test_refuses_served_name_when_config_names_a_collection_directly():
    with pytest.raises(UnsafeTargetError, match="app serves"):
        check("care-beacon-live", aliases={}, counts={**COUNTS, "care-beacon-live": 3})


@pytest.mark.parametrize("flags", [{}, {"reset": True}])
def test_refuses_everything_until_the_served_alias_exists(flags):
    """With no alias yet, the live collection can't be identified, so a
    --reset of care-beacon-medical must not be possible."""
    with pytest.raises(UnsafeTargetError, match="Create it first"):
        check("care-beacon-medical", aliases={}, **flags)
    with pytest.raises(UnsafeTargetError, match="Create it first"):
        check("care-beacon-medical-v2", aliases={}, **flags)


def test_refuses_a_collection_behind_another_alias():
    with pytest.raises(UnsafeTargetError, match="behind alias"):
        check("scratch", reset=True, aliases={**ALIASES, "other": "scratch"})


def test_non_empty_collection_needs_reset_or_resume():
    with pytest.raises(UnsafeTargetError, match="--reset"):
        check("scratch")
    check("scratch", reset=True)
    check("scratch", resume=True)


def _client(aliases, counts):
    client = MagicMock()
    client.get_aliases.return_value = MagicMock(
        aliases=[MagicMock(alias_name=a, collection_name=c) for a, c in aliases.items()]
    )
    collections = []
    for name in counts:
        m = MagicMock()
        m.name = name
        collections.append(m)
    client.get_collections.return_value = MagicMock(collections=collections)
    client.get_collection.side_effect = lambda name: MagicMock(points_count=counts[name])
    return client


def test_point_alias_switches_in_one_atomic_call():
    client = _client(ALIASES, {"care-beacon-medical": 5, "care-beacon-medical-v2": 4})

    previous = point_alias(client, "care-beacon-live", "care-beacon-medical-v2")

    assert previous == "care-beacon-medical"
    client.update_collection_aliases.assert_called_once()
    ops = client.update_collection_aliases.call_args.kwargs["change_aliases_operations"]
    assert ops[0].delete_alias.alias_name == "care-beacon-live"
    assert ops[1].create_alias.alias_name == "care-beacon-live"
    assert ops[1].create_alias.collection_name == "care-beacon-medical-v2"


def test_point_alias_creates_a_new_alias():
    client = _client({}, {"care-beacon-medical": 5})

    assert point_alias(client, "care-beacon-live", "care-beacon-medical") is None
    ops = client.update_collection_aliases.call_args.kwargs["change_aliases_operations"]
    assert len(ops) == 1


@pytest.mark.parametrize(
    "alias, collection, message",
    [
        ("care-beacon-live", "missing", "does not exist"),
        ("care-beacon-live", "empty", "is empty"),
        ("care-beacon-medical", "empty", "is a collection"),
    ],
)
def test_point_alias_refusals(alias, collection, message):
    client = _client({}, {"care-beacon-medical": 5, "empty": 0})

    with pytest.raises(UnsafeTargetError, match=message):
        point_alias(client, alias, collection)
    assert not client.update_collection_aliases.called


# --- local build + copy ------------------------------------------------------

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import Distance, PointStruct, VectorParams  # noqa: E402

from src.storage.qdrant_admin import (  # noqa: E402
    LOCAL_QDRANT_URL,
    check_copy_target,
    copy_points,
    endpoint,
)


def test_local_ingest_needs_no_served_alias_but_keeps_other_checks():
    check_ingest_target("v2", "care-beacon-live", {}, {}, require_serving=False)
    with pytest.raises(UnsafeTargetError, match="already holds"):
        check_ingest_target("v2", "care-beacon-live", {}, {"v2": 5}, require_serving=False)


def test_endpoint(monkeypatch):
    monkeypatch.delenv("QDRANT_LOCAL_URL", raising=False)
    assert endpoint("cloud") == (None, None)
    assert endpoint("local")[0] == LOCAL_QDRANT_URL
    monkeypatch.setenv("QDRANT_LOCAL_URL", "http://127.0.0.1:7000")
    assert endpoint("local")[0] == "http://127.0.0.1:7000"
    with pytest.raises(ValueError):
        endpoint("prod")


def test_copy_target_refuses_aliases_and_non_empty():
    check_copy_target("v2", ALIASES, COUNTS)
    with pytest.raises(UnsafeTargetError, match="is an alias"):
        check_copy_target("care-beacon-live", ALIASES, COUNTS)
    with pytest.raises(UnsafeTargetError, match="behind alias"):
        check_copy_target("care-beacon-medical", ALIASES, COUNTS, resume=True)
    with pytest.raises(UnsafeTargetError, match="already holds"):
        check_copy_target("scratch", ALIASES, COUNTS)
    check_copy_target("scratch", ALIASES, COUNTS, resume=True)


def _client_with(n):
    client = QdrantClient(":memory:")
    for name in ("src", "dst"):
        client.create_collection(name, vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    client.upsert("src", points=[
        PointStruct(id=i, vector=[float(i), 1.0, 0.0, 0.5], payload={"chunk_id": f"a_p{i}"}) for i in range(n)
    ])
    return client


def test_copy_points_copies_ids_vectors_and_payloads():
    client = _client_with(23)
    calls = []
    copied = copy_points(client, "src", client, "dst", batch_size=5, on_batch=lambda c, o: calls.append((c, o)))
    assert copied == 23
    assert client.count("dst").count == 23
    assert calls[-1] == (23, None)
    src = client.retrieve("src", ids=[7], with_vectors=True)[0]
    dst = client.retrieve("dst", ids=[7], with_vectors=True)[0]
    assert dst.payload == {"chunk_id": "a_p7"}
    assert dst.vector == pytest.approx(src.vector)


def test_copy_points_resumes_from_offset():
    client = _client_with(23)
    offsets = []
    copy_points(client, "src", client, "dst", batch_size=10, on_batch=lambda c, o: offsets.append(o))
    client.delete_collection("dst")
    client.create_collection("dst", vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    copied = copy_points(client, "src", client, "dst", batch_size=10, offset=offsets[0])
    assert copied == 13
    assert client.count("dst").count == 13


def test_partitions_cover_every_point_exactly_once():
    from src.storage.qdrant_admin import partition_offsets
    client = _client_with(103)
    ranges = partition_offsets(client, "src", 4)
    assert len(ranges) == 4 and ranges[0][0] is None and ranges[-1][1] is None
    counts = [copy_points(client, "src", client, "dst", batch_size=7, offset=a, stop=b) for a, b in ranges]
    assert sum(counts) == 103
    assert client.count("dst").count == 103


def test_copy_points_retries_a_failed_upsert():
    client = _client_with(10)
    dest = MagicMock()
    dest.upsert.side_effect = [RuntimeError("No space left on device"), None]
    assert copy_points(client, "src", dest, "dst", batch_size=50, retry_wait=0) == 10
    assert dest.upsert.call_count == 2
    dest.upsert.side_effect = RuntimeError("still full")
    with pytest.raises(RuntimeError):
        copy_points(client, "src", dest, "dst", batch_size=50, retries=1, retry_wait=0)
