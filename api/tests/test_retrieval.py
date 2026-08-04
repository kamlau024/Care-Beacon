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


def test_retrieve_with_source_filter_bc_cancer(retrieval_engine):
    """Test retrieval filtered by BC Cancer source."""
    context = retrieval_engine.retrieve_text(
        "cancer treatment",
        filters={"source": "BC Cancer"},
        max_results=5,
    )

    assert context is not None
    assert len(context.results) > 0

    # All results should be from BC Cancer
    for result in context.results:
        assert result.chunk.source == "BC Cancer"


def test_retrieve_with_source_filter_canadian_cancer_society(retrieval_engine):
    """Test retrieval filtered by Canadian Cancer Society source."""
    context = retrieval_engine.retrieve_text(
        "cancer treatment",
        filters={"source": "Canadian Cancer Society"},
        max_results=5,
    )

    assert context is not None
    # Note: Results might be empty if no Canadian Cancer Society data in test DB
    # This is expected - test verifies the filter works without error


def test_retrieve_without_source_filter_returns_mixed(retrieval_engine):
    """Test retrieval without source filter can return mixed sources."""
    context = retrieval_engine.retrieve_text(
        "cancer treatment",
        max_results=10,
    )

    assert context is not None
    assert len(context.results) > 0

    # Collect unique sources from results
    sources = set(result.chunk.source for result in context.results)

    # Should have at least one source (BC Cancer from test data)
    assert len(sources) >= 1
    assert "BC Cancer" in sources


def test_retrieve_with_combined_source_and_cancer_type_filters(retrieval_engine):
    """Test retrieval with both source and cancer_type filters."""
    context = retrieval_engine.retrieve_text(
        "symptoms",
        filters={
            "source": "BC Cancer",
            "cancer_type": "Breast Cancer"
        },
        max_results=5,
    )

    assert context is not None

    # Verify results match both filters
    for result in context.results:
        assert result.chunk.source == "BC Cancer"
        if result.chunk.cancer_type:  # Skip if None
            assert result.chunk.cancer_type == "Breast Cancer"


def test_retrieved_context_preserves_source_metadata(retrieval_engine):
    """Test that RetrievedContext preserves source metadata."""
    context = retrieval_engine.retrieve_text("cancer", max_results=5)

    assert context is not None
    assert len(context.results) > 0

    # Verify each result has source information
    for result in context.results:
        assert hasattr(result.chunk, 'source')
        assert result.chunk.source is not None
        assert isinstance(result.chunk.source, str)
        assert len(result.chunk.source) > 0


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


def test_retrieval_engine_initialization_with_default_config(mock_embedding_generator, mock_vector_db):
    """Test that retrieval engine initializes with default config loaded from file (lines 56-59)."""
    # Don't provide a config - should load from get_config()
    engine = RetrievalEngine(
        embedding_generator=mock_embedding_generator,
        vector_db=mock_vector_db,
        # No config parameter - will trigger _load_config() (lines 56-59)
    )

    # Verify it initialized with a config loaded from file
    assert engine.config is not None
    assert isinstance(engine.config, RetrievalConfig)
    assert engine.config.default_max_results > 0
    assert engine.config.default_min_similarity >= 0
    assert isinstance(engine.config.rerank_results, bool)
    assert isinstance(engine.config.include_metadata, bool)
    assert isinstance(engine.config.cache_embeddings, bool)


def test_get_similar_chunks_nonexistent_chunk(retrieval_engine, mock_vector_db):
    """Test get_similar_chunks when chunk doesn't exist (line 199)."""
    # Mock get_chunk to return None (chunk doesn't exist)
    mock_vector_db.get_chunk.return_value = None

    similar = retrieval_engine.get_similar_chunks("nonexistent_chunk_id", max_results=5)

    # Should return empty list
    assert similar == []


def test_get_similar_chunks_chunk_without_embedding(retrieval_engine, mock_vector_db):
    """Test get_similar_chunks when chunk has no embedding (line 199)."""
    # Create a chunk without embedding
    chunk_no_embedding = Chunk(
        chunk_id="no_embedding_chunk",
        text="Test chunk without embedding",
        article_id="test",
        article_title="Test Article",
        url="https://example.com",
        breadcrumbs=["Test"],
        section="Test Section",
        paragraph_index=0,
        total_paragraphs=10,
        embedding=None,  # No embedding
    )

    # Mock get_chunk to return chunk without embedding
    mock_vector_db.get_chunk.return_value = chunk_no_embedding

    similar = retrieval_engine.get_similar_chunks("no_embedding_chunk", max_results=5)

    # Should return empty list
    assert similar == []


def test_retrieved_context_get_by_article(retrieval_engine):
    """Test RetrievedContext.get_by_article method (line 84)."""
    # Get a context with multiple articles
    context = retrieval_engine.retrieve_text("test query", max_results=10)

    # Filter by specific article using get_by_article method (line 84)
    filtered_results = context.get_by_article("article_0")

    # Should only return results from article_0
    assert len(filtered_results) > 0
    for result in filtered_results:
        assert result.chunk.article_id == "article_0"
