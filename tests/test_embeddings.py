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
