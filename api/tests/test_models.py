"""Tests for storage models."""

import pytest
from datetime import datetime

from src.storage.models import Chunk, RetrievalResult, QueryResponse


@pytest.fixture
def sample_chunk():
    """Create a sample chunk for testing."""
    return Chunk(
        chunk_id="test-chunk-001",
        text="Breast cancer symptoms include lumps and changes in breast shape.",
        article_id="breast-cancer",
        article_title="Breast Cancer Overview",
        url="https://example.com/breast-cancer",
        breadcrumbs=["Health", "Cancer", "Breast Cancer"],
        cancer_type="Breast Cancer",
        source="BC Cancer",
        date_scraped=datetime.now(),
        section="Symptoms",
        paragraph_index=0,
        total_paragraphs=10,
        embedding=[0.1] * 1536,
    )


@pytest.fixture
def sample_retrieval_result(sample_chunk):
    """Create a sample retrieval result."""
    return RetrievalResult(
        chunk=sample_chunk,
        similarity_score=0.85,
        rank=1,
    )


def test_query_response_format_citations_with_sources(sample_retrieval_result):
    """Test QueryResponse.format_citations() with sources (lines 176-186)."""
    # Create a query response with sources
    response = QueryResponse(
        query="What are symptoms of breast cancer?",
        answer="Breast cancer symptoms include lumps and changes in breast shape.",
        sources=[sample_retrieval_result],
        processing_time=0.5,
    )

    # Format citations (lines 176-186)
    formatted = response.format_citations()

    # Verify formatted output includes answer
    assert "Breast cancer symptoms" in formatted

    # Verify it includes references section (line 179)
    assert "**References:**" in formatted

    # Verify it includes citation details (lines 182-184)
    assert "[1]" in formatted
    assert "Breast Cancer Overview" in formatted
    assert "BC Cancer" in formatted
    assert "Section: Symptoms" in formatted
    assert "Paragraph 0" in formatted
    assert "https://example.com/breast-cancer" in formatted


def test_query_response_format_citations_without_sources():
    """Test QueryResponse.format_citations() without sources."""
    # Create a query response without sources
    response = QueryResponse(
        query="What is cancer?",
        answer="Cancer is a disease where cells grow abnormally.",
        sources=[],
        processing_time=0.3,
    )

    # Format citations - should just return answer without references
    formatted = response.format_citations()

    # Should include answer (line 176)
    assert "Cancer is a disease" in formatted

    # Should NOT include references section (line 178 - sources is empty)
    assert "**References:**" not in formatted


def test_query_response_format_citations_with_multiple_sources(sample_chunk):
    """Test QueryResponse.format_citations() with multiple sources."""
    # Create multiple retrieval results
    result1 = RetrievalResult(
        chunk=sample_chunk,
        similarity_score=0.90,
        rank=1,
    )

    chunk2 = Chunk(
        chunk_id="test-chunk-002",
        text="Treatment options include surgery and chemotherapy.",
        article_id="breast-cancer-treatment",
        article_title="Breast Cancer Treatment",
        url="https://example.com/treatment",
        breadcrumbs=["Health", "Cancer", "Treatment"],
        cancer_type="Breast Cancer",
        source="Canadian Cancer Society",
        date_scraped=datetime.now(),
        section="Treatment Options",
        paragraph_index=5,
        total_paragraphs=20,
        embedding=[0.2] * 1536,
    )

    result2 = RetrievalResult(
        chunk=chunk2,
        similarity_score=0.85,
        rank=2,
    )

    response = QueryResponse(
        query="What are breast cancer symptoms and treatments?",
        answer="Symptoms include lumps. Treatments include surgery and chemotherapy.",
        sources=[result1, result2],
        processing_time=0.7,
    )

    # Format citations with multiple sources (lines 180-184 loop)
    formatted = response.format_citations()

    # Verify both citations are included
    assert "[1]" in formatted
    assert "[2]" in formatted
    assert "Breast Cancer Overview" in formatted
    assert "Breast Cancer Treatment" in formatted
    assert "BC Cancer" in formatted
    assert "Canadian Cancer Society" in formatted
    assert "Section: Symptoms" in formatted
    assert "Section: Treatment Options" in formatted
    assert "Paragraph 0" in formatted
    assert "Paragraph 5" in formatted


def test_retrieval_result_creation(sample_chunk):
    """Test RetrievalResult creation."""
    result = RetrievalResult(
        chunk=sample_chunk,
        similarity_score=0.75,
        rank=3,
    )

    assert result.chunk == sample_chunk
    assert result.similarity_score == 0.75
    assert result.rank == 3


def test_query_response_with_cache_flag():
    """Test QueryResponse with cached flag."""
    response = QueryResponse(
        query="Test query",
        answer="Test answer",
        sources=[],
        processing_time=0.05,
        cached=True,
    )

    assert response.cached is True
    assert response.processing_time == 0.05


def test_query_response_with_cost_info():
    """Test QueryResponse with cost information."""
    response = QueryResponse(
        query="Test query",
        answer="Test answer",
        sources=[],
        processing_time=0.5,
        cost={"llm": 0.001, "embeddings": 0.0001},
    )

    assert response.cost is not None
    assert response.cost["llm"] == 0.001
    assert response.cost["embeddings"] == 0.0001
