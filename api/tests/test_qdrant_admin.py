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
