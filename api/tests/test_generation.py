"""Tests for answer generation (using mocks)."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.generation.answer_generator import AnswerGenerator
from src.generation.llm_client import LLMClient
from src.generation.models import GeneratedAnswer, Citation, GenerationConfig
from src.retrieval.models import RetrievedContext, Query
from src.storage.models import Chunk, RetrievalResult


@pytest.fixture
def mock_retrieval_engine():
    """Create a mock retrieval engine."""
    engine = Mock()

    # Create mock chunks
    mock_chunk = Chunk(
        chunk_id="test_chunk_001",
        text="Breast cancer symptoms include lumps, changes in breast shape, and skin dimpling.",
        article_id="breast-cancer",
        article_title="Breast Cancer",
        url="https://example.com/breast-cancer",
        breadcrumbs=["Cancer", "Breast Cancer"],
        cancer_type="Breast Cancer",
        section="Symptoms",
        paragraph_index=0,
        total_paragraphs=10,
        embedding=[0.1] * 1536,
    )

    result = RetrievalResult(
        chunk=mock_chunk,
        similarity_score=0.85,
        rank=1,
    )

    query = Query(text="What are symptoms of breast cancer?", max_results=5)

    context = RetrievedContext(
        query=query,
        results=[result],
        total_chunks=1,
        retrieval_time_ms=100.0,
    )

    engine.retrieve_text.return_value = context
    engine.get_embedding_stats.return_value = {"total_cost": 0.0001}

    return engine


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = Mock()

    # Mock response
    mock_response = {
        "answer": "Breast cancer symptoms include lumps in the breast, changes in breast shape or size, and skin changes. [Source: Breast Cancer - Symptoms]",
        "tokens_used": {
            "input": 150,
            "output": 50,
            "total": 200,
        },
        "cost": 0.0003,
        "model": "gpt-4o-mini",
        "generation_time_ms": 500.0,
    }

    client.generate.return_value = mock_response
    client.get_stats.return_value = {
        "total_calls": 1,
        "total_input_tokens": 150,
        "total_output_tokens": 50,
        "total_cost": 0.0003,
    }

    return client


@pytest.fixture
def answer_generator(mock_retrieval_engine, mock_llm_client):
    """Create answer generator with mocked dependencies."""
    config = GenerationConfig(
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
        max_context_chunks=5,
        require_citations=True,
        include_disclaimer=True,
    )

    return AnswerGenerator(
        retrieval_engine=mock_retrieval_engine,
        llm_client=mock_llm_client,
        config=config,
    )


def test_answer_generator_initialization(answer_generator):
    """Test that answer generator initializes correctly."""
    assert answer_generator is not None
    assert answer_generator.retrieval_engine is not None
    assert answer_generator.llm_client is not None
    assert answer_generator.config is not None
    assert answer_generator.prompts is not None


def test_answer_generator_initialization_with_default_config(mock_retrieval_engine, mock_llm_client):
    """Test that answer generator initializes with default config loaded from file."""
    # Don't provide a config - should load from get_config()
    generator = AnswerGenerator(
        retrieval_engine=mock_retrieval_engine,
        llm_client=mock_llm_client,
        # No config parameter - will trigger _load_config() (lines 56-61)
    )

    # Verify it initialized with a config loaded from file
    assert generator.config is not None
    assert isinstance(generator.config, GenerationConfig)
    assert generator.config.model is not None
    assert generator.config.max_tokens > 0
    assert generator.config.temperature >= 0


def test_generate_answer_basic(answer_generator):
    """Test basic answer generation."""
    question = "What are symptoms of breast cancer?"

    answer = answer_generator.generate_answer(question)

    assert answer is not None
    assert isinstance(answer, GeneratedAnswer)
    assert answer.query == question
    assert len(answer.answer) > 0
    assert len(answer.citations) > 0
    assert answer.cost > 0
    assert answer.model == "gpt-4o-mini"


def test_generate_answer_with_citations(answer_generator):
    """Test that generated answers include citations."""
    question = "What are symptoms of breast cancer?"

    answer = answer_generator.generate_answer(question)

    assert len(answer.citations) > 0

    # Check citation structure
    citation = answer.citations[0]
    assert citation.chunk_id is not None
    assert citation.article_title is not None
    assert citation.section is not None
    assert citation.url is not None


def test_generate_answer_with_disclaimer(answer_generator):
    """Test that answers include disclaimer when configured."""
    question = "What are symptoms of breast cancer?"

    answer = answer_generator.generate_answer(question)

    assert answer.disclaimer is not None
    assert len(answer.disclaimer) > 0


def test_generate_answer_for_cancer_type(answer_generator):
    """Test generating answer filtered by cancer type."""
    question = "What are treatment options?"
    cancer_type = "Breast Cancer"

    answer = answer_generator.generate_answer_for_cancer_type(question, cancer_type)

    assert answer is not None
    assert answer.query == question


def test_get_formatted_answer(answer_generator):
    """Test getting formatted answer with citations."""
    question = "What are symptoms?"

    answer = answer_generator.generate_answer(question)
    formatted = answer.get_formatted_answer(include_disclaimer=True)

    assert isinstance(formatted, str)
    assert len(formatted) > len(answer.answer)  # Should include citations and disclaimer
    assert "Sources:" in formatted or answer.answer in formatted


def test_get_stats(answer_generator):
    """Test getting generation statistics."""
    # Generate an answer
    answer_generator.generate_answer("What are symptoms?")

    # Get stats
    stats = answer_generator.get_stats()

    assert "llm" in stats
    assert "retrieval" in stats
    assert "total_cost" in stats
    assert stats["total_cost"] > 0


def test_citation_to_reference():
    """Test citation formatting as reference."""
    citation = Citation(
        chunk_id="test_001",
        article_title="Breast Cancer",
        section="Symptoms",
        url="https://example.com",
        paragraph_index=0,
        text_excerpt="Test text",
    )

    reference = citation.to_reference()

    assert "Breast Cancer" in reference
    assert "Symptoms" in reference
    assert "paragraph 1" in reference


def test_citation_to_markdown_link():
    """Test citation formatting as markdown link."""
    citation = Citation(
        chunk_id="test_001",
        article_title="Breast Cancer",
        section="Symptoms",
        url="https://example.com",
        paragraph_index=0,
        text_excerpt="Test text",
    )

    markdown = citation.to_markdown_link()

    assert "[Breast Cancer - Symptoms]" in markdown
    assert "(https://example.com)" in markdown


def test_generated_answer_to_dict(answer_generator):
    """Test converting generated answer to dictionary."""
    answer = answer_generator.generate_answer("What are symptoms?")

    result_dict = answer.to_dict()

    assert isinstance(result_dict, dict)
    assert "query" in result_dict
    assert "answer" in result_dict
    assert "citations" in result_dict
    assert "model" in result_dict
    assert "tokens_used" in result_dict
    assert "cost" in result_dict


def test_generation_config_to_dict():
    """Test GenerationConfig to_dict method."""
    config = GenerationConfig(
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
        max_context_chunks=5,
        require_citations=True,
        include_disclaimer=True,
    )

    config_dict = config.to_dict()

    assert config_dict["model"] == "gpt-4o-mini"
    assert config_dict["max_tokens"] == 1000
    assert config_dict["temperature"] == 0.1
    assert config_dict["max_context_chunks"] == 5
    assert config_dict["require_citations"] is True


def test_no_context_found(answer_generator, mock_retrieval_engine):
    """Test handling when no context is found."""
    # Mock empty results
    empty_context = RetrievedContext(
        query=Query(text="test", max_results=5),
        results=[],
        total_chunks=0,
        retrieval_time_ms=50.0,
    )
    mock_retrieval_engine.retrieve_text.return_value = empty_context

    answer = answer_generator.generate_answer("Unknown topic")

    assert answer is not None
    assert len(answer.citations) == 0
    assert answer.cost == 0.0  # No LLM call made


def test_load_prompts_file_missing_raises(mock_retrieval_engine, mock_llm_client, tmp_path):
    """Test prompt loading when prompts.yaml doesn't exist.

    A missing prompts file must raise rather than silently fall back to a
    stub prompt: the stub has no citation instruction and no medical
    disclaimer, which is unacceptable for a patient-facing medical system.
    """
    config = GenerationConfig(
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
    )

    missing_prompts_path = tmp_path / "does_not_exist.yaml"

    with pytest.raises(FileNotFoundError, match="Prompt templates missing"):
        AnswerGenerator(
            retrieval_engine=mock_retrieval_engine,
            llm_client=mock_llm_client,
            config=config,
            prompts_path=missing_prompts_path,
        )


def test_load_prompts_default_path_anchored_to_module(mock_retrieval_engine, mock_llm_client):
    """The default prompts path must be anchored to the package location
    (api/config/prompts.yaml), not the process working directory, so it
    resolves correctly regardless of CWD."""
    config = GenerationConfig(
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
    )

    generator = AnswerGenerator(
        retrieval_engine=mock_retrieval_engine,
        llm_client=mock_llm_client,
        config=config,
    )

    assert "system_prompt" in generator.prompts
    assert "qa_prompt_template" in generator.prompts


def test_cache_hit_statistics_tracking(mock_retrieval_engine, mock_llm_client):
    """Test that cache hits properly track cost savings."""
    config = GenerationConfig(
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
    )

    # Create mock cache with a cached answer
    mock_cache = Mock()
    cached_answer = GeneratedAnswer(
        query="What are symptoms?",
        answer="Cached answer about symptoms.",
        citations=[],
        context_used=RetrievedContext(
            query=Query(text="test", max_results=5),
            results=[],
            total_chunks=0,
            retrieval_time_ms=0.0,
        ),
        model="gpt-4o-mini",
        tokens_used={"input": 100, "output": 50, "total": 150},
        cost=0.0005,  # This is the cost we saved
        generation_time_ms=500.0,
    )

    mock_cache.get.return_value = cached_answer
    mock_cache.stats = Mock()
    mock_cache.stats.total_cost_saved = 0.0
    mock_cache.stats.total_time_saved_ms = 0.0
    mock_cache.get_stats.return_value = {
        "cache_hits": 1,
        "cache_misses": 0,
        "total_cost_saved": 0.0005,
    }

    generator = AnswerGenerator(
        retrieval_engine=mock_retrieval_engine,
        llm_client=mock_llm_client,
        config=config,
        cache=mock_cache,
    )

    # Generate answer (should hit cache)
    answer = generator.generate_answer("What are symptoms?")

    # Verify cache was checked
    mock_cache.get.assert_called_once()

    # Verify we got the cached answer back
    assert answer.answer == "Cached answer about symptoms."

    # Verify cost savings were tracked (lines 181-182)
    assert mock_cache.stats.total_cost_saved >= 0.0005
    assert mock_cache.stats.total_time_saved_ms >= 500


def test_generate_answer_without_citations_requirement(mock_retrieval_engine, mock_llm_client):
    """Test answer generation with require_citations=False."""
    config = GenerationConfig(
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
        max_context_chunks=5,
        require_citations=False,  # Citations not required
        include_disclaimer=True,
    )

    generator = AnswerGenerator(
        retrieval_engine=mock_retrieval_engine,
        llm_client=mock_llm_client,
        config=config,
    )

    question = "What are symptoms of breast cancer?"
    answer = generator.generate_answer(question)

    # Verify LLM was called
    mock_llm_client.generate.assert_called_once()

    # Get the call arguments
    call_kwargs = mock_llm_client.generate.call_args.kwargs

    # When require_citations is False, should use basic qa_prompt_template (line 227)
    # The user_prompt should be formatted with the basic template
    assert "user_prompt" in call_kwargs
    assert question in call_kwargs["user_prompt"]

    # Answer should still be generated
    assert answer is not None
    assert len(answer.answer) > 0


def test_get_config_dict_method(answer_generator):
    """Test the get_config_dict method (line 317)."""
    config_dict = answer_generator.get_config_dict()

    # Verify it returns a dictionary with expected keys
    assert isinstance(config_dict, dict)
    assert "model" in config_dict
    assert "max_tokens" in config_dict
    assert "temperature" in config_dict
    assert "max_context_chunks" in config_dict
    assert "require_citations" in config_dict
    assert "include_disclaimer" in config_dict

    # Verify values match the config
    assert config_dict["model"] == answer_generator.config.model
    assert config_dict["max_tokens"] == answer_generator.config.max_tokens
    assert config_dict["temperature"] == answer_generator.config.temperature


def test_cache_miss_then_store(mock_retrieval_engine, mock_llm_client):
    """Test cache miss scenario with subsequent storage."""
    config = GenerationConfig(
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
    )

    # Create mock cache that returns None (cache miss)
    mock_cache = Mock()
    mock_cache.get.return_value = None
    mock_cache.get_stats.return_value = {
        "cache_hits": 0,
        "cache_misses": 1,
        "total_cost_saved": 0.0,
    }

    generator = AnswerGenerator(
        retrieval_engine=mock_retrieval_engine,
        llm_client=mock_llm_client,
        config=config,
        cache=mock_cache,
    )

    # Generate answer (cache miss)
    question = "What are symptoms?"
    answer = generator.generate_answer(question)

    # Verify cache.get was called
    mock_cache.get.assert_called_once()

    # Verify cache.set was called to store the result
    mock_cache.set.assert_called_once()

    # Verify the answer was generated
    assert answer is not None
    assert len(answer.answer) > 0


def test_get_stats_with_cost_calculation(answer_generator):
    """Test get_stats with comprehensive cost calculations."""
    # Generate an answer to accumulate stats
    answer_generator.generate_answer("What are symptoms?")

    # Get stats
    stats = answer_generator.get_stats()

    # Verify all required keys are present
    assert "llm" in stats
    assert "retrieval" in stats
    assert "cache" in stats
    assert "total_cost" in stats
    assert "total_cost_saved" in stats
    assert "total_cost_without_cache" in stats
    assert "cost_reduction_percent" in stats

    # Verify calculations are reasonable
    assert stats["total_cost"] >= 0
    assert stats["total_cost_saved"] >= 0
    assert stats["cost_reduction_percent"] >= 0
    assert stats["cost_reduction_percent"] <= 100
