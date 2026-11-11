"""LLM client wrapper for OpenAI and Anthropic APIs."""

import time
from typing import Dict, Any, Optional, List
import os

from src.caching.stats_store import StatsStore
from src.config_loader import get_config
from src.observability.tracing import get_openai_client


class LLMClient:
    """Unified client for LLM APIs (OpenAI, Anthropic).

    Handles:
    - API calls with retry logic
    - Cost tracking
    - Token usage monitoring
    - Multiple provider support
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        stats_store: Optional["StatsStore"] = None,
    ):
        """Initialize LLM client.

        Args:
            provider: LLM provider ("openai" or "anthropic")
            model: Model name (e.g., "gpt-4o-mini")
            api_key: API key (if None, loads from environment)
            stats_store: Optional shared StatsStore for cross-instance counters
        """
        config = get_config()
        llm_config = config.get("llm", {})

        self.provider = provider or llm_config.get("provider", "openai")
        self.model = model or llm_config.get("model", "gpt-4o-mini")
        self.max_tokens = llm_config.get("max_tokens", 1000)
        self.temperature = llm_config.get("temperature", 0.1)
        self.max_retries = llm_config.get("max_retries", 3)
        self.timeout = llm_config.get("timeout", 30)

        # Load cost configuration
        cost_config = config.get("cost_tracking", {})
        self.cost_per_1k_input = cost_config.get("llm_cost_input_per_1k", 0.00015)
        self.cost_per_1k_output = cost_config.get("llm_cost_output_per_1k", 0.0006)

        # Cost tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0
        self.stats_store = stats_store or StatsStore(None)

        # Initialize client
        if self.provider == "openai":
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            self.client = get_openai_client(api_key)
        elif self.provider == "anthropic":
            # Future: Initialize Anthropic client
            raise NotImplementedError("Anthropic provider not yet implemented")
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate a response from the LLM.

        Args:
            system_prompt: System prompt (context/instructions)
            user_prompt: User prompt (query/question)
            max_tokens: Maximum tokens in response (overrides default)
            temperature: Temperature for generation (overrides default)

        Returns:
            Dictionary with:
                - answer: Generated text
                - tokens_used: Dict with input, output, total tokens
                - cost: Cost in USD
                - model: Model used
                - generation_time_ms: Time taken in milliseconds
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.generate_messages(
            messages, max_tokens=max_tokens, temperature=temperature
        )

    def generate_messages(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a response from an arbitrary message list (blocking).

        Returns the same dictionary shape as ``generate()``.
        """
        start_time = time.time()

        if max_tokens is None:
            max_tokens = self.max_tokens
        if temperature is None:
            temperature = self.temperature
        model = model or self.model

        if self.provider == "openai":
            result = self._generate_openai(messages, max_tokens, temperature, model)
        else:
            raise NotImplementedError(f"Provider {self.provider} not implemented")

        generation_time = (time.time() - start_time) * 1000  # Convert to ms

        self.call_count += 1
        self.stats_store.incr("llm_calls")

        return {
            **result,
            "generation_time_ms": generation_time,
        }

    def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> "LLMStream":
        """Open a streaming completion and return an iterable of text deltas.

        Only the opening API call is retried; once iteration has started,
        errors propagate. ``LLMStream.usage`` is set when the usage chunk
        arrives, at which point cost and token counters are recorded.
        """
        if self.provider != "openai":
            raise NotImplementedError(f"Provider {self.provider} not implemented")

        if max_tokens is None:
            max_tokens = self.max_tokens
        if temperature is None:
            temperature = self.temperature
        model = model or self.model

        raw = self._with_retries(
            lambda: self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.timeout,
                stream=True,
                stream_options={"include_usage": True},
            )
        )
        return LLMStream(self, raw, model)

    def _with_retries(self, call):
        """Run ``call`` with exponential-backoff retries."""
        for attempt in range(self.max_retries):
            try:
                return call()
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"API error, retrying in {wait_time}s... ({str(e)[:100]})")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"LLM API call failed after {self.max_retries} attempts: {e}")

    def _generate_openai(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        temperature: float,
        model: str,
    ) -> Dict[str, Any]:
        """Generate response using OpenAI API.

        Returns:
            Dictionary with answer, tokens_used, cost, model
        """

        def _call() -> Dict[str, Any]:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.timeout,
            )
            answer = response.choices[0].message.content
            usage = response.usage
            tokens_used, cost = self._record_usage(
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
            )
            return {
                "answer": answer,
                "tokens_used": tokens_used,
                "cost": cost,
                "model": model,
            }

        return self._with_retries(_call)

    def _record_usage(self, input_tokens: int, output_tokens: int, total_tokens: int):
        """Compute cost and update all token/cost counters. Returns (tokens_used, cost)."""
        cost = (
            (input_tokens / 1000) * self.cost_per_1k_input +
            (output_tokens / 1000) * self.cost_per_1k_output
        )
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        self.stats_store.incr("llm_input_tokens", input_tokens)
        self.stats_store.incr("llm_output_tokens", output_tokens)
        self._record_cost(cost)
        return (
            {"input": input_tokens, "output": output_tokens, "total": total_tokens},
            cost,
        )

    def _record_cost(self, cost: float) -> None:
        """Record spend in the cumulative counter and the per-UTC-day counter.

        Every call path (including streaming) should use this so the daily
        spend cap sees all model cost.
        """
        self.stats_store.incr_float("llm_cost", cost)
        self.stats_store.incr_daily_cost(cost)

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics.

        Returns:
            Dictionary with statistics
        """
        persisted = self.stats_store.get_all()
        calls = int(persisted.get("llm_calls", self.call_count))
        input_tokens = int(persisted.get("llm_input_tokens", self.total_input_tokens))
        output_tokens = int(persisted.get("llm_output_tokens", self.total_output_tokens))
        total_cost = persisted.get("llm_cost", self.total_cost)

        return {
            "provider": self.provider,
            "model": self.model,
            "total_calls": calls,
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "total_cost": total_cost,
            "avg_input_tokens_per_call": (
                input_tokens / calls if calls > 0 else 0
            ),
            "avg_output_tokens_per_call": (
                output_tokens / calls if calls > 0 else 0
            ),
            "avg_cost_per_call": (
                total_cost / calls if calls > 0 else 0
            ),
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0
        self.stats_store.reset()


class LLMStream:
    """Iterable of text deltas from a streaming completion.

    ``usage`` stays ``None`` until the usage chunk arrives (and if the stream
    never delivers one). Mid-stream errors propagate and are not retried.
    """

    def __init__(self, client: LLMClient, raw_stream: Any, model: str):
        self._client = client
        self._raw = raw_stream
        self._model = model
        self.usage: Optional[Dict[str, Any]] = None

    def __iter__(self):
        for chunk in self._raw:
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                tokens_used, cost = self._client._record_usage(
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
                )
                self._client.call_count += 1
                self._client.stats_store.incr("llm_calls")
                self.usage = {
                    "tokens_used": tokens_used,
                    "cost": cost,
                    "model": self._model,
                }
            choices = getattr(chunk, "choices", None)
            if choices:
                text = choices[0].delta.content
                if text:
                    yield text
