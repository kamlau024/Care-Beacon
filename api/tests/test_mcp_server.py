"""Contract tests for /api/mcp: the real app over HTTP, the generator mocked.

They cover the tool contract (plan §3) and every deterministic error case
from the plan's E5 table, so they run in CI with no secrets and no LLM spend.
"""

import hashlib
import json
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from src.api.filters import configured_sources
from src.api.main import app
from src.caching.stats_store import StatsStore
from src.chat.spend import cap_reached as chat_cap_reached
from src.generation.models import Citation, GeneratedAnswer
from src.mcp_server.schemas import CareBeaconAnswer
from tests.test_stats_store import FakeRedis

RAW_KEY = "test-key-123"
KEY_LINE = f"pytest:{hashlib.sha256(RAW_KEY.encode()).hexdigest()}"
VERSION = "2026-07-28"


class LimitRedis(FakeRedis):
    """FakeRedis plus the INCR the rate limiter uses."""

    def incr(self, name):
        self.data[name] = int(self.data.get(name, 0)) + 1
        return self.data[name]


class DownRedis(LimitRedis):
    def incr(self, name):
        raise RedisError("down")

    def get(self, name):
        raise RedisError("down")


def _answer(citations=True):
    cites = (
        [
            Citation(
                chunk_id="c1",
                article_title="Managing side effects",
                section="Fatigue",
                url="https://www.bccancer.bc.ca/fatigue",
                paragraph_index=0,
                text_excerpt="Fatigue is common.",
                similarity_score=0.81234,
                source="BC Cancer",
                full_text="Fatigue is common during treatment.",
            ),
            Citation(
                chunk_id="c2",
                article_title="Coping",
                section="[Physical changes](https://cancer.ca/coping#2181)",
                url="https://cancer.ca/coping",
                paragraph_index=3,
                text_excerpt="Your body may change.",
                similarity_score=0.7,
                source="Canadian Cancer Society",
            ),
        ]
        if citations
        else []
    )
    text = (
        "Tiredness is common [Source: Managing side effects - Fatigue]. "
        "Bodies change [Source: Coping - Physical changes]."
        if citations
        else "I couldn't find relevant information to answer your question."
    )
    return GeneratedAnswer(
        query="q",
        answer=text,
        citations=cites,
        context_used=None,
        model="gpt-4o-mini",
        tokens_used={"input": 100, "output": 50, "total": 150},
        cost=0.0004,
        generation_time_ms=900.0,
        disclaimer="This information is for educational purposes only.",
    )


@pytest.fixture
def redis_client():
    return LimitRedis()


@pytest.fixture
def generator(redis_client):
    g = Mock()
    store = StatsStore(redis_client)

    def generate(**kwargs):
        # Spend is recorded deep inside the real clients; do the same here.
        store.incr_daily_cost(0.0004)
        return _answer()

    g.generate_answer.side_effect = generate
    g.context_text.return_value = "CONTEXT"
    g.cache.stats_store = store
    return g


@pytest.fixture
def client(monkeypatch, generator):
    monkeypatch.setenv("MCP_API_KEYS", KEY_LINE)
    for var in ("MCP_DAILY_SPEND_CAP_USD", "MCP_RATE_LIMIT_PER_MIN", "VERCEL_ENV"):
        monkeypatch.delenv(var, raising=False)
    with patch("src.api.main.get_answer_generator", return_value=generator):
        with TestClient(app) as c:
            yield c


def rpc(client, method, params=None, *, name=None, headers=None, key=RAW_KEY):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {
            **(params or {}),
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1"},
            },
        },
    }
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": VERSION,
        "Mcp-Method": method,
    }
    if name is not None:
        h["Mcp-Name"] = name
    if key is not None:
        h["Authorization"] = f"Bearer {key}"
    h.update(headers or {})
    return client.post("/api/mcp", content=json.dumps(body), headers=h)


def call(client, arguments, **kw):
    r = rpc(client, "tools/call", {"name": "ask_care_beacon", "arguments": arguments},
            name="ask_care_beacon", **kw)
    assert r.status_code == 200, r.text
    return r.json()["result"]


def _tool(client):
    r = rpc(client, "tools/list")
    assert r.status_code == 200, r.text
    [tool] = r.json()["result"]["tools"]
    return tool, r.json()["result"]


# --- discovery -----------------------------------------------------------------


def test_lists_exactly_one_read_only_tool(client):
    tool, result = _tool(client)
    assert tool["name"] == "ask_care_beacon"
    assert tool["annotations"] == {
        "title": "Ask Care Beacon",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    assert result["ttlMs"] == 3_600_000
    assert result["cacheScope"] == "public"


def test_input_schema_matches_the_contract(client):
    schema = _tool(client)[0]["inputSchema"]
    props = schema["properties"]
    assert schema["required"] == ["question"]
    assert schema["additionalProperties"] is False
    assert set(props) == {"question", "sources", "min_similarity", "max_results", "include_source_text"}
    assert props["min_similarity"]["default"] == 0.5
    assert props["max_results"]["default"] == 5


def test_sources_enum_is_the_configured_sources(client):
    props = _tool(client)[0]["inputSchema"]["properties"]
    items = props["sources"]["anyOf"][0]["items"] if "anyOf" in props["sources"] else props["sources"]["items"]
    assert items["enum"] == configured_sources()


def test_output_schema_is_published(client):
    schema = _tool(client)[0]["outputSchema"]
    assert set(schema["required"]) >= {"answer", "answered", "citations", "disclaimer", "settings", "meta"}


def test_discover_advertises_only_tools(client):
    r = rpc(client, "server/discover")
    assert r.status_code == 200, r.text
    caps = r.json()["result"]["capabilities"]
    assert "tools" in caps
    assert "prompts" not in caps and "resources" not in caps


# --- a successful call -----------------------------------------------------------


def test_structured_output_validates_against_the_model(client):
    result = call(client, {"question": "Why am I so tired during chemo?"})
    assert result["isError"] is False
    answer = CareBeaconAnswer.model_validate(result["structuredContent"])
    assert answer.answered is True
    assert [c.n for c in answer.citations] == [1, 2]
    assert answer.citations[1].section == "Physical changes"
    assert answer.citations[1].section_url == "https://cancer.ca/coping#2181"
    assert answer.citations[0].text is None
    assert answer.meta.model == "gpt-4o-mini"
    assert answer.meta.cost_usd == 0.0004


def test_every_marker_becomes_a_citation_number(client):
    answer = call(client, {"question": "Why am I so tired during chemo?"})["structuredContent"]["answer"]
    assert answer == "Tiredness is common [1]. Bodies change [2]."


def test_content_is_markdown_then_the_json(client):
    result = call(client, {"question": "Why am I so tired during chemo?"})
    markdown, js = (block["text"] for block in result["content"])
    assert "**Sources**" in markdown
    assert "[2] Coping — Physical changes (Canadian Cancer Society)." in markdown
    assert json.loads(js) == result["structuredContent"]


def test_defaults_are_the_search_page_defaults(client, generator):
    settings = call(client, {"question": "Why am I so tired?"})["structuredContent"]["settings"]
    assert settings == {"sources": configured_sources(), "min_similarity": 0.5, "max_results": 5}
    kw = generator.generate_answer.call_args.kwargs
    assert kw["min_similarity"] == 0.5
    assert kw["filters"] is None
    assert kw["include_full_text"] is False


def test_settings_arrive_as_passed(client, generator):
    result = call(client, {
        "question": "Why am I so tired?",
        "sources": ["Cleveland Clinic", "BC Cancer"],
        "min_similarity": 0.7,
        "max_results": 3,
        "include_source_text": True,
    })
    kw = generator.generate_answer.call_args.kwargs
    assert kw["filters"] == {"source": ["BC Cancer", "Cleveland Clinic"]}
    assert (kw["min_similarity"], kw["max_results"], kw["include_full_text"]) == (0.7, 3, True)
    assert result["structuredContent"]["citations"][0]["text"] == "Fatigue is common during treatment."


def test_max_results_is_a_hard_cap_for_mcp(client, generator):
    # Search returns every passage above min_similarity; the tool promises at most max_results.
    call(client, {"question": "Why am I so tired?", "max_results": 3})
    assert generator.generate_answer.call_args.kwargs["cap_results"] is True


def test_no_sources_means_answered_false_not_an_error(client, generator):
    generator.generate_answer.side_effect = None
    generator.generate_answer.return_value = _answer(citations=False)
    result = call(client, {"question": "Something obscure?", "min_similarity": 0.95})
    assert result["isError"] is False
    assert result["structuredContent"]["answered"] is False
    assert result["structuredContent"]["citations"] == []


def test_spend_is_counted_on_the_mcp_channel(client, generator):
    call(client, {"question": "Why am I so tired?"})
    store = generator.cache.stats_store
    assert store.get_daily_cost(channel="mcp") == pytest.approx(0.0004)
    assert store.get_daily_cost() == pytest.approx(0.0004)


# --- HTTP-level refusals -----------------------------------------------------------


def test_missing_key_is_401(client):
    r = rpc(client, "tools/list", key=None)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_wrong_key_is_401(client):
    assert rpc(client, "tools/list", key="nope").status_code == 401


def test_no_keys_configured_is_503(client, monkeypatch):
    monkeypatch.delenv("MCP_API_KEYS")
    assert rpc(client, "tools/list").status_code == 503


def test_foreign_origin_is_403(client):
    assert rpc(client, "tools/list", headers={"Origin": "https://evil.example"}).status_code == 403


def test_our_origin_is_allowed(client):
    r = rpc(client, "tools/list", headers={"Origin": "https://care-beacon-health.vercel.app"})
    assert r.status_code == 200


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_non_post_is_405_without_a_version_header(client, method):
    # Without the guard, a bare GET opens a legacy SSE stream that never ends.
    r = client.request(method, "/api/mcp", headers={"Authorization": f"Bearer {RAW_KEY}"})
    assert r.status_code == 405
    assert r.headers["allow"] == "POST"


def test_a_deployed_host_header_is_accepted(client):
    # Phase 0: the SDK's default rejects any non-localhost Host with 421.
    r = rpc(client, "tools/list", headers={"Host": "care-beacon-health.vercel.app"})
    assert r.status_code == 200


def test_mcp_name_header_mismatch_is_rejected(client):
    r = rpc(client, "tools/call", {"name": "ask_care_beacon", "arguments": {"question": "Why?"}},
            name="something_else")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == -32020


# --- tool errors (isError results) -------------------------------------------------


def _error(result):
    assert result["isError"] is True
    return result["structuredContent"]["error"]


def test_unknown_source_is_invalid_arguments_with_no_spend(client, generator):
    err = _error(call(client, {"question": "Why am I so tired?", "sources": ["Mayo Clinic"]}))
    assert err["code"] == "invalid_arguments"
    assert err["field"].startswith("sources")
    assert "BC Cancer" in err["message"]
    generator.generate_answer.assert_not_called()


@pytest.mark.parametrize("arguments, field", [
    ({"question": "Why?", "min_similarity": 1.5}, "min_similarity"),
    ({"question": "Hi"}, "question"),
    ({"question": "Why am I tired?", "max_results": 0}, "max_results"),
    ({"question": "Why am I tired?", "cancer_type": "breast"}, "cancer_type"),
])
def test_bad_arguments_are_invalid_arguments(client, generator, arguments, field):
    err = _error(call(client, arguments))
    assert err["code"] == "invalid_arguments"
    assert err["field"] == field
    assert "pydantic" not in err["message"]
    generator.generate_answer.assert_not_called()


def test_rate_limit_is_a_tool_error_with_retry_after(client, monkeypatch, generator):
    monkeypatch.setenv("MCP_RATE_LIMIT_PER_MIN", "1")
    call(client, {"question": "Why am I so tired?"})
    err = _error(call(client, {"question": "Why am I so tired?"}))
    assert err["code"] == "rate_limited"
    assert 0 < err["retry_after_s"] <= 60
    assert generator.generate_answer.call_count == 1


def test_daily_cap_is_a_tool_error_and_chat_stays_open(client, monkeypatch, generator):
    monkeypatch.setenv("MCP_DAILY_SPEND_CAP_USD", "0")
    err = _error(call(client, {"question": "Why am I so tired?"}))
    assert err["code"] == "daily_limit_reached"
    assert err["resets_at"].endswith("T00:00:00Z")
    generator.generate_answer.assert_not_called()
    assert chat_cap_reached(generator.cache.stats_store) is False


def test_unreadable_counters_refuse_the_call(client, generator):
    generator.cache.stats_store = StatsStore(DownRedis())
    result = call(client, {"question": "Why am I so tired?"})
    assert result["isError"] is True
    generator.generate_answer.assert_not_called()


def test_upstream_failure_is_a_short_tool_error(client, generator):
    generator.generate_answer.side_effect = RuntimeError("qdrant: connection refused at 10.0.0.1")
    err = _error(call(client, {"question": "Why am I so tired?"}))
    assert err["code"] == "upstream_unavailable"
    assert "qdrant" not in err["message"].lower()


def test_unknown_tool_is_a_tool_error(client):
    r = rpc(client, "tools/call", {"name": "nope", "arguments": {}}, name="nope")
    assert r.status_code == 200
    assert r.json()["result"]["isError"] is True


# --- tracing -------------------------------------------------------------------------


def test_the_trace_is_mcp_ask_with_channel_and_caller(client, monkeypatch):
    from contextlib import contextmanager

    from src.api import ask_service

    seen = []

    class T:
        trace_id = "t-1"

        def update(self, output=None, metadata=None):
            seen.append(("update", metadata))

    @contextmanager
    def fake_trace(name, **kw):
        seen.append(("start", name, kw))
        yield T()

    monkeypatch.setattr(ask_service, "request_trace", fake_trace)
    result = call(client, {"question": "Why am I so tired?", "max_results": 4})
    _, name, kw = seen[0]
    assert name == "mcp_ask"
    assert kw["user_id"] == "pytest"
    assert kw["tags"] == ["mcp"]
    meta = kw["metadata"]
    assert meta["channel"] == "mcp"
    assert meta["mcp"]["key_name"] == "pytest"
    assert meta["mcp"]["client"] == "pytest/1"
    assert meta["mcp"]["protocol_version"] == VERSION
    assert meta["arguments"]["max_results"] == 4
    final = seen[-1][1]
    assert final["context"] == "CONTEXT"
    assert final["unmatched_markers"] == 0
    assert result["structuredContent"]["meta"]["trace_id"] == "t-1"
