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
