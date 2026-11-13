"""Optional Langfuse tracing.

Tracing is off unless LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST
are all set. This is the only module that imports ``langfuse``, and it imports
it lazily so the disabled path never loads the SDK. Tracing is best effort:
any SDK failure is logged and swallowed, never raised into the caller.
"""

import os
import sys
from contextlib import ExitStack, contextmanager
from typing import Any, Dict, Iterator, Optional

from loguru import logger
from openai import OpenAI

_ENV_VARS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")


def tracing_enabled() -> bool:
    """True only when all three LANGFUSE_* variables are set."""
    return all(os.getenv(name) for name in _ENV_VARS)


class _Handle:
    """Handle to a trace or span. `update` never raises."""

    def __init__(self, observation: Any = None):
        self._observation = observation

    def update(self, output: Any = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        if self._observation is None:
            return
        kwargs: Dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        if not kwargs:
            return
        try:
            self._observation.update(**kwargs)
        except Exception as e:
            logger.warning(f"Langfuse update failed: {e}")


def _get_client() -> Any:
    from langfuse import get_client

    return get_client()


def get_openai_client(api_key: str) -> OpenAI:
    """Langfuse-wrapped OpenAI client when tracing is enabled, plain otherwise."""
    if tracing_enabled():
        try:
            # Importing langfuse.openai instruments the openai package, so only
            # do it when tracing is on. It exposes the same OpenAI class.
            from langfuse.openai import OpenAI as TracedOpenAI

            return TracedOpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"Langfuse OpenAI instrumentation failed: {e}")
    return OpenAI(api_key=api_key)


@contextmanager
def _observation(
    stack_factory,
) -> Iterator[_Handle]:
    """Enter an SDK context manager best-effort; always re-raise body errors."""
    stack = ExitStack()
    handle = _Handle()
    try:
        handle = _Handle(stack_factory(stack))
    except Exception as e:
        logger.warning(f"Langfuse tracing start failed: {e}")
        try:
            stack.close()  # unwind anything entered before the failure
        except Exception:
            pass
        stack = ExitStack()
        handle = _Handle()
    try:
        yield handle
    except BaseException:
        exc = sys.exc_info()
        try:
            stack.__exit__(*exc)
        except Exception as e:
            logger.warning(f"Langfuse tracing end failed: {e}")
        raise
    else:
        try:
            stack.close()
        except Exception as e:
            logger.warning(f"Langfuse tracing end failed: {e}")


@contextmanager
def request_trace(
    name: str,
    *,
    metadata: Dict[str, Any],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Iterator[_Handle]:
    """Root trace for one request. Yields a handle with `.update(...)`."""
    if not tracing_enabled():
        yield _Handle()
        return

    def start(stack: ExitStack) -> Any:
        from langfuse import propagate_attributes

        client = _get_client()
        stack.enter_context(
            propagate_attributes(trace_name=name, session_id=session_id, user_id=user_id)
        )
        return stack.enter_context(
            client.start_as_current_observation(as_type="span", name=name, metadata=metadata)
        )

    with _observation(start) as handle:
        yield handle


@contextmanager
def span(name: str, *, input: Any = None) -> Iterator[_Handle]:
    """Child span of the current trace. Yields a handle with `.update(...)`."""
    if not tracing_enabled():
        yield _Handle()
        return

    def start(stack: ExitStack) -> Any:
        client = _get_client()
        return stack.enter_context(
            client.start_as_current_observation(as_type="span", name=name, input=input)
        )

    with _observation(start) as handle:
        yield handle


def flush() -> None:
    """Flush pending events (needed on serverless). No-op when disabled."""
    if not tracing_enabled():
        return
    try:
        _get_client().flush()
    except Exception as e:
        logger.warning(f"Langfuse flush failed: {e}")
