"""Tests for the streaming chat turn (ChatService + SSE framing)."""

import contextvars
import hashlib
from contextlib import contextmanager
import json
import uuid
from unittest.mock import MagicMock

import pytest

from src.api.chat_models import ChatRequest
from src.chat.models import ThreadSettings
from src.chat.prompt import fallback_title, load_chat_prompts
from src.chat.repository import ThreadNotFound
from src.chat.service import ERROR_MESSAGE, ChatService, run_in_pinned_context
from src.chat.sse import frame
from src.retrieval.models import Query
from src.storage.models import Chunk, RetrievalResult
from tests.fakes import InMemoryThreadRepository

OWNER = str(uuid.uuid4())
OTHER = str(uuid.uuid4())
DISCLAIMER = "Educational only. Talk to your care team."


# ---------------------------------------------------------------- fakes


def result(i=1, text="Radiation can cause fatigue.", source="BC Cancer", score=0.8):
    chunk = Chunk(
        chunk_id=f"c{i}",
        text=text,
        article_id=f"a{i}",
        article_title=f"Article {i}",
        url=f"https://example.com/{i}",
        breadcrumbs=[],
        section=f"Section {i}",
        source=source,
    )
    return RetrievalResult(chunk=chunk, similarity_score=score)


class FakeRetrieval:
    def __init__(self, results=None, raises=None):
        self.results = [result()] if results is None else results
        self.raises = raises
        self.queries = []
        self.ranked = 0

    def make_query(self, query_text, max_results=None, min_similarity=None, filters=None):
        q = Query(text=query_text, filters=filters, max_results=max_results or 10,
                  min_similarity=min_similarity or 0.0)
        return q

    def search_candidates(self, query):
        self.queries.append(query)
        if self.raises:
            raise self.raises
        return list(self.results)

    def rank_candidates(self, query, candidates):
        self.ranked += 1
        return candidates


class FakeStream:
    def __init__(self, deltas, raise_after=None, on_delta=None):
        self.deltas = deltas
        self.raise_after = raise_after
        self.on_delta = on_delta
        self.usage = None
        self.closed = False

    def __iter__(self):
        try:
            for i, d in enumerate(self.deltas):
                if self.raise_after is not None and i == self.raise_after:
                    raise RuntimeError("openai secret failure text sk-123")
                yield d
            self.usage = {"tokens_used": {"input": 10, "output": 5, "total": 15},
                          "cost": 0.0012, "model": "m", "estimated": False}
        finally:
            if self.usage is None:
                self.closed = True
                self.usage = {"tokens_used": {"input": 10, "output": 2, "total": 12},
                              "cost": 0.0005, "model": "m", "estimated": True}


class FakeLLM:
    def __init__(self, deltas=("Fatigue ", "is ", "common [1]."), raise_after=None,
                 rewrite="rewritten standalone query", title="Radiation side effects",
                 title_raises=False):
        self.deltas = list(deltas)
        self.raise_after = raise_after
        self.rewrite = rewrite
        self.title = title
        self.title_raises = title_raises
        self.stream_calls = []
        self.utility_calls = []
        self.streams = []

    def generate_stream(self, messages, max_tokens=None, temperature=None, model=None):
        self.stream_calls.append(messages)
        s = FakeStream(self.deltas, self.raise_after)
        self.streams.append(s)
        return s

    def generate_messages(self, messages, max_tokens=None, temperature=None, model=None):
        prompt = messages[0]["content"]
        self.utility_calls.append(prompt)
        if "Standalone query" in prompt:
            return {"answer": self.rewrite}
        if self.title_raises:
            raise RuntimeError("title boom")
        return {"answer": self.title}


@pytest.fixture
def prompts():
    return load_chat_prompts()


@pytest.fixture
def repo():
    return InMemoryThreadRepository()


def make_service(repo, prompts, retrieval=None, llm=None, max_context_chunks=5):
    return ChatService(
        repository=repo,
        retrieval_engine=retrieval or FakeRetrieval(),
        llm_client=llm or FakeLLM(),
        prompts=prompts,
        stats_store=MagicMock(),
        max_context_chunks=max_context_chunks,
        disclaimer=DISCLAIMER,
    )


def parse(raw):
    lines = raw.strip("\n").split("\n")
    assert lines[0].startswith("event: ") and lines[1].startswith("data: ")
    return lines[0][len("event: "):], json.loads(lines[1][len("data: "):])


def run_turn(service, message="What are the side effects of radiation?", thread_id=None,
             include_full_text=False):
    req = ChatRequest(thread_id=thread_id, message=message, include_full_text=include_full_text)
    thread, prior, is_new = service.start_turn(OWNER, req)
    gen = service.stream_turn(thread, prior, is_new, req.message, req.include_full_text)
    return thread, gen


def events(frames):
    return [parse(f)[0] for f in frames]


def assistants(repo, thread_id):
    return [m for m in repo.list_messages(thread_id) if m.role == "assistant"]


# ---------------------------------------------------------------- sse


def test_frame_format_is_compact_json():
    assert frame("token", {"text": "hi there"}) == 'event: token\ndata: {"text":"hi there"}\n\n'


# ---------------------------------------------------------------- start_turn


def test_start_turn_new_thread_uses_default_settings_and_writes_user_message(repo, prompts):
    service = make_service(repo, prompts)
    thread, prior, is_new = service.start_turn(OWNER, ChatRequest(message="Hello there"))
    assert is_new and prior == []
    assert thread.settings == ThreadSettings(
        sources=["BC Cancer", "Canadian Cancer Society", "Cleveland Clinic"], min_similarity=0.5
    )
    msgs = repo.list_messages(thread.id)
    assert [(m.role, m.content) for m in msgs] == [("user", "Hello there")]


def test_start_turn_existing_thread_ignores_request_settings(repo, prompts):
    stored = ThreadSettings(sources=["BC Cancer"], min_similarity=0.7)
    t = repo.create_thread(OWNER, stored)
    repo.append_message(t.id, "user", "first")
    service = make_service(repo, prompts)
    req = ChatRequest(thread_id=t.id, message="second one",
                      settings=ThreadSettings(sources=["Cleveland Clinic"], min_similarity=0.1))
    thread, prior, is_new = service.start_turn(OWNER, req)
    assert not is_new and thread.settings == stored
    assert [m.content for m in prior] == ["first"]
    assert [m.content for m in repo.list_messages(t.id)] == ["first", "second one"]


def test_start_turn_other_owner_raises_not_found(repo, prompts):
    t = repo.create_thread(OTHER, ThreadSettings(sources=["BC Cancer"], min_similarity=0.5))
    with pytest.raises(ThreadNotFound):
        make_service(repo, prompts).start_turn(OWNER, ChatRequest(thread_id=t.id, message="hey you"))
    assert repo.list_messages(t.id) == []


@pytest.mark.parametrize("message", ["hi", "x" * 501])
def test_chat_request_message_length(message):
    with pytest.raises(ValueError):
        ChatRequest(message=message)


# ---------------------------------------------------------------- stream_turn


def test_first_turn_frame_order(repo, prompts):
    retrieval = FakeRetrieval()
    service = make_service(repo, prompts, retrieval=retrieval)
    thread, gen = run_turn(service)
    frames = [parse(f) for f in gen]
    names = [e for e, _ in frames]
    assert names == ["status", "status", "citations", "token", "token", "token", "done"]
    assert frames[0][1] == {"stage": "searching", "query": "What are the side effects of radiation?"}
    assert frames[1][1] == {"stage": "ranking"}
    cits = frames[2][1]["citations"]
    assert cits == [{
        "n": 1, "article_title": "Article 1", "section": "Section 1",
        "url": "https://example.com/1", "source": "BC Cancer", "similarity_score": 0.8,
        "excerpt": "Radiation can cause fatigue.",
    }]
    assert "".join(d["text"] for e, d in frames if e == "token") == "Fatigue is common [1]."
    msg = assistants(repo, thread.id)[0]
    assert frames[-1][1] == {"thread_id": thread.id, "message_id": msg.id, "disclaimer": DISCLAIMER}
    # Default settings: all sources -> no source filter; thread min_similarity applies.
    assert retrieval.queries[0].filters is None
    assert retrieval.queries[0].min_similarity == 0.5


def test_follow_up_emits_rewriting_and_searches_rewritten_query(repo, prompts):
    retrieval, llm = FakeRetrieval(), FakeLLM()
    service = make_service(repo, prompts, retrieval=retrieval, llm=llm)
    thread, gen = run_turn(service)
    list(gen)
    _, gen2 = run_turn(service, message="What about the second one?", thread_id=thread.id)
    frames = [parse(f) for f in gen2]
    assert frames[0] == ("status", {"stage": "rewriting"})
    assert frames[1] == ("status", {"stage": "searching", "query": "rewritten standalone query"})
    assert retrieval.queries[-1].text == "rewritten standalone query"
    # The model still sees the original question verbatim.
    assert "What about the second one?" in llm.stream_calls[-1][-1]["content"]


def test_source_filter_from_thread_settings(repo, prompts):
    retrieval = FakeRetrieval()
    service = make_service(repo, prompts, retrieval=retrieval)
    req = ChatRequest(message="Question here",
                      settings=ThreadSettings(sources=["Cleveland Clinic"], min_similarity=0.65))
    thread, prior, is_new = service.start_turn(OWNER, req)
    list(service.stream_turn(thread, prior, is_new, req.message, False))
    assert retrieval.queries[0].filters == {"source": "Cleveland Clinic"}
    assert retrieval.queries[0].min_similarity == 0.65


def test_citations_capped_excerpt_and_full_text(repo, prompts):
    long_text = "y" * 900
    retrieval = FakeRetrieval(results=[result(i, text=long_text) for i in range(1, 8)])
    service = make_service(repo, prompts, retrieval=retrieval, max_context_chunks=3)
    thread, gen = run_turn(service, include_full_text=True)
    frames = [parse(f) for f in gen]
    cits = next(d for e, d in frames if e == "citations")["citations"]
    assert [c["n"] for c in cits] == [1, 2, 3]
    assert all(len(c["excerpt"]) == 500 and c["full_text"] == long_text for c in cits)
    stored = assistants(repo, thread.id)[0].citations
    assert [c["n"] for c in stored] == [1, 2, 3]
    assert all("full_text" not in c for c in stored)


def test_assistant_message_persisted_before_done(repo, prompts):
    service = make_service(repo, prompts)
    thread, gen = run_turn(service)
    for raw in gen:
        event, data = parse(raw)
        if event == "done":
            msgs = assistants(repo, thread.id)
            assert len(msgs) == 1
            assert msgs[0].id == data["message_id"]
            assert msgs[0].status == "complete"
            assert msgs[0].content == "Fatigue is common [1]."
            assert msgs[0].tokens == 15 and msgs[0].cost == pytest.approx(0.0012)
            assert msgs[0].citations and msgs[0].citations[0]["n"] == 1
            break
    else:
        pytest.fail("no done frame")


def test_no_results_streams_no_context_text_without_generation(repo, prompts):
    llm = FakeLLM()
    service = make_service(repo, prompts, retrieval=FakeRetrieval(results=[]), llm=llm)
    thread, gen = run_turn(service)
    frames = [parse(f) for f in gen]
    assert [e for e, _ in frames] == ["status", "status", "citations", "token", "done"]
    assert frames[2][1] == {"citations": []}
    assert frames[3][1] == {"text": prompts["no_context_found"]}
    assert llm.stream_calls == []
    [msg] = assistants(repo, thread.id)
    assert msg.content == prompts["no_context_found"] and msg.status == "complete"


def test_disconnect_persists_partial_as_interrupted(repo, prompts):
    llm = FakeLLM()
    service = make_service(repo, prompts, llm=llm)
    thread, gen = run_turn(service)
    tokens = 0
    for raw in gen:
        if parse(raw)[0] == "token":
            tokens += 1
            if tokens == 2:
                break
    gen.close()
    [msg] = assistants(repo, thread.id)
    assert msg.status == "interrupted"
    assert msg.content == "Fatigue is "
    assert msg.citations and msg.citations[0]["n"] == 1
    # The LLM stream was closed, so its (estimated) cost was recorded and saved.
    assert llm.streams[0].closed
    assert msg.cost == pytest.approx(0.0005) and msg.tokens == 12
    # An interrupted first turn gets the fallback title (no LLM titling call).
    assert repo.get_thread(thread.id, OWNER).title == fallback_title(
        "What are the side effects of radiation?"
    )
    assert not any("Title:" in p for p in llm.utility_calls)

    # The thread reopens normally and the next turn works, with the
    # interrupted answer in the history given to the prompt builder.
    history = repo.list_messages(thread.id)
    assert [(m.role, m.status) for m in history] == [
        ("user", "complete"), ("assistant", "interrupted")
    ]
    _, gen2 = run_turn(service, message="And how long does it last?", thread_id=thread.id)
    frames = [parse(f) for f in gen2]
    assert frames[0] == ("status", {"stage": "rewriting"})
    assert frames[-1][0] == "done"
    prompt = llm.stream_calls[-1][-1]["content"]
    assert "Assistant: Fatigue is" in prompt
    assert [(m.role, m.status) for m in repo.list_messages(thread.id)] == [
        ("user", "complete"), ("assistant", "interrupted"),
        ("user", "complete"), ("assistant", "complete"),
    ]


def test_disconnect_before_any_token_saves_nothing(repo, prompts):
    service = make_service(repo, prompts)
    thread, gen = run_turn(service)
    for raw in gen:
        if parse(raw)[0] == "citations":
            break
    gen.close()
    assert assistants(repo, thread.id) == []


def test_disconnect_at_done_writes_exactly_once(repo, prompts):
    service = make_service(repo, prompts)
    thread, gen = run_turn(service)
    for raw in gen:
        if parse(raw)[0] == "done":
            break
    gen.close()
    [msg] = assistants(repo, thread.id)
    assert msg.status == "complete"


def test_llm_error_mid_stream_emits_error_and_saves_partial(repo, prompts):
    service = make_service(repo, prompts, llm=FakeLLM(raise_after=2))
    thread, gen = run_turn(service)
    raw = list(gen)
    frames = [parse(f) for f in raw]
    assert [e for e, _ in frames] == ["status", "status", "citations", "token", "token", "error"]
    assert frames[-1][1] == {"message": ERROR_MESSAGE}
    assert "sk-123" not in "".join(raw)
    [msg] = assistants(repo, thread.id)
    assert msg.status == "interrupted" and msg.content == "Fatigue is "


def test_error_before_tokens_emits_error_and_saves_nothing(repo, prompts):
    retrieval = FakeRetrieval(raises=RuntimeError("qdrant down secret"))
    service = make_service(repo, prompts, retrieval=retrieval)
    thread, gen = run_turn(service)
    frames = [parse(f) for f in gen]
    assert [e for e, _ in frames] == ["status", "error"]
    assert assistants(repo, thread.id) == []


def test_title_set_for_new_thread_only(repo, prompts):
    llm = FakeLLM(title="Radiation side effects")
    service = make_service(repo, prompts, llm=llm)
    thread, gen = run_turn(service)
    list(gen)
    assert repo.get_thread(thread.id, OWNER).title == "Radiation side effects"
    repo.rename_thread(thread.id, OWNER, "Mine")
    _, gen2 = run_turn(service, message="And after that?", thread_id=thread.id)
    list(gen2)
    assert repo.get_thread(thread.id, OWNER).title == "Mine"


def test_title_failure_does_not_affect_stream(repo, prompts):
    service = make_service(repo, prompts)
    repo.set_title_if_empty = MagicMock(side_effect=RuntimeError("db gone"))
    thread, gen = run_turn(service)
    frames = [parse(f) for f in gen]
    assert frames[-1][0] == "done"
    assert len(assistants(repo, thread.id)) == 1


def test_assistant_write_failure_emits_error_once(repo, prompts):
    service = make_service(repo, prompts)
    thread, gen = run_turn(service)
    original = repo.append_message
    calls = []

    def failing(*a, **kw):
        calls.append(kw.get("status"))
        raise RuntimeError("psycopg secret")

    repo.append_message = failing
    raw = list(gen)
    repo.append_message = original
    assert [parse(f)[0] for f in raw][-1] == "error"
    assert "done" not in [parse(f)[0] for f in raw]
    assert "psycopg" not in "".join(raw)
    # A failed final write is not retried as an interrupted row: at most one write.
    assert calls == ["complete"]


# ---------------------------------------------------------------- tracing


def test_trace_gets_owner_pseudonym_never_raw_key(repo, prompts, monkeypatch):
    import src.chat.service as service_module

    recorded = []

    class Handle:
        def update(self, output=None, metadata=None):
            recorded.append(("update", output, metadata))

    @contextmanager
    def fake_trace(name, *, metadata, session_id=None, user_id=None):
        recorded.append(("start", name, metadata, session_id, user_id))
        yield Handle()

    monkeypatch.setattr(service_module, "request_trace", fake_trace)
    service = make_service(repo, prompts)
    thread, gen = run_turn(service)
    raw = "".join(gen)

    start = recorded[0]
    assert start[1] == "chat"
    assert start[3] == thread.id
    assert start[4] == hashlib.sha256(OWNER.encode()).hexdigest()[:32]
    assert any(r[0] == "update" for r in recorded)
    assert OWNER not in repr(recorded)
    assert OWNER not in raw


# ---------------------------------------------------------------- context pinning


def test_run_in_pinned_context_keeps_contextvars_across_threadpool_hops():
    var = contextvars.ContextVar("v", default="unset")
    seen = []
    closed = []

    def inner():
        var.set("set-in-step-1")
        yield 1
        seen.append(var.get())
        try:
            yield 2
        except GeneratorExit:
            closed.append(var.get())
            raise

    gen = run_in_pinned_context(inner())
    # Each step runs in a fresh context copy, as Starlette's threadpool does.
    assert contextvars.copy_context().run(next, gen) == 1
    assert contextvars.copy_context().run(next, gen) == 2
    contextvars.copy_context().run(gen.close)
    assert seen == ["set-in-step-1"]
    assert closed == ["set-in-step-1"]
    assert var.get() == "unset"


def test_chat_uses_same_max_results_default_as_ask(repo, prompts):
    from src.api.models import QuestionRequest

    default = QuestionRequest.model_fields["max_results"].default
    retrieval = FakeRetrieval()
    service = make_service(repo, prompts, retrieval=retrieval, max_context_chunks=30)
    _, gen = run_turn(service)
    list(gen)
    assert retrieval.queries[0].max_results == default


def test_error_on_new_thread_sets_fallback_title(repo, prompts):
    llm = FakeLLM()
    retrieval = FakeRetrieval(raises=RuntimeError("qdrant down secret"))
    service = make_service(repo, prompts, retrieval=retrieval, llm=llm)
    q = "Does chemotherapy always cause hair loss for everyone?"
    thread, gen = run_turn(service, message=q)
    frames = [parse(f) for f in gen]
    assert frames[-1][0] == "error"
    assert repo.get_thread(thread.id, OWNER).title == fallback_title(q)
    assert llm.utility_calls == []


def test_error_on_existing_thread_leaves_title_alone(repo, prompts):
    service = make_service(repo, prompts)
    thread, gen = run_turn(service)
    list(gen)
    repo.rename_thread(thread.id, OWNER, "Mine")
    bad = make_service(repo, prompts, retrieval=FakeRetrieval(raises=RuntimeError("x")))
    _, gen2 = run_turn(bad, message="And after that?", thread_id=thread.id)
    list(gen2)
    assert repo.get_thread(thread.id, OWNER).title == "Mine"


def test_fallback_title_failure_does_not_break_error_frame(repo, prompts):
    retrieval = FakeRetrieval(raises=RuntimeError("x"))
    service = make_service(repo, prompts, retrieval=retrieval)
    repo.set_title_if_empty = MagicMock(side_effect=RuntimeError("db gone"))
    _, gen = run_turn(service)
    frames = [parse(f) for f in gen]
    assert frames[-1] == ("error", {"message": ERROR_MESSAGE})
