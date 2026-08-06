"""Tests for embedding generation."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.models import Chunk


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock_client = Mock()

    # Mock embedding response
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]  # 1536-dimensional vector
    mock_response.usage = Mock(total_tokens=10)

    mock_client.embeddings.create.return_value = mock_response

    return mock_client


@pytest.fixture
def generator_with_mock(mock_openai_client):
    """Create embedding generator with mocked client."""
    with patch('src.embeddings.embedding_generator.OpenAI') as mock_openai:
        mock_openai.return_value = mock_openai_client
        generator = EmbeddingGenerator(api_key="test-key")
        return generator


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    chunks = []
    for i in range(5):
        chunk = Chunk(
            chunk_id=f"test-article_section_p{i:03d}",
            text=f"This is test paragraph {i} with some medical content.",
            article_id="test-article",
            article_title="Test Article",
            url="https://example.com",
            breadcrumbs=["Test"],
            section="Test Section",
            paragraph_index=i,
            total_paragraphs=5
        )
        chunks.append(chunk)
    return chunks


def test_generator_initialization(generator_with_mock):
    """Test that generator initializes correctly."""
    assert generator_with_mock is not None
    assert generator_with_mock.model == "text-embedding-3-small"
    assert generator_with_mock.dimensions == 1536
    assert generator_with_mock.batch_size == 100


def test_embed_single_text(generator_with_mock):
    """Test embedding a single text."""
    text = "Test medical text about cancer treatment."

    embedding = generator_with_mock.embed_text(text)

    # Check that embedding is returned
    assert embedding is not None
    assert isinstance(embedding, list)
    assert len(embedding) == 1536
    assert all(isinstance(x, float) for x in embedding)


def test_embed_batch(generator_with_mock):
    """Test embedding a batch of texts."""
    texts = [
        "First medical text.",
        "Second medical text.",
        "Third medical text."
    ]

    # Mock batch response
    mock_response = Mock()
    mock_response.data = [
        Mock(embedding=[0.1] * 1536),
        Mock(embedding=[0.2] * 1536),
        Mock(embedding=[0.3] * 1536)
    ]
    mock_response.usage = Mock(total_tokens=30)

    generator_with_mock.client.embeddings.create.return_value = mock_response

    embeddings = generator_with_mock.embed_batch(texts)

    # Check that embeddings are returned
    assert len(embeddings) == 3
    assert all(len(emb) == 1536 for emb in embeddings)


def test_embed_chunks(generator_with_mock, sample_chunks):
    """Test embedding chunks."""
    # Mock batch response
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1 * i] * 1536) for i in range(5)]
    mock_response.usage = Mock(total_tokens=50)

    generator_with_mock.client.embeddings.create.return_value = mock_response

    # Embed chunks
    result_chunks = generator_with_mock.embed_chunks(sample_chunks, show_progress=False)

    # Check that embeddings are attached
    assert len(result_chunks) == 5
    for chunk in result_chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 1536


def test_cost_tracking(generator_with_mock):
    """Test that costs are tracked correctly."""
    # Reset stats
    generator_with_mock.reset_stats()

    # Mock response
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]
    mock_response.usage = Mock(total_tokens=100)
    generator_with_mock.client.embeddings.create.return_value = mock_response

    # Generate embedding
    generator_with_mock.embed_text("Test text")

    # Check cost tracking
    assert generator_with_mock.total_tokens_used == 100
    assert generator_with_mock.total_cost > 0

    # Get stats
    stats = generator_with_mock.get_embedding_stats()
    assert stats['total_tokens_used'] == 100
    assert stats['total_cost'] > 0
    assert stats['model'] == 'text-embedding-3-small'


def test_reset_stats(generator_with_mock):
    """Test that stats can be reset."""
    # Generate some usage
    generator_with_mock.total_tokens_used = 100
    generator_with_mock.total_cost = 0.05

    # Reset
    generator_with_mock.reset_stats()

    # Check reset
    assert generator_with_mock.total_tokens_used == 0
    assert generator_with_mock.total_cost == 0.0


def test_empty_batch_handling(generator_with_mock):
    """Test handling of empty batch."""
    embeddings = generator_with_mock.embed_batch([])

    assert embeddings == []


def test_empty_chunks_handling(generator_with_mock):
    """Test handling of empty chunks list."""
    result = generator_with_mock.embed_chunks([], show_progress=False)

    assert result == []


def test_large_batch_splitting(generator_with_mock):
    """Test that large batches are automatically split."""
    # Create a large list of texts
    texts = [f"Text {i}" for i in range(250)]  # Exceeds batch_size of 100

    # Mock response to return the correct number of embeddings based on input
    def mock_create(*args, **kwargs):
        input_texts = kwargs.get('input', [])
        num_texts = len(input_texts) if isinstance(input_texts, list) else 1

        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(num_texts)]
        mock_response.usage = Mock(total_tokens=num_texts * 10)
        return mock_response

    generator_with_mock.client.embeddings.create.side_effect = mock_create

    embeddings = generator_with_mock.embed_batch(texts)

    # Should have split into 3 batches (100 + 100 + 50)
    assert len(embeddings) == 250
    assert generator_with_mock.client.embeddings.create.call_count == 3


@pytest.mark.parametrize("model_name,expected_dims", [
    ("text-embedding-3-small", 1536),
    ("text-embedding-3-large", 1536),
])
def test_different_models(mock_openai_client, model_name, expected_dims):
    """Test initialization with different models."""
    with patch('src.embeddings.embedding_generator.OpenAI') as mock_openai:
        mock_openai.return_value = mock_openai_client

        generator = EmbeddingGenerator(api_key="test-key", model=model_name)

        assert generator.model == model_name


def test_embed_text_rate_limit_retry(generator_with_mock):
    """Test retry logic when rate limit is hit."""
    from openai import RateLimitError

    # Mock to fail twice with rate limit, then succeed
    mock_success_response = Mock()
    mock_success_response.data = [Mock(embedding=[0.1] * 1536)]
    mock_success_response.usage = Mock(total_tokens=10)

    generator_with_mock.client.embeddings.create.side_effect = [
        RateLimitError("Rate limit exceeded", response=Mock(status_code=429), body=None),
        RateLimitError("Rate limit exceeded", response=Mock(status_code=429), body=None),
        mock_success_response
    ]

    # Mock time.sleep to avoid actual delays
    with patch('time.sleep') as mock_sleep:
        embedding = generator_with_mock.embed_text("Test text")

        assert embedding is not None
        assert len(embedding) == 1536

        # Should have retried twice (exponential backoff: 1s, 2s)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)  # 2^0 * retry_delay
        mock_sleep.assert_any_call(2.0)  # 2^1 * retry_delay


def test_embed_text_rate_limit_max_retries_exceeded(generator_with_mock):
    """Test that exception is raised when rate limit retries are exceeded."""
    from openai import RateLimitError

    generator_with_mock.client.embeddings.create.side_effect = RateLimitError(
        "Rate limit exceeded", response=Mock(status_code=429), body=None
    )

    with patch('time.sleep'):
        with pytest.raises(Exception, match="Rate limit exceeded after 3 retries"):
            generator_with_mock.embed_text("Test text")

    # Should have tried max_retries times
    assert generator_with_mock.client.embeddings.create.call_count == 3


def test_embed_text_api_error_retry(generator_with_mock):
    """Test retry logic when API error occurs."""
    from openai import APIError

    # Mock to fail once with API error, then succeed
    mock_success_response = Mock()
    mock_success_response.data = [Mock(embedding=[0.1] * 1536)]
    mock_success_response.usage = Mock(total_tokens=10)

    generator_with_mock.client.embeddings.create.side_effect = [
        APIError("API error", request=Mock(), body=None),
        mock_success_response
    ]

    with patch('time.sleep') as mock_sleep:
        embedding = generator_with_mock.embed_text("Test text")

        assert embedding is not None
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(1.0)  # First retry


def test_embed_text_api_error_max_retries_exceeded(generator_with_mock):
    """Test that exception is raised when API error retries are exceeded."""
    from openai import APIError

    generator_with_mock.client.embeddings.create.side_effect = APIError(
        "API error", request=Mock(), body=None
    )

    with patch('time.sleep'):
        with pytest.raises(Exception, match="API error after 3 retries"):
            generator_with_mock.embed_text("Test text")


def test_embed_text_unexpected_error(generator_with_mock):
    """Test handling of unexpected errors."""
    generator_with_mock.client.embeddings.create.side_effect = ValueError("Unexpected error")

    with pytest.raises(Exception, match="Unexpected error generating embedding"):
        generator_with_mock.embed_text("Test text")


def test_embed_batch_rate_limit_retry(generator_with_mock):
    """Test retry logic for batch embedding when rate limit is hit."""
    from openai import RateLimitError

    texts = ["Text 1", "Text 2", "Text 3"]

    # Mock to fail once with rate limit, then succeed
    mock_success_response = Mock()
    mock_success_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(3)]
    mock_success_response.usage = Mock(total_tokens=30)

    generator_with_mock.client.embeddings.create.side_effect = [
        RateLimitError("Rate limit exceeded", response=Mock(status_code=429), body=None),
        mock_success_response
    ]

    with patch('time.sleep') as mock_sleep:
        embeddings = generator_with_mock.embed_batch(texts)

        assert len(embeddings) == 3
        assert mock_sleep.call_count == 1


def test_embed_batch_rate_limit_max_retries_exceeded(generator_with_mock):
    """Test that exception is raised when batch rate limit retries are exceeded."""
    from openai import RateLimitError

    texts = ["Text 1", "Text 2"]

    generator_with_mock.client.embeddings.create.side_effect = RateLimitError(
        "Rate limit exceeded", response=Mock(status_code=429), body=None
    )

    with patch('time.sleep'):
        with pytest.raises(Exception, match="Rate limit exceeded after 3 retries"):
            generator_with_mock.embed_batch(texts)


def test_embed_batch_api_error_retry(generator_with_mock):
    """Test retry logic for batch embedding when API error occurs."""
    from openai import APIError

    texts = ["Text 1", "Text 2"]

    # Mock to fail once with API error, then succeed
    mock_success_response = Mock()
    mock_success_response.data = [Mock(embedding=[0.1] * 1536), Mock(embedding=[0.2] * 1536)]
    mock_success_response.usage = Mock(total_tokens=20)

    generator_with_mock.client.embeddings.create.side_effect = [
        APIError("API error", request=Mock(), body=None),
        mock_success_response
    ]

    with patch('time.sleep') as mock_sleep:
        embeddings = generator_with_mock.embed_batch(texts)

        assert len(embeddings) == 2
        assert mock_sleep.call_count == 1


def test_embed_batch_api_error_max_retries_exceeded(generator_with_mock):
    """Test that exception is raised when batch API error retries are exceeded."""
    from openai import APIError

    texts = ["Text 1", "Text 2"]

    generator_with_mock.client.embeddings.create.side_effect = APIError(
        "API error", request=Mock(), body=None
    )

    with patch('time.sleep'):
        with pytest.raises(Exception, match="API error after 3 retries"):
            generator_with_mock.embed_batch(texts)


def test_embed_batch_unexpected_error(generator_with_mock):
    """Test handling of unexpected errors in batch embedding."""
    texts = ["Text 1", "Text 2"]

    generator_with_mock.client.embeddings.create.side_effect = ValueError("Unexpected error")

    with pytest.raises(Exception, match="Unexpected error generating embeddings"):
        generator_with_mock.embed_batch(texts)


def test_embed_chunks_with_progress_display(generator_with_mock, sample_chunks, capsys):
    """Test embed_chunks with progress display enabled."""
    # Mock batch response
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1 * i] * 1536) for i in range(5)]
    mock_response.usage = Mock(total_tokens=50)

    generator_with_mock.client.embeddings.create.return_value = mock_response
    generator_with_mock.reset_stats()

    # Embed chunks with progress display
    result_chunks = generator_with_mock.embed_chunks(sample_chunks, show_progress=True)

    # Capture output
    captured = capsys.readouterr()

    # Check that progress messages were printed
    assert "Processing batch" in captured.out
    assert "✅ Generated 5 embeddings" in captured.out
    assert "Total tokens used:" in captured.out
    assert "Total cost:" in captured.out

    # Check results
    assert len(result_chunks) == 5
    for chunk in result_chunks:
        assert chunk.embedding is not None


def test_embed_chunks_multiple_batches_with_progress(generator_with_mock, capsys):
    """Test embed_chunks with multiple batches and progress display."""
    # Create more chunks than batch size
    chunks = []
    for i in range(150):  # Exceeds batch_size of 100
        chunk = Chunk(
            chunk_id=f"chunk_{i}",
            text=f"Text {i}",
            article_id="test",
            article_title="Test",
            url="https://example.com",
            breadcrumbs=["Test"],
            section="Test",
            paragraph_index=i,
            total_paragraphs=150
        )
        chunks.append(chunk)

    # Mock response to return correct number of embeddings
    def mock_create(*args, **kwargs):
        input_texts = kwargs.get('input', [])
        num_texts = len(input_texts) if isinstance(input_texts, list) else 1

        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(num_texts)]
        mock_response.usage = Mock(total_tokens=num_texts * 10)
        return mock_response

    generator_with_mock.client.embeddings.create.side_effect = mock_create

    # Embed chunks with progress
    result_chunks = generator_with_mock.embed_chunks(chunks, show_progress=True)

    # Capture output
    captured = capsys.readouterr()

    # Should show progress for 2 batches (100 + 50)
    assert "Processing batch 1/2" in captured.out
    assert "Processing batch 2/2" in captured.out
    assert len(result_chunks) == 150


def test_exponential_backoff_timing(generator_with_mock):
    """Test that exponential backoff uses correct timing."""
    from openai import RateLimitError

    # Set retry_delay to 2.0 for easier calculation
    generator_with_mock.retry_delay = 2.0

    mock_success_response = Mock()
    mock_success_response.data = [Mock(embedding=[0.1] * 1536)]
    mock_success_response.usage = Mock(total_tokens=10)

    generator_with_mock.client.embeddings.create.side_effect = [
        RateLimitError("Rate limit", response=Mock(status_code=429), body=None),
        RateLimitError("Rate limit", response=Mock(status_code=429), body=None),
        mock_success_response
    ]

    with patch('time.sleep') as mock_sleep:
        generator_with_mock.embed_text("Test")

        # Exponential backoff: 2^0 * 2.0 = 2.0, 2^1 * 2.0 = 4.0
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(2.0)  # First retry
        mock_sleep.assert_any_call(4.0)  # Second retry


def test_embedding_generator_initialization_without_api_key():
    """Test that generator loads API key from config when not provided (line 26)."""
    # Don't provide api_key - should load from config via get_api_key()
    with patch('src.embeddings.embedding_generator.OpenAI') as mock_openai:
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key-from-env'}):
            generator = EmbeddingGenerator()  # No api_key parameter (line 26)

            # Should have initialized with API key from config
            assert generator is not None
            mock_openai.assert_called_once()
            # The OpenAI client should be initialized with the key from config
            call_kwargs = mock_openai.call_args.kwargs
            assert 'api_key' in call_kwargs
