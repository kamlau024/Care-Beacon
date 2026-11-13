"""One conversational chat turn: persistence, retrieval, streaming generation.

``start_turn`` runs before the response opens and writes the user message.
``stream_turn`` is a **sync** generator (the shape the serverless spike tested)
that yields SSE frames and writes the assistant message exactly once:

- complete, before the ``done`` frame;
- or, if the stream is closed (``GeneratorExit``) or fails after tokens have
  started, the partial text with ``status='interrupted'`` (empty partials are
  not saved).

On Vercel a client disconnect does not interrupt the generator, so the turn
runs to completion and the complete write lands. The interrupted path is for
runtimes that do close the generator (uvicorn locally).

The chat path never touches the answer cache.
"""

import contextvars
import hashlib
from typing import Any, Dict, Iterator, List, Optional, Tuple

from loguru import logger

from src.api.chat_models import ChatRequest
from src.api.filters import configured_sources, normalize_sources
from src.chat.models import Message, Thread, ThreadSettings
from src.api.models import QuestionRequest
from src.chat.prompt import build_chat_messages, fallback_title, generate_title, rewrite_query
from src.chat.repository import ThreadNotFound
from src.chat.sse import frame
from src.observability.tracing import flush, request_trace
from src.storage.models import RetrievalResult

DEFAULT_MIN_SIMILARITY = 0.5
EXCERPT_MAX_CHARS = 500
ERROR_MESSAGE = "Something went wrong while answering. Please try again."
ENDPOINT = "/api/v1/chat"
# Same retrieval breadth as /api/v1/ask from the Search page, so Chat and
# Search stay comparable (spec, open decision 2).
ASK_MAX_RESULTS = QuestionRequest.model_fields["max_results"].default


def default_settings() -> ThreadSettings:
    """All configured sources, min_similarity 0.5."""
    return ThreadSettings(sources=configured_sources(), min_similarity=DEFAULT_MIN_SIMILARITY)


def owner_pseudonym(owner_key: str) -> str:
    """Non-reversible trace user id for an owner key.

    The owner key is the bearer credential for a user's chat history, so it is
    never sent to the tracing provider. A UUIDv4 carries 122 bits of entropy,
    so an unsalted hash cannot be brute-forced back to the key.
    """
    return hashlib.sha256(owner_key.encode()).hexdigest()[:32]


def run_in_pinned_context(inner: Iterator[str]) -> Iterator[str]:
    """Drive ``inner`` so every step runs in one ``contextvars.Context``.

    Starlette iterates a sync generator in a threadpool, and each ``next()``
    runs in a fresh copy of the caller's context, so a context variable set
    in one step (e.g. the current trace) would be gone in the next. Pinning
    one context keeps the trace and its child spans connected across steps.
    """
    ctx = contextvars.copy_context()
    while True:
        try:
            item = ctx.run(next, inner)
        except StopIteration:
            return
        try:
            yield item
        except GeneratorExit:
            ctx.run(inner.close)
            raise


class ChatService:
    def __init__(
        self,
        repository,
        retrieval_engine,
        llm_client,
        prompts: Dict[str, str],
        stats_store,
        max_context_chunks: int,
        disclaimer: Optional[str] = None,
    ):
        self.repository = repository
        self.retrieval_engine = retrieval_engine
        self.llm_client = llm_client
        self.prompts = prompts
        self.stats_store = stats_store
        self.max_context_chunks = max_context_chunks
        self.disclaimer = disclaimer if disclaimer is not None else prompts["medical_disclaimer"]

    # ------------------------------------------------------------ before the stream

    def start_turn(
        self, owner_key: str, request: ChatRequest
    ) -> Tuple[Thread, List[Message], bool]:
        """Resolve or create the thread and write the user message.

        Returns ``(thread, prior_messages, is_new)``. Raises ``ThreadNotFound``
        for a missing thread or one owned by someone else.
        """
        if request.thread_id:
            thread = self.repository.get_thread(request.thread_id, owner_key)
            if thread is None:
                raise ThreadNotFound(request.thread_id)
            prior = self.repository.list_messages(thread.id)
            is_new = False
        else:
            thread = self.repository.create_thread(
                owner_key, request.settings or default_settings()
            )
            prior = []
            is_new = True
        self.repository.append_message(thread.id, "user", request.message)
        return thread, prior, is_new

    # ------------------------------------------------------------ the stream

    def stream_turn(
        self,
        thread: Thread,
        prior_messages: List[Message],
        is_new: bool,
        question: str,
        include_full_text: bool,
    ) -> Iterator[str]:
        return run_in_pinned_context(
            self._turn(thread, prior_messages, is_new, question, include_full_text)
        )

    def _turn(self, thread, prior_messages, is_new, question, include_full_text):
        try:
            with request_trace(
                "chat",
                metadata={
                    "endpoint": ENDPOINT,
                    "thread_id": thread.id,
                    "settings": thread.settings.model_dump(),
                },
                session_id=thread.id,
                user_id=owner_pseudonym(thread.owner_key),
            ) as trace:
                yield from self._turn_body(
                    trace, thread, prior_messages, is_new, question, include_full_text
                )
        finally:
            try:
                flush()
            except Exception as e:
                logger.warning(f"Chat trace flush failed: {type(e).__name__}")

    def _turn_body(self, trace, thread, prior_messages, is_new, question, include_full_text):
        parts: List[str] = []
        citations: List[dict] = []
        stream = None
        stream_iter = None
        # Set before the final write is attempted, so no path writes twice
        # (a failed final write is never followed by an interrupted one).
        write_attempted = False

        def save_partial() -> None:
            if write_attempted or not "".join(parts):
                return
            try:
                if stream_iter is not None:
                    stream_iter.close()  # records the (estimated) cost on the stream
                self._save_assistant(
                    thread.id, "".join(parts), citations,
                    stream.usage if stream is not None else None, "interrupted",
                )
            except Exception as e:
                logger.error(f"Saving interrupted chat answer failed: {type(e).__name__}")

        def fallback_title_if_new() -> None:
            # A first turn that never reaches `done` still gets a title, so the
            # thread isn't left untitled in History. No LLM call; best effort.
            if not is_new:
                return
            try:
                self.repository.set_title_if_empty(thread.id, fallback_title(question))
            except Exception as e:
                logger.warning(f"Chat fallback titling failed: {type(e).__name__}")

        try:
            query_text = question
            if any(m.role != "settings" for m in prior_messages):
                yield frame("status", {"stage": "rewriting"})
                query_text = rewrite_query(self.llm_client, question, prior_messages, self.prompts)

            yield frame("status", {"stage": "searching", "query": query_text})
            query = self.retrieval_engine.make_query(
                query_text,
                max_results=ASK_MAX_RESULTS,
                min_similarity=thread.settings.min_similarity,
                filters=self._filters(thread.settings),
            )
            candidates = self.retrieval_engine.search_candidates(query)

            yield frame("status", {"stage": "ranking"})
            results = self.retrieval_engine.rank_candidates(query, candidates)
            results = results[: self.max_context_chunks]
            citations = [_citation(n, r) for n, r in enumerate(results, start=1)]
            yield frame("citations", {"citations": [
                _with_full_text(c, r) if include_full_text else c
                for c, r in zip(citations, results)
            ]})

            if not results:
                text = self.prompts["no_context_found"]
                parts.append(text)
                yield frame("token", {"text": text})
            else:
                messages = build_chat_messages(question, results, prior_messages, self.prompts)
                stream = self.llm_client.generate_stream(messages)
                stream_iter = iter(stream)
                for delta in stream_iter:
                    parts.append(delta)
                    yield frame("token", {"text": delta})

            write_attempted = True
            message = self._save_assistant(
                thread.id, "".join(parts), citations,
                stream.usage if stream is not None else None, "complete",
            )
            yield frame("done", {
                "thread_id": thread.id,
                "message_id": message.id,
                "disclaimer": self.disclaimer,
            })
        except GeneratorExit:
            save_partial()
            fallback_title_if_new()
            raise
        except Exception as e:
            # Never echo exception text (it may carry provider or DB details).
            logger.error(f"Chat turn failed: {type(e).__name__}")
            save_partial()
            fallback_title_if_new()
            trace.update(metadata={"status": "error"})
            yield frame("error", {"message": ERROR_MESSAGE})
            return

        # After `done`: best effort only.
        if is_new:
            try:
                title = generate_title(self.llm_client, question, self.prompts)
                self.repository.set_title_if_empty(thread.id, title)
            except Exception as e:
                logger.warning(f"Chat titling failed: {type(e).__name__}")
        try:
            trace.update(
                output="".join(parts),
                metadata={"status": "complete", "sources_count": len(citations)},
            )
        except Exception as e:
            logger.warning(f"Chat trace update failed: {type(e).__name__}")

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _filters(settings: ThreadSettings) -> Optional[Dict[str, Any]]:
        """Same source filter as /api/v1/ask; None when every source is selected."""
        source = normalize_sources(settings.sources, configured_sources())
        return {"source": source} if source is not None else None

    def _save_assistant(self, thread_id, content, citations, usage, status) -> Message:
        tokens = cost = None
        if usage:
            tokens = (usage.get("tokens_used") or {}).get("total")
            cost = usage.get("cost")
        return self.repository.append_message(
            thread_id, "assistant", content,
            status=status, citations=citations, tokens=tokens, cost=cost,
        )


def _citation(n: int, r: RetrievalResult) -> dict:
    c = r.chunk
    return {
        "n": n,
        "article_title": c.article_title,
        "section": c.section,
        "url": c.url,
        "source": c.source,
        "similarity_score": r.similarity_score,
        "excerpt": c.text[:EXCERPT_MAX_CHARS],
    }


def _with_full_text(citation: dict, r: RetrievalResult) -> dict:
    return {**citation, "full_text": r.chunk.text}
