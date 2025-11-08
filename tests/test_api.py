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


def test_health_check(client, mock_generator):
    """Test health check endpoint."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "services" in data
        assert data["services"]["redis_cache"] is True


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


def test_clear_cache(client, mock_generator):
    """Test cache clearing endpoint."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.post("/api/v1/cache/clear")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Cache cleared" in data["message"]

        # Verify clear_all was called
        mock_generator.cache.clear_all.assert_called_once()


def test_reset_stats(client, mock_generator):
    """Test statistics reset endpoint."""
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        response = client.post("/api/v1/stats/reset")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Statistics reset" in data["message"]

        # Verify reset was called
        mock_generator.llm_client.reset_stats.assert_called_once()
        mock_generator.cache.reset_stats.assert_called_once()


def test_rate_limiting(client, mock_generator):
    """Test rate limiting (basic test)."""
    # Note: This is a simplified test. In production, you'd test actual rate limits
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        # Make multiple requests
        for _ in range(5):
            response = client.post(
                "/api/v1/ask",
                json={"question": "What are symptoms?", "max_results": 5},
            )
            # All should succeed (under rate limit)
            assert response.status_code == 200


def test_cors_headers(client):
    """Test CORS headers are present."""
    response = client.get("/", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 200
    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers


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
    )

    assert citation.article_title == "Breast Cancer"
    assert citation.section == "Symptoms"


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
