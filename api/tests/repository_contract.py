"""Behaviour suite shared by InMemoryThreadRepository and ThreadRepository.

Each consumer module defines a ``repo`` fixture and star-imports the tests.
"""

import pytest

from src.chat.models import ThreadSettings
from src.chat.repository import ThreadNotFound

OWNER = "owner-a"
OTHER = "owner-b"


def make_settings(**kw):
    base = {"sources": ["BC Cancer"], "min_similarity": 0.5}
    base.update(kw)
    return ThreadSettings(**base)


def test_create_and_get_roundtrip(repo):
    t = repo.create_thread(OWNER, make_settings())
    assert t.id.startswith("thr_")
    got = repo.get_thread(t.id, OWNER)
    assert got is not None and got.id == t.id
    assert got.title is None
    assert got.settings == make_settings()


def test_other_owner_cannot_read_rename_delete_or_update(repo):
    t = repo.create_thread(OWNER, make_settings())
    assert repo.get_thread(t.id, OTHER) is None
    assert repo.rename_thread(t.id, OTHER, "x") is False
    assert repo.delete_thread(t.id, OTHER) is False
    with pytest.raises(ThreadNotFound):
        repo.update_settings(t.id, OTHER, make_settings(min_similarity=0.9))
    # untouched for the real owner
    assert repo.get_thread(t.id, OWNER).title is None
    assert repo.get_thread(t.id, OWNER).settings == make_settings()
    assert repo.list_messages(t.id) == []
    assert repo.list_threads(OTHER) == []


def test_missing_thread_looks_like_other_owner(repo):
    assert repo.get_thread("thr_nope", OWNER) is None
    assert repo.rename_thread("thr_nope", OWNER, "x") is False
    assert repo.delete_thread("thr_nope", OWNER) is False
    with pytest.raises(ThreadNotFound):
        repo.update_settings("thr_nope", OWNER, make_settings())


def test_list_threads_orders_by_latest_message(repo):
    a = repo.create_thread(OWNER, make_settings())
    b = repo.create_thread(OWNER, make_settings())
    assert [s.id for s in repo.list_threads(OWNER)] == [b.id, a.id]
    repo.append_message(a.id, "user", "hello")
    summaries = repo.list_threads(OWNER)
    assert [s.id for s in summaries] == [a.id, b.id]
    assert summaries[0].message_count == 1
    assert summaries[1].message_count == 0


def test_list_messages_oldest_first_and_fields(repo):
    t = repo.create_thread(OWNER, make_settings())
    repo.append_message(t.id, "user", "q")
    m = repo.append_message(
        t.id,
        "assistant",
        "a",
        citations=[{"n": 1}],
        status="interrupted",
        tokens=12,
        cost=0.5,
    )
    assert m.id.startswith("msg_")
    msgs = repo.list_messages(t.id)
    assert [x.content for x in msgs] == ["q", "a"]
    assert msgs[1].citations == [{"n": 1}]
    assert msgs[1].status == "interrupted"
    assert msgs[1].tokens == 12
    assert msgs[1].cost == 0.5
    assert msgs[0].status == "complete"


def test_delete_cascades_messages(repo):
    t = repo.create_thread(OWNER, make_settings())
    repo.append_message(t.id, "user", "q")
    assert repo.delete_thread(t.id, OWNER) is True
    assert repo.get_thread(t.id, OWNER) is None
    assert repo.list_messages(t.id) == []


def test_update_settings_writes_marker_with_before_and_after(repo):
    t = repo.create_thread(OWNER, make_settings())
    new = make_settings(sources=["BC Cancer", "Cleveland Clinic"], min_similarity=0.7)
    marker = repo.update_settings(t.id, OWNER, new)
    assert marker is not None
    assert marker.role == "settings"
    assert marker.content == ""
    assert marker.settings_delta == {
        "before": {"sources": ["BC Cancer"], "min_similarity": 0.5},
        "after": {
            "sources": ["BC Cancer", "Cleveland Clinic"],
            "min_similarity": 0.7,
        },
    }
    assert repo.get_thread(t.id, OWNER).settings == new
    assert [m.role for m in repo.list_messages(t.id)] == ["settings"]


def test_update_settings_unchanged_writes_no_marker(repo):
    t = repo.create_thread(OWNER, make_settings())
    assert repo.update_settings(t.id, OWNER, make_settings()) is None
    assert repo.list_messages(t.id) == []


def test_rename_and_set_title_if_empty_does_not_overwrite_a_rename(repo):
    t = repo.create_thread(OWNER, make_settings())
    repo.set_title_if_empty(t.id, "auto title")
    assert repo.get_thread(t.id, OWNER).title == "auto title"
    assert repo.rename_thread(t.id, OWNER, "mine") is True
    repo.set_title_if_empty(t.id, "auto again")
    assert repo.get_thread(t.id, OWNER).title == "mine"


def test_set_title_if_empty_fills_only_when_empty(repo):
    t = repo.create_thread(OWNER, make_settings())
    repo.set_title_if_empty(t.id, "first")
    repo.set_title_if_empty(t.id, "second")
    assert repo.get_thread(t.id, OWNER).title == "first"


def test_settings_validation():
    with pytest.raises(ValueError):
        ThreadSettings(sources=[], min_similarity=0.5)
    with pytest.raises(ValueError):
        ThreadSettings(sources=["Nowhere"], min_similarity=0.5)
    with pytest.raises(ValueError):
        ThreadSettings(sources=["BC Cancer"], min_similarity=1.5)
    with pytest.raises(ValueError):
        ThreadSettings(sources=["BC Cancer"], min_similarity=-0.1)
