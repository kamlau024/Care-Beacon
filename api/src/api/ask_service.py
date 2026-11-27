"""The question-answering core shared by POST /api/v1/ask and the MCP tool.

Both callers go through answer_question(), so they get the same filter
normalisation, cache, cost accounting and Langfuse root-trace shape (the live
evaluators read `input.question`, `output` and `metadata.context`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.api.filters import configured_sources, normalize_sources
from src.api.models import CitationResponse, QuestionRequest, QuestionResponse
from src.generation.models import GeneratedAnswer
from src.observability.tracing import request_trace


class InvalidSources(ValueError):
    """The request named a source that is not configured."""


@dataclass
class AskOutcome:
    """What answer_question() produced."""

    response: QuestionResponse
    answer: GeneratedAnswer
    trace_id: Optional[str]


def _filters(req: QuestionRequest) -> Optional[Dict[str, Any]]:
    filters: Dict[str, Any] = {}
    if req.cancer_type:
        filters["cancer_type"] = req.cancer_type
    try:
        source_filter = normalize_sources(req.source, configured_sources())
    except ValueError as e:
        raise InvalidSources(str(e)) from e
    if source_filter is not None:
        filters["source"] = source_filter
    return filters or None


def _response(answer: GeneratedAnswer) -> QuestionResponse:
    return QuestionResponse(
        question=answer.query,
        answer=answer.answer,
        sources=[
            CitationResponse(
                article_title=c.article_title,
                section=c.section,
                url=c.url,
                paragraph_index=c.paragraph_index,
                text_excerpt=c.text_excerpt,
                similarity_score=c.similarity_score,
                source=c.source,
                full_text=c.full_text,
            )
            for c in answer.citations
        ],
        disclaimer=answer.disclaimer,
        model=answer.model,
        metadata={
            "tokens_used": answer.tokens_used.get("total", 0),
            "cost": answer.cost,
            "generation_time_ms": answer.generation_time_ms,
            # Whether THIS answer came from the cache (not a cumulative hit counter)
            "cached": answer.cached,
            "sources_count": len(answer.citations),
        },
    )


def answer_question(
    req: QuestionRequest,
    generator: Any,
    *,
    trace_name: str = "ask",
    endpoint: str = "/api/v1/ask",
    extra_metadata: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    annotate: Optional[Callable[[AskOutcome], Dict[str, Any]]] = None,
    cap_results: bool = False,
) -> AskOutcome:
    """Answer one question with RAG inside a root Langfuse trace.

    Args:
        req: The validated request.
        generator: The AnswerGenerator to use.
        trace_name: Root trace name (`ask` for Search, `mcp_ask` for MCP).
        endpoint: Recorded in the trace metadata.
        extra_metadata: Merged into the trace's opening metadata.
        user_id: Langfuse user id (never a secret).
        tags: Langfuse trace tags.
        annotate: Called with the outcome before the trace closes; the dict it
            returns is added to the trace's final metadata.
        cap_results: Answer from at most req.max_results passages (MCP). Off
            for Search, which shows every passage above min_similarity.

    Raises:
        InvalidSources: before any retrieval, if a source is unknown.
    """
    metadata: Dict[str, Any] = {
        "endpoint": endpoint,
        "filters": {"cancer_type": req.cancer_type, "source": req.source},
        "min_similarity": req.min_similarity,
        **(extra_metadata or {}),
    }
    with request_trace(
        trace_name,
        input={"question": req.question},
        metadata=metadata,
        user_id=user_id,
        tags=tags,
    ) as trace:
        filters = _filters(req)
        answer = generator.generate_answer(
            question=req.question,
            filters=filters,
            # Re-ranking fetches more (2x) internally for better quality.
            max_results=req.max_results,
            min_similarity=req.min_similarity,
            include_full_text=req.include_full_text,
            cap_results=cap_results,
        )
        outcome = AskOutcome(response=_response(answer), answer=answer, trace_id=trace.trace_id)
        final: Dict[str, Any] = {
            "cached": answer.cached,
            "sources_count": len(answer.citations),
            # Empty for a cached answer; live evaluators skip those.
            "context": generator.context_text(answer),
        }
        if annotate is not None:
            final.update(annotate(outcome))
        trace.update(output=answer.answer, metadata=final)
        return outcome
