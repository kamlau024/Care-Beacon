"""Tests for retrieval engine."""

import pytest
from unittest.mock import Mock, MagicMock

from src.retrieval.retrieval_engine import RetrievalEngine
from src.retrieval.models import Query, RetrievedContext, RetrievalConfig
from src.storage.models import Chunk, RetrievalResult
from datetime import datetime


@pytest.fixture
def mock_embedding_generator():
    """Create a mock embedding generator."""
    generator = Mock()
    generator.embed_text.return_value = [0.1] * 1536  # Mock embedding
    generator.get_embedding_stats.return_value = {
        "total_tokens_used": 100,
        "total_cost": 0.002,
    }
    return generator


@pytest.fixture
def mock_vector_db():
    """Create a mock vector database."""
    db = Mock()

    # Create mock chunks
    mock_chunks = []
    for i in range(5):
        chunk = Chunk(
            chunk_id=f"article_{i}_p000",
            text=f"This is test chunk {i} about breast cancer.",
            article_id=f"article_{i}",
            article_title=f"Article {i}",
            url=f"https://example.com/article_{i}",
            breadcrumbs=["Test"],
            cancer_type="Breast Cancer" if i < 3 else None,
            section="Test Section",
            paragraph_index=0,
            total_paragraphs=10,
            embedding=[0.1 + i * 0.1] * 1536,
        )
        mock_chunks.append(chunk)

    # Mock search to return results
    def mock_search(query_embedding, n_results=10, where=None):
        # Filter by metadata if provided
        chunks = mock_chunks
        if where:
            if "cancer_type" in where:
                chunks = [c for c in chunks if c.cancer_type == where["cancer_type"]]
            if "article_id" in where:
                chunks = [c for c in chunks if c.article_id == where["article_id"]]

        # Return top n results
        results = []
        for i, chunk in enumerate(chunks[:n_results]):
            result = RetrievalResult(
                chunk=chunk,
                similarity_score=0.9 - i * 0.1,  # Decreasing scores
                rank=i + 1,
            )
            results.append(result)

        return results

    db.search.side_effect = mock_search
    db.get_chunk.return_value = mock_chunks[0]
    db.get_stats.return_value = {
        "total_chunks": 100,
        "collection_name": "test-collection",
    }

    return db


@pytest.fixture
def retrieval_engine(mock_embedding_generator, mock_vector_db):
    """Create a retrieval engine with mocked dependencies."""
    config = RetrievalConfig(
        default_max_results=10,
        default_min_similarity=0.0,
        rerank_results=False,
        include_metadata=True,
        cache_embeddings=True,
    )

    return RetrievalEngine(
        embedding_generator=mock_embedding_generator,
        vector_db=mock_vector_db,
        config=config,
    )


def test_retrieval_engine_initialization(retrieval_engine):
    """Test that retrieval engine initializes correctly."""
    assert retrieval_engine is not None
    assert retrieval_engine.embedding_generator is not None
    assert retrieval_engine.vector_db is not None
    assert retrieval_engine.config is not None


def test_retrieve_basic(retrieval_engine):
    """Test basic retrieval."""
    query = Query(text="What are symptoms of breast cancer?", max_results=5)

    context = retrieval_engine.retrieve(query)

    assert context is not None
    assert isinstance(context, RetrievedContext)
    assert context.query == query
    assert len(context.results) > 0
    assert context.total_chunks == len(context.results)
    assert context.retrieval_time_ms > 0


def test_retrieve_text_convenience(retrieval_engine):
    """Test convenience method for text retrieval."""
    context = retrieval_engine.retrieve_text("What are symptoms?", max_results=3)

    assert context is not None
    assert context.query.text == "What are symptoms?"
    assert len(context.results) <= 3


def test_retrieve_with_filters(retrieval_engine):
    """Test retrieval with metadata filters."""
    context = retrieval_engine.retrieve_text(
        "What are symptoms?",
        filters={"cancer_type": "Breast Cancer"},
        max_results=5,
    )

    assert context is not None
    assert len(context.results) > 0

    # All results should have cancer_type = Breast Cancer
    for result in context.results:
        if result.chunk.cancer_type:  # Skip if None
            assert result.chunk.cancer_type == "Breast Cancer"


def test_retrieve_for_cancer_type(retrieval_engine):
    """Test retrieval filtered by cancer type."""
    context = retrieval_engine.retrieve_for_cancer_type(
        "symptoms", "Breast Cancer", max_results=5
    )

    assert context is not None
    assert len(context.results) > 0


def test_retrieve_for_article(retrieval_engine):
    """Test retrieval filtered by article."""
    context = retrieval_engine.retrieve_for_article(
        "symptoms", "article_0", max_results=5
    )

    assert context is not None
    assert len(context.results) > 0

    # All results should be from article_0
    for result in context.results:
        assert result.chunk.article_id == "article_0"


def test_retrieve_with_min_similarity(retrieval_engine):
    """Test retrieval with minimum similarity threshold."""
    query = Query(text="symptoms", max_results=10, min_similarity=0.7)

    context = retrieval_engine.retrieve(query)

    # All results should have similarity >= 0.7
    for result in context.results:
        assert result.similarity_score >= 0.7


def test_get_similar_chunks(retrieval_engine):
    """Test finding similar chunks."""
    similar = retrieval_engine.get_similar_chunks("article_0_p000", max_results=3)

    assert similar is not None
    assert len(similar) > 0

    # Should not include the original chunk
    for result in similar:
        assert result.chunk.chunk_id != "article_0_p000"


def test_retrieved_context_get_top_k(retrieval_engine):
    """Test getting top k results from context."""
    context = retrieval_engine.retrieve_text("symptoms", max_results=10)

    top_3 = context.get_top_k(3)

    assert len(top_3) <= 3
    # Should be ordered by score
    for i in range(len(top_3) - 1):
        assert top_3[i].similarity_score >= top_3[i + 1].similarity_score


def test_retrieved_context_get_above_threshold(retrieval_engine):
    """Test getting results above threshold."""
    context = retrieval_engine.retrieve_text("symptoms", max_results=10)

    above_threshold = context.get_above_threshold(0.7)

    # All should be above threshold
    for result in above_threshold:
        assert result.similarity_score >= 0.7


def test_retrieved_context_get_unique_articles(retrieval_engine):
    """Test getting unique articles from results."""
    context = retrieval_engine.retrieve_text("symptoms", max_results=10)

    unique_articles = context.get_unique_articles()

    assert isinstance(unique_articles, list)
    assert len(unique_articles) > 0
    # Should not have duplicates
    assert len(unique_articles) == len(set(unique_articles))


def test_retrieved_context_get_context_text(retrieval_engine):
    """Test getting combined context text."""
    context = retrieval_engine.retrieve_text("symptoms", max_results=3)

    text = context.get_context_text()

    assert isinstance(text, str)
    assert len(text) > 0
    # Should include article titles
    assert "Article" in text


def test_retrieved_context_get_context_text_limited(retrieval_engine):
    """Test getting context text with limit."""
    context = retrieval_engine.retrieve_text("symptoms", max_results=10)

    text = context.get_context_text(max_chunks=2)

    assert isinstance(text, str)
    # Should only include 2 chunks worth of text
    text_parts = text.split("\n\n")
    assert len(text_parts) <= 2


def test_retrieved_context_to_dict(retrieval_engine):
    """Test converting context to dictionary."""
    context = retrieval_engine.retrieve_text("symptoms", max_results=3)

    result_dict = context.to_dict()

    assert isinstance(result_dict, dict)
    assert "query" in result_dict
    assert "results" in result_dict
    assert "total_chunks" in result_dict
    assert "retrieval_time_ms" in result_dict


def test_get_embedding_stats(retrieval_engine):
    """Test getting embedding statistics."""
    stats = retrieval_engine.get_embedding_stats()

    assert isinstance(stats, dict)
    assert "total_tokens_used" in stats


def test_get_database_stats(retrieval_engine):
    """Test getting database statistics."""
    stats = retrieval_engine.get_database_stats()

    assert isinstance(stats, dict)
    assert "total_chunks" in stats


def test_get_config_dict(retrieval_engine):
    """Test getting configuration dictionary."""
    config_dict = retrieval_engine.get_config_dict()

    assert isinstance(config_dict, dict)
    assert "default_max_results" in config_dict
    assert "default_min_similarity" in config_dict


def test_query_model():
    """Test Query data model."""
    query = Query(
        text="test query",
        filters={"cancer_type": "Breast Cancer"},
        max_results=5,
        min_similarity=0.7,
    )

    assert query.text == "test query"
    assert query.filters == {"cancer_type": "Breast Cancer"}
    assert query.max_results == 5
    assert query.min_similarity == 0.7
    assert query.timestamp is not None


def test_retrieval_config_to_dict():
    """Test RetrievalConfig to_dict method."""
    config = RetrievalConfig(
        default_max_results=10,
        default_min_similarity=0.5,
        rerank_results=True,
        include_metadata=True,
        cache_embeddings=False,
    )

    config_dict = config.to_dict()

    assert config_dict["default_max_results"] == 10
    assert config_dict["default_min_similarity"] == 0.5
    assert config_dict["rerank_results"] is True
    assert config_dict["include_metadata"] is True
    assert config_dict["cache_embeddings"] is False
