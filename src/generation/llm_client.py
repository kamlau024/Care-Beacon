"""LLM client wrapper for OpenAI and Anthropic APIs."""

import time
from typing import Dict, Any, Optional, List
from openai import OpenAI
import os

from src.config_loader import get_config


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
    ):
        """Initialize LLM client.

        Args:
            provider: LLM provider ("openai" or "anthropic")
            model: Model name (e.g., "gpt-4o-mini")
            api_key: API key (if None, loads from environment)
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

        # Initialize client
        if self.provider == "openai":
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            self.client = OpenAI(api_key=api_key)
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
        start_time = time.time()

        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        # Call appropriate provider
        if self.provider == "openai":
            result = self._generate_openai(system_prompt, user_prompt, max_tokens, temperature)
        else:
            raise NotImplementedError(f"Provider {self.provider} not implemented")

        # Calculate time
        generation_time = (time.time() - start_time) * 1000  # Convert to ms

        # Update tracking
        self.call_count += 1

        return {
            **result,
            "generation_time_ms": generation_time,
        }

    def _generate_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """Generate response using OpenAI API.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            max_tokens: Maximum tokens
            temperature: Temperature

        Returns:
            Dictionary with answer, tokens_used, cost, model
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Call API with retries
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=self.timeout,
                )

                # Extract response
                answer = response.choices[0].message.content

                # Extract token usage
                usage = response.usage
                input_tokens = usage.prompt_tokens
                output_tokens = usage.completion_tokens
                total_tokens = usage.total_tokens

                # Calculate cost
                cost = (
                    (input_tokens / 1000) * self.cost_per_1k_input +
                    (output_tokens / 1000) * self.cost_per_1k_output
                )

                # Update totals
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                self.total_cost += cost

                return {
                    "answer": answer,
                    "tokens_used": {
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": total_tokens,
                    },
                    "cost": cost,
                    "model": self.model,
                }

            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"API error, retrying in {wait_time}s... ({str(e)[:100]})")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"LLM API call failed after {self.max_retries} attempts: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "total_calls": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": self.total_cost,
            "avg_input_tokens_per_call": (
                self.total_input_tokens / self.call_count if self.call_count > 0 else 0
            ),
            "avg_output_tokens_per_call": (
                self.total_output_tokens / self.call_count if self.call_count > 0 else 0
            ),
            "avg_cost_per_call": (
                self.total_cost / self.call_count if self.call_count > 0 else 0
            ),
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0
