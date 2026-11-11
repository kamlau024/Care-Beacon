"""Tests for LLM client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from src.generation.llm_client import LLMClient


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = "This is a test response from the LLM."

    response.usage = Mock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    response.usage.total_tokens = 150

    return response


@pytest.fixture
def mock_openai_client(mock_openai_response):
    """Create a mock OpenAI client."""
    client = Mock()
    client.chat.completions.create.return_value = mock_openai_response
    return client


def test_llm_client_initialization_openai():
    """Test LLM client initializes with OpenAI provider."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client") as mock_openai:
            client = LLMClient(provider="openai", model="gpt-4o-mini")

            assert client.provider == "openai"
            assert client.model == "gpt-4o-mini"
            assert client.call_count == 0
            assert client.total_cost == 0.0
            mock_openai.assert_called_once_with("test-key")


def test_llm_client_initialization_missing_api_key():
    """Test LLM client raises error when API key is missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="OpenAI API key not found"):
            LLMClient(provider="openai")


def test_llm_client_initialization_anthropic_not_implemented():
    """Test LLM client raises error for Anthropic provider (not yet implemented)."""
    with pytest.raises(NotImplementedError, match="Anthropic provider not yet implemented"):
        LLMClient(provider="anthropic")


def test_llm_client_initialization_invalid_provider():
    """Test LLM client raises error for invalid provider."""
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMClient(provider="invalid-provider")


def test_llm_client_initialization_with_custom_api_key():
    """Test LLM client initialization with custom API key."""
    with patch("src.generation.llm_client.get_openai_client") as mock_openai:
        client = LLMClient(provider="openai", api_key="custom-key")

        mock_openai.assert_called_once_with("custom-key")


def test_llm_client_initialization_defaults_from_config():
    """Test LLM client loads defaults from config."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client"):
            client = LLMClient()

            # Should load from config
            assert client.provider == "openai"
            assert client.model == "gpt-4o-mini"
            assert client.max_tokens == 1000
            assert client.temperature == 0.1
            assert client.max_retries == 3
            assert client.timeout == 30


def test_generate_basic(mock_openai_client, mock_openai_response):
    """Test basic text generation."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai", model="gpt-4o-mini")

            result = client.generate(
                system_prompt="You are a helpful assistant.",
                user_prompt="What is cancer?"
            )

            assert result["answer"] == "This is a test response from the LLM."
            assert result["tokens_used"]["input"] == 100
            assert result["tokens_used"]["output"] == 50
            assert result["tokens_used"]["total"] == 150
            assert result["cost"] > 0
            assert result["model"] == "gpt-4o-mini"
            assert result["generation_time_ms"] >= 0

            # Verify API was called correctly
            mock_openai_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4o-mini"
            assert len(call_kwargs["messages"]) == 2
            assert call_kwargs["messages"][0]["role"] == "system"
            assert call_kwargs["messages"][1]["role"] == "user"


def test_generate_with_custom_parameters(mock_openai_client):
    """Test generation with custom max_tokens and temperature."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            client.generate(
                system_prompt="System",
                user_prompt="User",
                max_tokens=500,
                temperature=0.5
            )

            call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 500
            assert call_kwargs["temperature"] == 0.5


def test_generate_cost_calculation(mock_openai_client):
    """Test cost calculation is accurate."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            result = client.generate(
                system_prompt="System",
                user_prompt="User"
            )

            # Cost = (100/1000 * 0.00015) + (50/1000 * 0.0006)
            # Cost = 0.015 + 0.03 = 0.045
            expected_cost = (100 / 1000) * 0.00015 + (50 / 1000) * 0.0006
            assert abs(result["cost"] - expected_cost) < 0.00001


def test_generate_updates_statistics(mock_openai_client):
    """Test that generate() updates usage statistics."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            # Initial state
            assert client.call_count == 0
            assert client.total_input_tokens == 0
            assert client.total_output_tokens == 0
            assert client.total_cost == 0.0

            # Generate once
            client.generate(system_prompt="System", user_prompt="User")

            assert client.call_count == 1
            assert client.total_input_tokens == 100
            assert client.total_output_tokens == 50
            assert client.total_cost > 0

            # Generate again
            client.generate(system_prompt="System", user_prompt="User")

            assert client.call_count == 2
            assert client.total_input_tokens == 200
            assert client.total_output_tokens == 100


def test_generate_retry_on_api_error(mock_openai_client):
    """Test retry logic when API call fails."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            # Set up mock to fail twice, then succeed
            mock_openai_client.chat.completions.create.side_effect = [
                Exception("API Error 1"),
                Exception("API Error 2"),
                mock_openai_client.chat.completions.create.return_value
            ]

            client = LLMClient(provider="openai", model="gpt-4o-mini")

            # Mock time.sleep to avoid actual delays in tests
            with patch("time.sleep"):
                result = client.generate(
                    system_prompt="System",
                    user_prompt="User"
                )

            # Should succeed on third attempt
            assert result["answer"] == "This is a test response from the LLM."
            assert mock_openai_client.chat.completions.create.call_count == 3


def test_generate_max_retries_exceeded():
    """Test that exception is raised when max retries exceeded."""
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")

    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_client):
            client = LLMClient(provider="openai")

            with patch("time.sleep"):
                with pytest.raises(Exception, match="LLM API call failed after 3 attempts"):
                    client.generate(
                        system_prompt="System",
                        user_prompt="User"
                    )

            # Should have tried max_retries times (3)
            assert mock_client.chat.completions.create.call_count == 3


def test_generate_exponential_backoff():
    """Test exponential backoff delay between retries."""
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = [
        Exception("Error 1"),
        Exception("Error 2"),
        Mock(choices=[Mock(message=Mock(content="Success"))],
             usage=Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150))
    ]

    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_client):
            client = LLMClient(provider="openai")

            with patch("time.sleep") as mock_sleep:
                client.generate(system_prompt="System", user_prompt="User")

                # Should sleep with exponential backoff: 2^0=1s, 2^1=2s
                assert mock_sleep.call_count == 2
                mock_sleep.assert_any_call(1)  # First retry: 2^0
                mock_sleep.assert_any_call(2)  # Second retry: 2^1


def test_get_stats_initial():
    """Test get_stats returns correct initial values."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client"):
            client = LLMClient(provider="openai", model="gpt-4o-mini")

            stats = client.get_stats()

            assert stats["provider"] == "openai"
            assert stats["model"] == "gpt-4o-mini"
            assert stats["total_calls"] == 0
            assert stats["total_input_tokens"] == 0
            assert stats["total_output_tokens"] == 0
            assert stats["total_tokens"] == 0
            assert stats["total_cost"] == 0.0
            assert stats["avg_input_tokens_per_call"] == 0
            assert stats["avg_output_tokens_per_call"] == 0
            assert stats["avg_cost_per_call"] == 0


def test_get_stats_after_calls(mock_openai_client):
    """Test get_stats returns correct values after API calls."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            # Make 2 calls
            client.generate(system_prompt="System", user_prompt="User")
            client.generate(system_prompt="System", user_prompt="User")

            stats = client.get_stats()

            assert stats["total_calls"] == 2
            assert stats["total_input_tokens"] == 200
            assert stats["total_output_tokens"] == 100
            assert stats["total_tokens"] == 300
            assert stats["total_cost"] > 0
            assert stats["avg_input_tokens_per_call"] == 100
            assert stats["avg_output_tokens_per_call"] == 50
            assert stats["avg_cost_per_call"] > 0


def test_reset_stats(mock_openai_client):
    """Test reset_stats clears all statistics."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            # Generate to accumulate stats
            client.generate(system_prompt="System", user_prompt="User")

            assert client.call_count > 0
            assert client.total_cost > 0

            # Reset
            client.reset_stats()

            assert client.call_count == 0
            assert client.total_input_tokens == 0
            assert client.total_output_tokens == 0
            assert client.total_cost == 0.0

            # Verify get_stats also shows reset values
            stats = client.get_stats()
            assert stats["total_calls"] == 0
            assert stats["total_cost"] == 0.0


def test_generate_with_timeout_setting(mock_openai_client):
    """Test that timeout is passed to API call."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            client.generate(system_prompt="System", user_prompt="User")

            call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["timeout"] == 30  # Default timeout from config


def test_generate_unsupported_provider_error():
    """Test that generate raises error for non-OpenAI provider."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client"):
            client = LLMClient(provider="openai")

            # Manually change provider to test error handling
            client.provider = "unsupported"

            with pytest.raises(NotImplementedError, match="Provider unsupported not implemented"):
                client.generate(system_prompt="System", user_prompt="User")


def test_cost_tracking_configuration():
    """Test that cost tracking uses configured rates."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client"):
            client = LLMClient(provider="openai")

            # Verify cost rates are loaded from config
            assert client.cost_per_1k_input == 0.00015  # Default from config
            assert client.cost_per_1k_output == 0.0006  # Default from config


def test_generation_time_measurement(mock_openai_client):
    """Test that generation time is measured correctly."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            # Mock time.time to control timing
            with patch("time.time", side_effect=[0.0, 0.5]):  # 500ms difference
                result = client.generate(system_prompt="System", user_prompt="User")

                # Should be 500ms
                assert result["generation_time_ms"] == 500.0


def test_prompt_structure(mock_openai_client):
    """Test that system and user prompts are formatted correctly."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            system_text = "You are a medical assistant."
            user_text = "What is cancer?"

            client.generate(system_prompt=system_text, user_prompt=user_text)

            call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
            messages = call_kwargs["messages"]

            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == system_text
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == user_text


def test_zero_temperature_is_passed_through(mock_openai_client):
    """An explicit temperature=0.0 must reach the API, not be replaced by the default."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            client.generate("s", "u", temperature=0.0)

            call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.0


def test_zero_max_tokens_is_passed_through(mock_openai_client):
    """An explicit max_tokens=0 must not be replaced by the default."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            client = LLMClient(provider="openai")

            client.generate("s", "u", max_tokens=0)

            call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 0


# ---------------------------------------------------------------------------
# Message lists and streaming
# ---------------------------------------------------------------------------

def _delta_chunk(text):
    chunk = Mock()
    chunk.choices = [Mock()]
    chunk.choices[0].delta.content = text
    chunk.usage = None
    return chunk


def _usage_chunk(prompt=100, completion=50):
    chunk = Mock()
    chunk.choices = []
    chunk.usage = Mock()
    chunk.usage.prompt_tokens = prompt
    chunk.usage.completion_tokens = completion
    chunk.usage.total_tokens = prompt + completion
    return chunk


def _stream_client(chunks_or_iter):
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = chunks_or_iter
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_client):
            llm = LLMClient(provider="openai")
    return llm, mock_client


def test_stream_yields_deltas_and_sets_usage():
    llm, mock_client = _stream_client(
        iter([_delta_chunk("Hel"), _delta_chunk("lo"), _usage_chunk(100, 50)])
    )
    messages = [{"role": "user", "content": "hi"}]

    stream = llm.generate_stream(messages, max_tokens=10, temperature=0.0, model="other-model")
    assert stream.usage is None
    assert "".join(stream) == "Hello"

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}
    assert kwargs["temperature"] == 0.0
    assert kwargs["model"] == "other-model"
    assert kwargs["messages"] == messages

    expected_cost = (100 / 1000) * llm.cost_per_1k_input + (50 / 1000) * llm.cost_per_1k_output
    assert stream.usage["tokens_used"] == {"input": 100, "output": 50, "total": 150}
    assert stream.usage["cost"] == pytest.approx(expected_cost)
    assert stream.usage["model"] == "other-model"
    assert llm.total_input_tokens == 100
    assert llm.total_output_tokens == 50
    assert llm.total_cost == pytest.approx(expected_cost)


def test_stream_records_daily_cost():
    llm, _ = _stream_client(iter([_delta_chunk("a"), _usage_chunk(100, 50)]))
    llm.stats_store = Mock()

    list(llm.generate_stream([{"role": "user", "content": "hi"}]))

    expected_cost = (100 / 1000) * llm.cost_per_1k_input + (50 / 1000) * llm.cost_per_1k_output
    llm.stats_store.incr_daily_cost.assert_called_once_with(pytest.approx(expected_cost))
    llm.stats_store.incr_float.assert_called_once_with("llm_cost", pytest.approx(expected_cost))
    llm.stats_store.incr.assert_any_call("llm_input_tokens", 100)
    llm.stats_store.incr.assert_any_call("llm_output_tokens", 50)


def test_stream_error_after_first_delta_propagates_without_retry():
    def broken():
        yield _delta_chunk("Hel")
        raise RuntimeError("connection dropped")

    llm, mock_client = _stream_client(broken())
    stream = llm.generate_stream([{"role": "user", "content": "hi"}])

    it = iter(stream)
    assert next(it) == "Hel"
    with pytest.raises(RuntimeError, match="connection dropped"):
        next(it)
    assert mock_client.chat.completions.create.call_count == 1
    assert stream.usage is None


def test_stream_usage_stays_none_without_usage_chunk():
    llm, _ = _stream_client(iter([_delta_chunk("Hi")]))
    stream = llm.generate_stream([{"role": "user", "content": "hi"}])
    assert "".join(stream) == "Hi"
    assert stream.usage is None


def test_stream_retries_opening_call():
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = [
        Exception("boom"),
        iter([_delta_chunk("ok"), _usage_chunk()]),
    ]
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_client):
            llm = LLMClient(provider="openai")
    with patch("time.sleep"):
        stream = llm.generate_stream([{"role": "user", "content": "hi"}])
    assert "".join(stream) == "ok"
    assert mock_client.chat.completions.create.call_count == 2


def test_generate_delegates_to_generate_messages():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client"):
            llm = LLMClient(provider="openai")
    llm.generate_messages = Mock(return_value={"answer": "x", "tokens_used": {}, "cost": 0.0, "model": "m"})

    result = llm.generate("SYS", "USR", max_tokens=5, temperature=0.0)

    llm.generate_messages.assert_called_once_with(
        [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USR"}],
        max_tokens=5,
        temperature=0.0,
    )
    assert result["answer"] == "x"


def test_generate_messages_model_override(mock_openai_client):
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("src.generation.llm_client.get_openai_client", return_value=mock_openai_client):
            llm = LLMClient(provider="openai")
    msgs = [{"role": "user", "content": "q"}]
    result = llm.generate_messages(msgs, model="utility-model", temperature=0.0)
    kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "utility-model"
    assert kwargs["temperature"] == 0.0
    assert kwargs["messages"] == msgs
    assert result["model"] == "utility-model"
