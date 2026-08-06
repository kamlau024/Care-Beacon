"""Tests for REST API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

from src.api.main import app, get_answer_generator
from src.generation.models import GeneratedAnswer, Citation


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_answer():
    """Create a mock generated answer."""
    citation = Citation(
        chunk_id="test_001",
        article_title="Breast Cancer",
        section="Symptoms",
        url="https://example.com/breast-cancer",
        paragraph_index=0,
        text_excerpt="Test excerpt about symptoms",
    )

    return GeneratedAnswer(
        query="What are symptoms of breast cancer?",
        answer="Common symptoms include lumps in the breast. [Source: Breast Cancer - Symptoms]",
        citations=[citation],
        context_used=None,
        model="gpt-4o-mini",
        tokens_used={"input": 100, "output": 50, "total": 150},
        cost=0.0002,
        generation_time_ms=500.0,
        disclaimer="This information is for educational purposes only.",
    )


@pytest.fixture
def mock_generator(mock_answer):
    """Create a mock answer generator."""
    generator = Mock()
    generator.generate_answer.return_value = mock_answer
    generator.cache = Mock()
    generator.cache.is_healthy.return_value = True
    generator.cache.get_stats.return_value = {
        "total_queries": 10,
        "cache_hits": 5,
        "cache_misses": 5,
        "hit_rate": 0.5,
        "total_cost_saved": 0.001,
    }
    generator.llm_client = Mock()
    generator.llm_client.get_stats.return_value = {
        "total_calls": 5,
        "total_tokens": 750,
        "total_cost": 0.001,
        "total_input_tokens": 500,
        "total_output_tokens": 250,
    }
    generator.retrieval_engine = Mock()
    generator.retrieval_engine.get_embedding_stats.return_value = {
        "total_cost": 0.0001,
    }
    generator.get_stats.return_value = {
        "llm": generator.llm_client.get_stats(),
        "cache": generator.cache.get_stats(),
        "retrieval": generator.retrieval_engine.get_embedding_stats(),
        "total_cost": 0.0011,
        "total_cost_saved": 0.001,
        "cost_reduction_percent": 47.6,
    }

    return generator


def test_root_endpoint(client):
    """Test root endpoint returns API information."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "Care-Beacon" in data["name"]
    assert data["endpoints"] == {
        "ask": "/api/v1/ask",
        "health": "/api/health",
        "stats": "/api/v1/stats",
    }


def test_health_check_reports_qdrant_reachable(client, mock_generator):
    """A 200 must mean Qdrant answered, since the keepalive relies on it."""
    from unittest.mock import MagicMock, patch

    with patch("src.api.main.create_vector_database") as mock_factory, \
         patch("src.api.main.get_answer_generator", return_value=mock_generator):
        mock_factory.return_value.client.get_collection = MagicMock(return_value=object())
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["services"]["vector_db"] is True
    mock_factory.return_value.client.get_collection.assert_called_once()


def test_health_check_returns_503_when_qdrant_unreachable(client, mock_generator):
    """A dead cluster must fail the check, not be masked as healthy."""
    from unittest.mock import patch

    with patch("src.api.main.create_vector_database", side_effect=Exception("connection refused")), \
         patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["services"]["vector_db"] is False


def test_old_health_path_is_gone(client):
    """The route moved under /api/ so one rewrite covers the whole backend."""
    assert client.get("/health").status_code == 404


def test_ask_question_success(client, mock_generator):
    """Test successful question answering."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        request_data = {
            "question": "What are symptoms of breast cancer?",
            "max_results": 5,
        }

        response = client.post("/api/v1/ask", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["question"] == "What are symptoms of breast cancer?"
        assert "answer" in data
        assert "sources" in data
        assert len(data["sources"]) > 0
        assert data["sources"][0]["article_title"] == "Breast Cancer"
        assert "metadata" in data
        assert "cost" in data["metadata"]


def test_ask_question_with_cancer_type_filter(client, mock_generator):
    """Test question answering with cancer type filter."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        request_data = {
            "question": "What are treatment options?",
            "cancer_type": "Breast Cancer",
            "max_results": 3,
        }

        response = client.post("/api/v1/ask", json=request_data)

        assert response.status_code == 200

        # Verify filter was passed (the mock returns a fixed answer, so check the call)
        mock_generator.generate_answer.assert_called()
        call_kwargs = mock_generator.generate_answer.call_args.kwargs
        assert call_kwargs["filters"] == {"cancer_type": "Breast Cancer"}
        assert call_kwargs["question"] == "What are treatment options?"
        assert call_kwargs["max_results"] == 3


def test_ask_question_with_source_filter_bc_cancer(client, mock_generator):
    """Test question answering with BC Cancer source filter."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        request_data = {
            "question": "What are treatment options?",
            "source": "BC Cancer",
            "max_results": 3,
        }

        response = client.post("/api/v1/ask", json=request_data)

        assert response.status_code == 200

        # Verify source filter was passed
        mock_generator.generate_answer.assert_called()
        call_kwargs = mock_generator.generate_answer.call_args.kwargs
        assert call_kwargs["filters"] == {"source": "BC Cancer"}
        assert call_kwargs["question"] == "What are treatment options?"


def test_ask_question_with_source_filter_canadian_cancer_society(client, mock_generator):
    """Test question answering with Canadian Cancer Society source filter."""
    # Create mock answer with Canadian Cancer Society source
    canadian_citation = Citation(
        chunk_id="test_ccs_001",
        article_title="Clinical Trials",
        section="Types and Phases",
        url="https://cancer.ca/en/treatments/clinical-trials",
        paragraph_index=0,
        text_excerpt="Test excerpt from Canadian Cancer Society",
        similarity_score=0.82,
        source="Canadian Cancer Society",
    )

    canadian_answer = GeneratedAnswer(
        query="What are clinical trials?",
        answer="Clinical trials are research studies. [Source: Clinical Trials - Types and Phases]",
        citations=[canadian_citation],
        context_used=None,
        model="gpt-4o-mini",
        tokens_used={"input": 100, "output": 50, "total": 150},
        cost=0.0002,
        generation_time_ms=500.0,
        disclaimer="This information is for educational purposes only.",
    )

    mock_gen = Mock()
    mock_gen.generate_answer.return_value = canadian_answer
    mock_gen.cache = Mock()
    mock_gen.cache.get_stats.return_value = {
        "cache_hits": 0,
        "cache_misses": 1,
    }

    with patch("src.api.main.get_answer_generator", return_value=mock_gen):
        request_data = {
            "question": "What are clinical trials?",
            "source": "Canadian Cancer Society",
            "max_results": 3,
        }

        response = client.post("/api/v1/ask", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Verify the source in the response
        assert len(data["sources"]) > 0
        assert data["sources"][0]["source"] == "Canadian Cancer Society"
        assert data["sources"][0]["article_title"] == "Clinical Trials"

        # Verify source filter was passed
        mock_gen.generate_answer.assert_called()
        call_kwargs = mock_gen.generate_answer.call_args.kwargs
        assert call_kwargs["filters"] == {"source": "Canadian Cancer Society"}


def test_ask_question_with_mixed_sources(client, mock_generator):
    """Test question answering returns mixed sources when no filter applied."""
    # Create citations from both sources
    bc_citation = Citation(
        chunk_id="test_bc_001",
        article_title="Breast Cancer",
        section="Symptoms",
        url="https://www.bccancer.bc.ca/health-info/types-of-cancer/breast",
        paragraph_index=0,
        text_excerpt="BC Cancer excerpt",
        similarity_score=0.90,
        source="BC Cancer",
    )

    ccs_citation = Citation(
        chunk_id="test_ccs_001",
        article_title="Understanding Cancer",
        section="Overview",
        url="https://cancer.ca/en/cancer-information/cancer-types/breast",
        paragraph_index=0,
        text_excerpt="Canadian Cancer Society excerpt",
        similarity_score=0.85,
        source="Canadian Cancer Society",
    )

    mixed_answer = GeneratedAnswer(
        query="What is cancer?",
        answer="Cancer information from multiple sources. [Source: Breast Cancer] [Source: Understanding Cancer]",
        citations=[bc_citation, ccs_citation],
        context_used=None,
        model="gpt-4o-mini",
        tokens_used={"input": 150, "output": 75, "total": 225},
        cost=0.0003,
        generation_time_ms=600.0,
        disclaimer="This information is for educational purposes only.",
    )

    mock_gen = Mock()
    mock_gen.generate_answer.return_value = mixed_answer
    mock_gen.cache = Mock()
    mock_gen.cache.get_stats.return_value = {
        "cache_hits": 0,
        "cache_misses": 1,
    }

    with patch("src.api.main.get_answer_generator", return_value=mock_gen):
        request_data = {
            "question": "What is cancer?",
            "max_results": 5,
        }

        response = client.post("/api/v1/ask", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Verify we have sources from both organizations
        assert len(data["sources"]) == 2
        sources = [s["source"] for s in data["sources"]]
        assert "BC Cancer" in sources
        assert "Canadian Cancer Society" in sources


def test_ask_question_with_combined_filters(client, mock_generator):
    """Test question answering with both source and cancer_type filters."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        request_data = {
            "question": "What are treatment options for breast cancer?",
            "source": "BC Cancer",
            "cancer_type": "Breast Cancer",
            "max_results": 3,
        }

        response = client.post("/api/v1/ask", json=request_data)

        assert response.status_code == 200

        # Verify both filters were passed
        mock_generator.generate_answer.assert_called()
        call_kwargs = mock_generator.generate_answer.call_args.kwargs
        assert call_kwargs["filters"] == {
            "source": "BC Cancer",
            "cancer_type": "Breast Cancer"
        }


def test_citation_source_attribution(client, mock_generator):
    """Test that citations properly attribute source organization."""
    # Create citations with different sources
    citations = [
        Citation(
            chunk_id="test_001",
            article_title="Test Article 1",
            section="Section 1",
            url="https://example.com/1",
            paragraph_index=0,
            text_excerpt="Excerpt 1",
            similarity_score=0.90,
            source="BC Cancer",
        ),
        Citation(
            chunk_id="test_002",
            article_title="Test Article 2",
            section="Section 2",
            url="https://example.com/2",
            paragraph_index=0,
            text_excerpt="Excerpt 2",
            similarity_score=0.85,
            source="Canadian Cancer Society",
        ),
    ]

    answer = GeneratedAnswer(
        query="Test question",
        answer="Test answer with multiple sources",
        citations=citations,
        context_used=None,
        model="gpt-4o-mini",
        tokens_used={"input": 100, "output": 50, "total": 150},
        cost=0.0002,
        generation_time_ms=500.0,
        disclaimer="This information is for educational purposes only.",
    )

    mock_gen = Mock()
    mock_gen.generate_answer.return_value = answer
    mock_gen.cache = Mock()
    mock_gen.cache.get_stats.return_value = {
        "cache_hits": 0,
        "cache_misses": 1,
    }

    with patch("src.api.main.get_answer_generator", return_value=mock_gen):
        response = client.post("/api/v1/ask", json={"question": "Test question"})

        assert response.status_code == 200
        data = response.json()

        # Verify each citation has correct source
        assert len(data["sources"]) == 2
        assert data["sources"][0]["source"] == "BC Cancer"
        assert data["sources"][1]["source"] == "Canadian Cancer Society"

        # Verify similarity scores are present
        assert data["sources"][0]["similarity_score"] == 0.90
        assert data["sources"][1]["similarity_score"] == 0.85


def test_ask_question_validation_error_short_question(client):
    """Test validation error for too short question."""
    request_data = {
        "question": "Hi",  # Too short (< 3 characters)
        "max_results": 5,
    }

    response = client.post("/api/v1/ask", json=request_data)

    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "ValidationError"


def test_ask_question_validation_error_long_question(client):
    """Test validation error for too long question."""
    request_data = {
        "question": "x" * 501,  # Too long (> 500 characters)
        "max_results": 5,
    }

    response = client.post("/api/v1/ask", json=request_data)

    assert response.status_code == 422


def test_ask_question_validation_error_invalid_max_results(client):
    """Test validation error for invalid max_results."""
    request_data = {
        "question": "What are symptoms?",
        "max_results": 15,  # Too high (> 10)
    }

    response = client.post("/api/v1/ask", json=request_data)

    assert response.status_code == 422


def test_get_stats(client, mock_generator):
    """Test statistics endpoint."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()

        assert "llm" in data
        assert "cache" in data
        assert "retrieval" in data
        assert "total_cost" in data
        assert "total_cost_saved" in data
        assert "cost_reduction_percent" in data


def test_vector_db_stats_cache_hit_short_circuits(client, mock_generator):
    """A cache hit must return the cached payload without touching Qdrant.

    This is the expensive endpoint that otherwise scrolls the entire
    collection -- the cache-hit path existing and actually short-circuiting
    is what keeps repeated Statistics page loads cheap.
    """
    cached_payload = {
        "total_documents": 500,
        "total_chunks": 5000,
        "sources": [
            {"name": "bc-cancer", "articles": 500, "chunks": 5000, "storage_mb": 12.3}
        ],
        "collection_name": "care-beacon-medical",
        "distance_metric": "cosine",
        "vector_size": 1536,
    }
    mock_generator.cache.get_vector_db_stats.return_value = cached_payload

    with patch("src.api.main.create_vector_database") as mock_factory, \
         patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.get("/api/v1/vector-db/stats")

    assert response.status_code == 200
    assert response.json() == cached_payload
    # The cache must short-circuit before Qdrant is ever constructed/touched.
    assert not mock_factory.called


def test_vector_db_stats_cache_miss_computes_and_caches(client, mock_generator):
    """A cache miss must scroll Qdrant to completion, assemble the per-source
    breakdown, and cache the computed result for next time."""
    mock_generator.cache.get_vector_db_stats.return_value = None

    mock_vector_db = MagicMock()
    mock_vector_db.get_stats.return_value = {
        "collection_name": "care-beacon-medical",
        "total_chunks": 3,
        "distance_metric": "cosine",
        "vector_size": 1536,
        "unique_articles_sample": 2,
    }
    mock_vector_db.collection_name = "care-beacon-medical"

    def make_point(source, article_id):
        point = MagicMock()
        point.payload = {"source": source, "article_id": article_id}
        return point

    page1 = [make_point("bc-cancer", "a1"), make_point("bc-cancer", "a1")]
    page2 = [make_point("canadian-cancer-society", "a2")]

    # First page reports a next_offset (more to fetch); second page's
    # next_offset is None, which is what must terminate the pagination loop.
    mock_vector_db.client.scroll.side_effect = [
        (page1, "offset-1"),
        (page2, None),
    ]

    with patch("src.api.main.create_vector_database", return_value=mock_vector_db), \
         patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.get("/api/v1/vector-db/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["total_chunks"] == 3
    assert body["total_documents"] == 2  # unique article_ids: a1, a2

    # Pagination must have stopped as soon as next_offset came back None,
    # not looped forever or under-consumed the mocked pages.
    assert mock_vector_db.client.scroll.call_count == 2

    source_names = {s["name"] for s in body["sources"]}
    assert source_names == {"bc-cancer", "canadian-cancer-society"}

    bc_source = next(s for s in body["sources"] if s["name"] == "bc-cancer")
    assert bc_source["chunks"] == 2
    assert bc_source["articles"] == 1

    # The freshly computed result must be cached so the next load is cheap.
    mock_generator.cache.set_vector_db_stats.assert_called_once()
    cached_arg = mock_generator.cache.set_vector_db_stats.call_args[0][0]
    assert cached_arg["total_chunks"] == 3


def test_vector_db_stats_failure_path_returns_500(client, mock_generator):
    """A Qdrant failure must surface as a clean 500, not crash the app or
    silently return partial/incorrect data."""
    mock_generator.cache.get_vector_db_stats.return_value = None

    with patch("src.api.main.create_vector_database", side_effect=Exception("connection refused")), \
         patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.get("/api/v1/vector-db/stats")

    assert response.status_code == 500
    body = response.json()
    assert "Failed to retrieve vector DB statistics" in body["message"]


def test_clear_cache(client, mock_generator, monkeypatch):
    """Test cache clearing endpoint."""
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.post(
            "/api/v1/cache/clear", headers={"X-API-Key": "secret-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Cache cleared" in data["message"]

        # Verify clear_all was called
        mock_generator.cache.clear_all.assert_called_once()


def test_reset_stats(client, mock_generator, monkeypatch):
    """Test statistics reset endpoint."""
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.post(
            "/api/v1/stats/reset", headers={"X-API-Key": "secret-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Statistics reset" in data["message"]

        # Verify reset was called
        mock_generator.llm_client.reset_stats.assert_called_once()
        mock_generator.cache.reset_stats.assert_called_once()


def test_clear_cache_requires_api_key(client, mock_generator, monkeypatch):
    """An unauthenticated caller must not be able to wipe the cache."""
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    assert client.post("/api/v1/cache/clear").status_code == 403


def test_clear_cache_succeeds_with_api_key(client, mock_generator, monkeypatch):
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    response = client.post("/api/v1/cache/clear", headers={"X-API-Key": "secret-key"})
    assert response.status_code == 200


def test_reset_stats_requires_api_key(client, mock_generator, monkeypatch):
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    assert client.post("/api/v1/stats/reset").status_code == 403


def test_admin_endpoints_disabled_when_no_key_configured(client, mock_generator, monkeypatch):
    """An unset ADMIN_API_KEY must close the endpoints, not open them."""
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "")
    assert client.post("/api/v1/cache/clear").status_code == 503


def test_openapi_docs_available(client):
    """Test that OpenAPI documentation is available."""
    response = client.get("/docs")
    assert response.status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data


def test_question_request_example():
    """Test QuestionRequest model example."""
    from src.api.models import QuestionRequest

    request = QuestionRequest(
        question="What are symptoms of breast cancer?",
        cancer_type="Breast Cancer",
        max_results=5,
    )

    assert request.question == "What are symptoms of breast cancer?"
    assert request.cancer_type == "Breast Cancer"
    assert request.max_results == 5


def test_citation_response_model():
    """Test CitationResponse model."""
    from src.api.models import CitationResponse

    citation = CitationResponse(
        article_title="Breast Cancer",
        section="Symptoms",
        url="https://example.com",
        paragraph_index=0,
        text_excerpt="Test excerpt",
        similarity_score=0.85,
        source="BC Cancer",
    )

    assert citation.article_title == "Breast Cancer"
    assert citation.section == "Symptoms"
    assert citation.similarity_score == 0.85
    assert citation.source == "BC Cancer"


def test_health_response_model():
    """Test HealthResponse model."""
    from src.api.models import HealthResponse
    from datetime import datetime

    health = HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=datetime.now(),
        services={"cache": True, "db": True},
    )

    assert health.status == "healthy"
    assert health.services["cache"] is True


def test_error_response_model():
    """Test ErrorResponse model."""
    from src.api.models import ErrorResponse
    from datetime import datetime

    error = ErrorResponse(
        error="ValidationError",
        message="Invalid input",
        detail="Field: question",
        timestamp=datetime.now(),
    )

    assert error.error == "ValidationError"
    assert error.message == "Invalid input"


def test_filtered_stderr_write_filters_telemetry(capsys):
    """Test FilteredStderr.write() filters telemetry messages (lines 26-27)."""
    from src.api.main import FilteredStderr
    import sys
    from io import StringIO

    # Create a mock stderr to capture output
    mock_stderr = StringIO()
    filtered = FilteredStderr(mock_stderr)

    # Test filtering telemetry message (should be filtered out)
    filtered.write("WARNING: telemetry is enabled")
    # Test normal message (should pass through)
    filtered.write("Normal message")

    # Get the output
    output = mock_stderr.getvalue()

    # Telemetry message should be filtered out
    assert "telemetry" not in output
    # Normal message should be present
    assert "Normal message" in output


def test_filtered_stderr_flush_method(capsys):
    """Test FilteredStderr.flush() method (line 30)."""
    from src.api.main import FilteredStderr
    import sys
    from io import StringIO

    # Create a mock stderr
    mock_stderr = StringIO()
    filtered = FilteredStderr(mock_stderr)

    # Write something and flush
    filtered.write("Test message")
    filtered.flush()  # Line 30

    # Should not raise any exceptions
    output = mock_stderr.getvalue()
    assert "Test message" in output


def test_get_answer_generator_singleton_initialization():
    """Test get_answer_generator() creates singleton on first call (lines 81-83)."""
    from src.api.main import get_answer_generator, _answer_generator
    import src.api.main as main_module

    # Reset the global variable to None to test initialization
    main_module._answer_generator = None

    with patch("src.api.main.AnswerGenerator") as mock_answer_gen_class:
        mock_instance = Mock()
        mock_answer_gen_class.return_value = mock_instance

        # First call should initialize (lines 81-83)
        generator1 = get_answer_generator()

        # Should have called AnswerGenerator() constructor
        mock_answer_gen_class.assert_called_once()
        assert generator1 == mock_instance

        # Second call should return same instance (not create new one)
        generator2 = get_answer_generator()
        assert generator2 == mock_instance
        assert mock_answer_gen_class.call_count == 1  # Still only called once


def test_http_exception_handler(client):
    """Test HTTP exception handler (line 142)."""
    from fastapi import HTTPException

    # Create a route that raises HTTPException
    @app.get("/test_http_exception")
    def test_route():
        raise HTTPException(status_code=404, detail="Resource not found")

    response = client.get("/test_http_exception")

    # Should be handled by http_exception_handler (line 142)
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "HTTPException"
    assert "Resource not found" in data["message"]


def test_general_exception_handler():
    """Test general exception handler (line 155)."""
    from src.api.main import general_exception_handler
    from fastapi import Request
    import asyncio

    # Create a mock request
    mock_request = Mock(spec=Request)

    # Create a test exception
    test_exception = ValueError("Something went wrong")

    # Call the handler directly
    response = asyncio.run(general_exception_handler(mock_request, test_exception))

    # Should return 500 with InternalServerError (line 155)
    assert response.status_code == 500
    data = response.body.decode()
    import json
    data = json.loads(data)
    assert data["error"] == "InternalServerError"
    # Line 159 shows message "An internal server error occurred"
    assert "internal server error" in data["message"].lower()


def test_min_similarity_adjustment_based_on_max_results(client, mock_generator):
    """Test min_similarity adjustment based on max_results (line 256)."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        # Request with min_similarity > 0 should adjust max_results to 50
        response = client.post(
            "/api/v1/ask",
            json={
                "question": "What are symptoms?",
                "max_results": 5,
                "min_similarity": 0.7,  # Line 256: when min_similarity > 0, max_results becomes 50
            },
        )

        assert response.status_code == 200

        # Check that generate_answer was called with adjusted max_results
        call_kwargs = mock_generator.generate_answer.call_args.kwargs
        # Line 256: if min_similarity > 0, max_results is set to 50
        assert call_kwargs["max_results"] == 50
        assert call_kwargs["min_similarity"] == 0.7


def test_ask_endpoint_exception_handling(client):
    """Test ask endpoint exception handling (lines 299-300)."""
    mock_gen = Mock()
    # Make generate_answer raise an exception
    mock_gen.generate_answer.side_effect = RuntimeError("Generation failed")

    with patch("src.api.main.get_answer_generator", return_value=mock_gen):
        response = client.post(
            "/api/v1/ask",
            json={"question": "What are symptoms?", "max_results": 5},
        )

        # Lines 299-300 - exception is caught and HTTPException is raised
        # which is then handled by http_exception_handler (line 142)
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "HTTPException"
        assert "Failed to generate answer" in data["message"]


def test_stats_endpoint_exception_handling(client):
    """Test stats endpoint exception handling (lines 332-333)."""
    mock_gen = Mock()
    # Make get_stats raise an exception
    mock_gen.get_stats.side_effect = RuntimeError("Stats retrieval failed")

    with patch("src.api.main.get_answer_generator", return_value=mock_gen):
        response = client.get("/api/v1/stats")

        # Lines 332-333 - exception is caught and HTTPException is raised
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "HTTPException"
        assert "Failed to retrieve statistics" in data["message"]


def test_clear_cache_exception_handling(client, monkeypatch):
    """Test clear cache endpoint exception handling (lines 358-359)."""
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    mock_gen = Mock()
    # Make cache.clear_all raise an exception
    mock_gen.cache.clear_all.side_effect = RuntimeError("Cache clear failed")

    with patch("src.api.main.get_answer_generator", return_value=mock_gen):
        response = client.post(
            "/api/v1/cache/clear", headers={"X-API-Key": "secret-key"}
        )

        # Lines 358-359 - exception is caught and HTTPException is raised
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "HTTPException"
        assert "Failed to clear cache" in data["message"]


def test_reset_stats_exception_handling(client, monkeypatch):
    """Test reset stats endpoint exception handling (lines 385-386)."""
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    mock_gen = Mock()
    # Make reset_stats raise an exception
    mock_gen.llm_client.reset_stats.side_effect = RuntimeError("Reset failed")

    with patch("src.api.main.get_answer_generator", return_value=mock_gen):
        response = client.post(
            "/api/v1/stats/reset", headers={"X-API-Key": "secret-key"}
        )

        # Lines 385-386 - exception is caught and HTTPException is raised
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "HTTPException"
        assert "Failed to reset statistics" in data["message"]


def test_lifespan_startup_and_shutdown(capsys):
    """Test lifespan context manager handles startup and shutdown (lines 56-81)."""
    from src.api.main import lifespan, app
    import asyncio

    # Mock get_answer_generator to avoid actual initialization
    with patch("src.api.main.get_answer_generator") as mock_get_gen:
        mock_gen = Mock()
        mock_gen.cache = Mock()
        mock_gen.cache.enabled = True
        mock_gen.cache.is_healthy.return_value = True
        mock_get_gen.return_value = mock_gen

        # Run the lifespan context manager
        async def run_lifespan():
            async with lifespan(app):
                # This is where the app would run
                pass

        asyncio.run(run_lifespan())

        # Capture output from lifespan
        captured = capsys.readouterr()

        # Verify startup messages are printed (lines 60-75)
        assert "Care-Beacon Medical RAG API" in captured.out
        assert "Version:" in captured.out
        assert "Answer generator initialized" in captured.out
        assert "Cache healthy: True" in captured.out

        # Verify shutdown messages are printed (lines 79-81)
        assert "Shutting down Care-Beacon API" in captured.out


def test_lifespan_survives_answer_generator_init_failure(capsys):
    """A cold dependency (bad credentials, Qdrant unreachable, ...) at startup
    must not abort the ASGI lifespan. If it did, the app would never come up
    and /api/health -- built specifically to diagnose this -- could never run;
    the keepalive would see an opaque platform error instead of a diagnosable
    503. Startup must log and continue.
    """
    from src.api.main import lifespan, app
    import asyncio

    with patch("src.api.main.get_answer_generator") as mock_get_gen:
        mock_get_gen.side_effect = ValueError("Qdrant API key not configured.")

        async def run_lifespan():
            async with lifespan(app):
                pass

        # Must not raise -- startup completes despite the failure.
        asyncio.run(run_lifespan())

        captured = capsys.readouterr()
        assert "Answer generator pre-initialization failed" in captured.out
        assert "API is ready to accept requests!" in captured.out
        assert "Shutting down Care-Beacon API" in captured.out

