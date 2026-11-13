"""Tests for the thread REST endpoints."""

import uuid

import pytest
from fastapi.testclient import TestClient

from src.api.chat_routes import get_repository
from src.api.main import app
from src.chat.models import ThreadSettings
from src.db.connection import DatabaseUnavailable
from tests.fakes import InMemoryThreadRepository

OWNER = str(uuid.uuid4())
OTHER = str(uuid.uuid4())
SETTINGS = ThreadSettings(sources=["BC Cancer"], min_similarity=0.5)


@pytest.fixture
def repo():
    return InMemoryThreadRepository()


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_repository] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.pop(get_repository, None)


def h(owner=OWNER):
    return {"X-Owner-Key": owner}


@pytest.fixture
def thread(repo):
    return repo.create_thread(OWNER, SETTINGS)


ENDPOINTS = [
    ("get", "/api/v1/threads", None),
    ("get", "/api/v1/threads/{id}", None),
    ("patch", "/api/v1/threads/{id}", {"title": "x"}),
    ("delete", "/api/v1/threads/{id}", None),
    ("patch", "/api/v1/threads/{id}/settings",
     {"sources": ["BC Cancer"], "min_similarity": 0.5}),
]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_missing_owner_header_is_400(client, thread, method, path, body):
    r = client.request(method, path.format(id=thread.id), json=body)
    assert r.status_code == 400


@pytest.mark.parametrize("bad", ["nope", str(uuid.uuid4()).upper(), ""])
def test_malformed_owner_header_is_400(client, bad):
    assert client.get("/api/v1/threads", headers=h(bad)).status_code == 400


@pytest.mark.parametrize("method,path,body", ENDPOINTS[1:])
def test_other_owner_and_missing_thread_get_identical_404(client, thread, method, path, body):
    other = client.request(method, path.format(id=thread.id), json=body, headers=h(OTHER))
    missing = client.request(method, path.format(id="thr_missing"), json=body, headers=h(OTHER))
    assert other.status_code == missing.status_code == 404
    a, b = other.json(), missing.json()
    a.pop("timestamp"), b.pop("timestamp")
    assert a == b


def test_list_threads_scoped_to_owner(client, repo, thread):
    repo.create_thread(OTHER, SETTINGS)
    repo.append_message(thread.id, "user", "hi")
    body = client.get("/api/v1/threads", headers=h()).json()
    assert [t["id"] for t in body["threads"]] == [thread.id]
    assert set(body["threads"][0]) == {"id", "title", "last_activity_at", "message_count"}
    assert body["threads"][0]["message_count"] == 1


def test_get_thread_detail(client, repo, thread):
    repo.append_message(thread.id, "user", "hello")
    body = client.get(f"/api/v1/threads/{thread.id}", headers=h()).json()
    assert body["id"] == thread.id
    assert body["settings"] == {"sources": ["BC Cancer"], "min_similarity": 0.5}
    assert [m["content"] for m in body["messages"]] == ["hello"]


def test_rename_trims_and_caps(client, thread):
    r = client.patch(f"/api/v1/threads/{thread.id}", json={"title": "  " + "a" * 250 + "  "}, headers=h())
    assert r.status_code == 200
    assert r.json() == {"id": thread.id, "title": "a" * 200}


@pytest.mark.parametrize("title", ["", "   "])
def test_rename_blank_is_422(client, thread, title):
    r = client.patch(f"/api/v1/threads/{thread.id}", json={"title": title}, headers=h())
    assert r.status_code == 422


def test_delete_thread(client, thread):
    assert client.delete(f"/api/v1/threads/{thread.id}", headers=h()).json() == {"ok": True}
    assert client.get(f"/api/v1/threads/{thread.id}", headers=h()).status_code == 404


def test_settings_unchanged_marker_null(client, thread):
    r = client.patch(f"/api/v1/threads/{thread.id}/settings", json=SETTINGS.model_dump(), headers=h())
    assert r.status_code == 200
    assert r.json() == {"settings": SETTINGS.model_dump(), "marker": None}


def test_settings_changed_returns_marker(client, thread):
    new = {"sources": ["BC Cancer", "Cleveland Clinic"], "min_similarity": 0.7}
    r = client.patch(f"/api/v1/threads/{thread.id}/settings", json=new, headers=h())
    body = r.json()
    assert body["settings"] == new
    assert body["marker"]["role"] == "settings"
    assert body["marker"]["settings_delta"]["before"] == SETTINGS.model_dump()
    assert body["marker"]["settings_delta"]["after"] == new


@pytest.mark.parametrize("body", [
    {"sources": ["Nope"], "min_similarity": 0.5},
    {"sources": [], "min_similarity": 0.5},
    {"sources": ["BC Cancer"], "min_similarity": 2},
])
def test_settings_invalid_is_422(client, thread, body):
    r = client.patch(f"/api/v1/threads/{thread.id}/settings", json=body, headers=h())
    assert r.status_code == 422


class _Down:
    def __getattr__(self, name):
        def fail(*a, **k):
            raise DatabaseUnavailable("postgres://user:secret@host/db unreachable")
        return fail


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_database_unavailable_is_503_without_detail(method, path, body):
    app.dependency_overrides[get_repository] = lambda: _Down()
    try:
        r = TestClient(app).request(method, path.format(id="thr_x"), json=body, headers=h())
    finally:
        app.dependency_overrides.pop(get_repository, None)
    assert r.status_code == 503
    assert "secret" not in r.text and "postgres" not in r.text
    assert set(r.json()) == {"error", "message", "timestamp"}


# ---------------------------------------------------------------- POST /api/v1/chat

from types import SimpleNamespace  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import src.api.main as main_module  # noqa: E402
from src.api.chat_routes import get_chat_service  # noqa: E402
from src.caching.redis_cache import RedisCache  # noqa: E402
from src.chat.prompt import load_chat_prompts  # noqa: E402
from src.chat.service import ChatService  # noqa: E402
from tests.test_chat_service import FakeLLM, FakeRetrieval  # noqa: E402

CHAT_BODY = {"message": "What are the side effects of radiation therapy?"}


def _stats(daily_cost=0.0):
    stats = MagicMock()
    stats.get_daily_cost.return_value = daily_cost
    return stats


@pytest.fixture
def chat_parts(repo):
    return SimpleNamespace(retrieval=FakeRetrieval(), llm=FakeLLM(), stats=_stats(), repo=repo)


@pytest.fixture
def chat_client(chat_parts):
    def build():
        return ChatService(
            repository=chat_parts.repo,
            retrieval_engine=chat_parts.retrieval,
            llm_client=chat_parts.llm,
            prompts=load_chat_prompts(),
            stats_store=chat_parts.stats,
            max_context_chunks=5,
            disclaimer="Disclaimer.",
        )

    app.dependency_overrides[get_chat_service] = build
    yield TestClient(app)
    app.dependency_overrides.pop(get_chat_service, None)


def _events(text):
    return [line[len("event: "):] for line in text.split("\n") if line.startswith("event: ")]


def test_chat_requires_owner_key(chat_client):
    assert chat_client.post("/api/v1/chat", json=CHAT_BODY).status_code == 400


def test_spend_cap_returns_429_before_any_model_call(chat_client, chat_parts, repo):
    chat_parts.stats.get_daily_cost.return_value = 1000.0
    r = chat_client.post("/api/v1/chat", json=CHAT_BODY, headers=h())
    assert r.status_code == 429
    assert r.json() == {
        "error": "DailyLimitReached",
        "message": "Today's chat limit has been reached. It resets at midnight UTC.",
    }
    assert chat_parts.retrieval.queries == []
    assert chat_parts.llm.stream_calls == [] and chat_parts.llm.utility_calls == []
    assert repo.list_threads(OWNER) == []


def test_chat_404_for_other_owners_thread(chat_client, repo):
    theirs = repo.create_thread(OTHER, SETTINGS)
    other = chat_client.post("/api/v1/chat", json={**CHAT_BODY, "thread_id": theirs.id}, headers=h())
    missing = chat_client.post("/api/v1/chat", json={**CHAT_BODY, "thread_id": "thr_x"}, headers=h())
    assert other.status_code == missing.status_code == 404
    assert repo.list_messages(theirs.id) == []


def test_chat_sets_thread_id_header_for_new_thread(chat_client, repo):
    r = chat_client.post("/api/v1/chat", json=CHAT_BODY, headers=h())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"
    [summary] = repo.list_threads(OWNER)
    assert r.headers["x-thread-id"] == summary.id
    assert _events(r.text) == ["status", "status", "citations", "token", "token", "token", "done"]
    roles = [m.role for m in repo.list_messages(summary.id)]
    assert roles == ["user", "assistant"]


def test_chat_existing_thread_streams_follow_up(chat_client, repo, thread):
    repo.append_message(thread.id, "user", "Earlier question")
    repo.append_message(thread.id, "assistant", "Earlier answer")
    r = chat_client.post("/api/v1/chat", json={**CHAT_BODY, "thread_id": thread.id}, headers=h())
    assert r.headers["x-thread-id"] == thread.id
    assert _events(r.text)[0] == "status" and '"stage":"rewriting"' in r.text


def test_chat_503_when_database_unavailable(chat_client, repo):
    def boom(*a, **kw):
        raise DatabaseUnavailable("x")

    repo.create_thread = boom
    r = chat_client.post("/api/v1/chat", json=CHAT_BODY, headers=h())
    assert r.status_code == 503


def test_answer_cache_never_used(client, repo, monkeypatch):
    """Real get_chat_service wiring from the AnswerGenerator; its cache is never read or written."""
    cache = MagicMock(spec=RedisCache)
    cache.stats_store = _stats()
    generator = SimpleNamespace(
        cache=cache,
        retrieval_engine=FakeRetrieval(),
        llm_client=FakeLLM(),
        config=SimpleNamespace(max_context_chunks=5, disclaimer_text="Ask disclaimer."),
    )
    monkeypatch.setattr(main_module, "_answer_generator", generator)
    r = client.post("/api/v1/chat", json=CHAT_BODY, headers=h())
    assert r.status_code == 200 and _events(r.text)[-1] == "done"
    assert '"disclaimer":"Ask disclaimer."' in r.text
    cache.get.assert_not_called()
    cache.set.assert_not_called()
    cache.stats_store.get_daily_cost.assert_called()
