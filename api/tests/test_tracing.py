"""Tests for the optional Langfuse tracing layer (inert unless keys are set)."""

from contextlib import contextmanager

import pytest

from src.observability import tracing
from src.observability.tracing import (
    flush,
    get_openai_client,
    request_trace,
    span,
    tracing_enabled,
)

KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")


def _set_keys(monkeypatch):
    for k in KEYS:
        monkeypatch.setenv(k, "x")


def _clear_keys(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def test_disabled_without_keys(monkeypatch):
    _clear_keys(monkeypatch)
    assert tracing_enabled() is False
    with request_trace("ask", metadata={}) as t:
        t.update(output="x")
    with span("search") as s:
        s.update(output=[])
    flush()
    assert type(get_openai_client("sk-test")).__module__.startswith("openai")


@pytest.mark.parametrize("missing", KEYS)
def test_enabled_requires_all_three_vars(monkeypatch, missing):
    _set_keys(monkeypatch)
    monkeypatch.delenv(missing)
    assert tracing_enabled() is False


def test_enabled_with_all_three_vars(monkeypatch):
    _set_keys(monkeypatch)
    assert tracing_enabled() is True


def test_disabled_does_not_touch_sdk(monkeypatch):
    _clear_keys(monkeypatch)

    def boom():
        raise AssertionError("SDK client must not be created when disabled")

    monkeypatch.setattr(tracing, "_get_client", boom)
    with request_trace("ask", metadata={"a": 1}, session_id="s") as t:
        t.update(output="x")
    flush()


class _ExplodingClient:
    def start_as_current_observation(self, *a, **k):
        raise RuntimeError("sdk down")

    def flush(self):
        raise RuntimeError("sdk down")


def test_sdk_errors_are_swallowed(monkeypatch):
    _set_keys(monkeypatch)
    monkeypatch.setattr(tracing, "_get_client", lambda: _ExplodingClient())
    with request_trace("ask", metadata={}) as t:
        t.update(output="x")
    with span("embed", input="q") as s:
        s.update(output=1)
    flush()


def test_get_client_failure_is_swallowed(monkeypatch):
    _set_keys(monkeypatch)

    def boom():
        raise RuntimeError("cannot init")

    monkeypatch.setattr(tracing, "_get_client", boom)
    with request_trace("ask", metadata={}) as t:
        t.update(output="x")
    flush()
    assert type(get_openai_client("sk-test")).__module__.startswith("openai")


class _FakeObservation:
    def __init__(self, fail_update=False):
        self.updates = []
        self.fail_update = fail_update

    def update(self, **kw):
        if self.fail_update:
            raise RuntimeError("update failed")
        self.updates.append(kw)


class _FakeClient:
    def __init__(self, fail_update=False):
        self.started = []
        self.flushed = 0
        self.obs = []
        self.fail_update = fail_update

    @contextmanager
    def start_as_current_observation(self, **kw):
        self.started.append(kw)
        o = _FakeObservation(self.fail_update)
        self.obs.append(o)
        yield o

    def flush(self):
        self.flushed += 1


def test_enabled_records_spans_and_updates(monkeypatch):
    _set_keys(monkeypatch)
    fake = _FakeClient()
    monkeypatch.setattr(tracing, "_get_client", lambda: fake)
    with request_trace("ask", metadata={"endpoint": "/x"}, session_id="s1") as t:
        t.update(output="answer", metadata={"cached": False})
        with span("embed", input="q") as s:
            s.update(output=3)
    flush()
    assert [k["name"] for k in fake.started] == ["ask", "embed"]
    assert fake.started[0]["metadata"] == {"endpoint": "/x"}
    assert fake.started[1]["input"] == "q"
    assert fake.obs[0].updates == [{"output": "answer", "metadata": {"cached": False}}]
    assert fake.obs[1].updates == [{"output": 3}]
    assert fake.flushed == 1


def test_handle_update_errors_are_swallowed(monkeypatch):
    _set_keys(monkeypatch)
    monkeypatch.setattr(tracing, "_get_client", lambda: _FakeClient(fail_update=True))
    with request_trace("ask", metadata={}) as t:
        t.update(output="x")


def test_body_exceptions_still_propagate(monkeypatch):
    _set_keys(monkeypatch)
    monkeypatch.setattr(tracing, "_get_client", lambda: _FakeClient())
    with pytest.raises(ValueError):
        with request_trace("ask", metadata={}):
            raise ValueError("real error")
    monkeypatch.setattr(tracing, "_get_client", lambda: _ExplodingClient())
    with pytest.raises(ValueError):
        with span("embed"):
            raise ValueError("real error")


def test_root_trace_records_input(monkeypatch):
    _set_keys(monkeypatch)
    fake = _FakeClient()
    monkeypatch.setattr(tracing, "_get_client", lambda: fake)
    with request_trace("chat", metadata={}, input={"question": "q?"}):
        pass
    assert fake.started[0]["input"] == {"question": "q?"}


def test_generation_kwargs_only_when_instrumented(monkeypatch):
    monkeypatch.setattr(tracing, "_openai_instrumented", False)
    assert tracing.generation_kwargs("answer") == {}
    monkeypatch.setattr(tracing, "_openai_instrumented", True)
    assert tracing.generation_kwargs("answer") == {"name": "answer"}
    assert tracing.generation_kwargs(None) == {}


def test_disabled_client_is_not_marked_instrumented(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setattr(tracing, "_openai_instrumented", False)
    get_openai_client("sk-test")
    assert tracing.generation_kwargs("answer") == {}


@pytest.mark.parametrize(
    "explicit, vercel, expected",
    [
        (None, "production", "production"),
        (None, "preview", "preview"),
        ("staging", "production", "staging"),
        (None, None, None),
    ],
)
def test_tracing_environment(monkeypatch, explicit, vercel, expected):
    for name, value in (("LANGFUSE_TRACING_ENVIRONMENT", explicit), ("VERCEL_ENV", vercel)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    assert tracing.tracing_environment() == expected
    tracing._apply_environment()
    import os

    assert os.getenv("LANGFUSE_TRACING_ENVIRONMENT") == expected


def test_root_trace_passes_tags_and_user(monkeypatch):
    _set_keys(monkeypatch)
    monkeypatch.setattr(tracing, "_get_client", lambda: _FakeClient())
    seen = {}

    @contextmanager
    def fake_propagate(**kw):
        seen.update(kw)
        yield

    import langfuse

    monkeypatch.setattr(langfuse, "propagate_attributes", fake_propagate)
    with request_trace("mcp_ask", metadata={}, user_id="kam", tags=["mcp"]):
        pass
    assert seen["trace_name"] == "mcp_ask"
    assert seen["user_id"] == "kam"
    assert seen["tags"] == ["mcp"]


def test_handle_exposes_trace_id(monkeypatch):
    _set_keys(monkeypatch)
    fake = _FakeClient()
    monkeypatch.setattr(tracing, "_get_client", lambda: fake)
    with request_trace("ask", metadata={}) as t:
        fake.obs[0].trace_id = "abc123"
        assert t.trace_id == "abc123"


def test_disabled_handle_has_no_trace_id(monkeypatch):
    _clear_keys(monkeypatch)
    with request_trace("ask", metadata={}) as t:
        assert t.trace_id is None
