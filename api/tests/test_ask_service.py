"""Tests for answer_question(), the core shared by /api/v1/ask and the MCP tool."""

from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from src.api import ask_service
from src.api.ask_service import InvalidSources, answer_question
from src.api.models import QuestionRequest
from src.generation.models import Citation, GeneratedAnswer


def _answer(cached=False):
    citation = Citation(
        chunk_id="c1",
        article_title="Breast Cancer",
        section="Symptoms",
        url="https://example.com/breast",
        paragraph_index=0,
        text_excerpt="Lumps.",
        similarity_score=0.8,
        source="BC Cancer",
        full_text="Lumps in the breast.",
    )
    a = GeneratedAnswer(
        query="What are symptoms of breast cancer?",
        answer="Lumps [Source: Breast Cancer - Symptoms]",
        citations=[citation],
        context_used=None,
        model="gpt-4o-mini",
        tokens_used={"input": 100, "output": 50, "total": 150},
        cost=0.0002,
        generation_time_ms=500.0,
        disclaimer="Educational only.",
    )
    a.cached = cached
    return a


@pytest.fixture
def generator():
    g = Mock()
    g.generate_answer.return_value = _answer()
    g.context_text.return_value = "CONTEXT"
    return g


class _FakeTrace:
    def __init__(self):
        self.updates = []
        self.trace_id = "trace-1"

    def update(self, output=None, metadata=None):
        self.updates.append({"output": output, "metadata": metadata})


@pytest.fixture
def traces(monkeypatch):
    calls = []

    @contextmanager
    def fake_request_trace(name, **kw):
        t = _FakeTrace()
        calls.append({"name": name, "trace": t, **kw})
        yield t

    monkeypatch.setattr(ask_service, "request_trace", fake_request_trace)
    return calls


def test_returns_the_same_response_shape_as_ask(generator, traces):
    req = QuestionRequest(question="What are symptoms of breast cancer?")
    out = answer_question(req, generator)
    assert out.response.answer == "Lumps [Source: Breast Cancer - Symptoms]"
    assert out.response.sources[0].article_title == "Breast Cancer"
    assert out.response.metadata["cost"] == 0.0002
    assert out.response.metadata["cached"] is False
    assert out.answer is generator.generate_answer.return_value
    assert out.trace_id == "trace-1"


def test_passes_settings_to_the_generator(generator, traces):
    req = QuestionRequest(
        question="Side effects?",
        source=["Cleveland Clinic", "BC Cancer"],
        max_results=3,
        min_similarity=0.5,
        include_full_text=True,
    )
    answer_question(req, generator)
    kw = generator.generate_answer.call_args.kwargs
    assert kw["filters"] == {"source": ["BC Cancer", "Cleveland Clinic"]}
    assert kw["max_results"] == 3
    assert kw["min_similarity"] == 0.5
    assert kw["include_full_text"] is True


def test_unknown_source_raises_before_any_generation(generator, traces):
    req = QuestionRequest(question="Side effects?", source=["Mayo"])
    with pytest.raises(InvalidSources):
        answer_question(req, generator)
    generator.generate_answer.assert_not_called()


def test_default_trace_is_the_ask_trace(generator, traces):
    answer_question(QuestionRequest(question="Side effects?"), generator)
    call = traces[0]
    assert call["name"] == "ask"
    assert call["input"] == {"question": "Side effects?"}
    assert call["metadata"]["endpoint"] == "/api/v1/ask"
    final = call["trace"].updates[-1]
    assert final["output"] == "Lumps [Source: Breast Cancer - Symptoms]"
    assert final["metadata"]["context"] == "CONTEXT"
    assert final["metadata"]["sources_count"] == 1
    assert final["metadata"]["cached"] is False


def test_caller_can_name_tag_and_annotate_the_trace(generator, traces):
    answer_question(
        QuestionRequest(question="Side effects?"),
        generator,
        trace_name="mcp_ask",
        endpoint="/api/mcp",
        extra_metadata={"channel": "mcp"},
        user_id="claude-desktop-kam",
        tags=["mcp"],
        annotate=lambda out: {"unmatched_markers": 0, "n": len(out.response.sources)},
    )
    call = traces[0]
    assert call["name"] == "mcp_ask"
    assert call["user_id"] == "claude-desktop-kam"
    assert call["tags"] == ["mcp"]
    assert call["metadata"]["endpoint"] == "/api/mcp"
    assert call["metadata"]["channel"] == "mcp"
    final = call["trace"].updates[-1]["metadata"]
    assert final["unmatched_markers"] == 0
    assert final["n"] == 1
    assert final["context"] == "CONTEXT"  # the evaluators' field is kept
