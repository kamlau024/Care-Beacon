"""Tests for caching functionality (using mocks)."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json
import hashlib

from src.caching.redis_cache import RedisCache
from src.caching.models import CacheConfig, CacheStats
from src.generation.models import GeneratedAnswer, Citation


@pytest.fixture
def cache_config():
    """Create a test cache configuration."""
    return CacheConfig(
        enabled=True,
        host="localhost",
        port=6379,
        db=0,
        ttl_seconds=3600,
        key_prefix="test:",
    )


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = MagicMock()
    client.ping.return_value = True
    client.get.return_value = None
    client.setex.return_value = True
    client.delete.return_value = 1
    client.keys.return_value = []
    return client


@pytest.fixture
def redis_cache(cache_config, mock_redis_client):
    """Create RedisCache with mocked Redis client."""
    with patch('redis.Redis', return_value=mock_redis_client):
        cache = RedisCache(config=cache_config)
        cache.client = mock_redis_client  # Ensure mock is used
        cache.enabled = True
        return cache


def test_cache_config_initialization():
    """Test CacheConfig initialization with defaults."""
    config = CacheConfig()

    assert config.enabled is True
    assert config.host == "localhost"
    assert config.port == 6379
    assert config.db == 0
    assert config.ttl_seconds == 3600
    assert config.key_prefix == "care_beacon:"


def test_cache_config_to_dict():
    """Test CacheConfig to_dict method."""
    config = CacheConfig(
        enabled=True,
        host="localhost",
        port=6379,
        ttl_seconds=7200,
    )

    config_dict = config.to_dict()

    assert config_dict["enabled"] is True
    assert config_dict["host"] == "localhost"
    assert config_dict["port"] == 6379
    assert config_dict["ttl_seconds"] == 7200


def test_cache_stats_initialization():
    """Test CacheStats initialization."""
    stats = CacheStats()

    assert stats.total_queries == 0
    assert stats.cache_hits == 0
    assert stats.cache_misses == 0
    assert stats.hit_rate == 0.0
    assert stats.miss_rate == 0.0


def test_cache_stats_hit_rate():
    """Test cache hit rate calculation."""
    stats = CacheStats()
    stats.total_queries = 10
    stats.cache_hits = 7
    stats.cache_misses = 3

    assert stats.hit_rate == 0.7
    assert stats.miss_rate == 0.3


def test_cache_stats_to_dict():
    """Test CacheStats to_dict method."""
    stats = CacheStats()
    stats.total_queries = 20
    stats.cache_hits = 15
    stats.cache_misses = 5
    stats.total_cost_saved = 0.003

    stats_dict = stats.to_dict()

    assert stats_dict["total_queries"] == 20
    assert stats_dict["cache_hits"] == 15
    assert stats_dict["cache_misses"] == 5
    assert stats_dict["hit_rate"] == 0.75
    assert stats_dict["total_cost_saved"] == 0.003


def test_cache_stats_reset():
    """Test resetting cache statistics."""
    stats = CacheStats()
    stats.total_queries = 20
    stats.cache_hits = 15
    stats.total_cost_saved = 0.003

    stats.reset()

    assert stats.total_queries == 0
    assert stats.cache_hits == 0
    assert stats.total_cost_saved == 0.0


def test_redis_cache_initialization(redis_cache):
    """Test RedisCache initialization."""
    assert redis_cache is not None
    assert redis_cache.config is not None
    assert redis_cache.stats is not None
    assert redis_cache.enabled is True


def test_cache_key_generation(redis_cache):
    """Test cache key generation is consistent."""
    question1 = "What are symptoms of breast cancer?"
    filters1 = {"cancer_type": "Breast Cancer"}

    key1 = redis_cache._generate_cache_key(question1, filters1, 5)
    key2 = redis_cache._generate_cache_key(question1, filters1, 5)

    # Same inputs should produce same key
    assert key1 == key2

    # Different inputs should produce different keys
    key3 = redis_cache._generate_cache_key("Different question", filters1, 5)
    assert key1 != key3


def test_cache_key_normalization(redis_cache):
    """Test that cache keys normalize question text."""
    # These should produce the same key (case-insensitive, whitespace normalized)
    key1 = redis_cache._generate_cache_key("What are symptoms?", None, 5)
    key2 = redis_cache._generate_cache_key("what are symptoms?", None, 5)

    assert key1 == key2


def test_cache_get_miss(redis_cache, mock_redis_client):
    """Test cache get with cache miss."""
    mock_redis_client.get.return_value = None

    result = redis_cache.get("What are symptoms?")

    assert result is None
    assert redis_cache.stats.total_queries == 1
    assert redis_cache.stats.cache_misses == 1
    assert redis_cache.stats.cache_hits == 0


def test_cache_get_hit(redis_cache, mock_redis_client):
    """Test cache get with cache hit."""
    # Create a mock cached answer
    cached_data = {
        "query": "What are symptoms?",
        "answer": "Symptoms include...",
        "citations": [
            {
                "chunk_id": "test_001",
                "article_title": "Breast Cancer",
                "section": "Symptoms",
                "url": "https://example.com",
                "paragraph_index": 0,
                "text_excerpt": "Test excerpt",
            }
        ],
        "model": "gpt-4o-mini",
        "tokens_used": {"input": 100, "output": 50, "total": 150},
        "cost": 0.0002,
        "generation_time_ms": 500.0,
        "disclaimer": "Test disclaimer",
    }

    mock_redis_client.get.return_value = json.dumps(cached_data)

    result = redis_cache.get("What are symptoms?")

    assert result is not None
    assert isinstance(result, GeneratedAnswer)
    assert result.query == "What are symptoms?"
    assert result.answer == "Symptoms include..."
    assert len(result.citations) == 1
    assert redis_cache.stats.cache_hits == 1
    assert redis_cache.stats.cache_misses == 0


def test_cache_set(redis_cache, mock_redis_client):
    """Test storing answer in cache."""
    # Create a test answer
    citation = Citation(
        chunk_id="test_001",
        article_title="Breast Cancer",
        section="Symptoms",
        url="https://example.com",
        paragraph_index=0,
        text_excerpt="Test excerpt",
    )

    answer = GeneratedAnswer(
        query="What are symptoms?",
        answer="Symptoms include...",
        citations=[citation],
        context_used=None,
        model="gpt-4o-mini",
        tokens_used={"input": 100, "output": 50, "total": 150},
        cost=0.0002,
        generation_time_ms=500.0,
        disclaimer="Test disclaimer",
    )

    redis_cache.set("What are symptoms?", answer)

    # Verify setex was called
    assert mock_redis_client.setex.called
    call_args = mock_redis_client.setex.call_args

    # Check TTL was set
    assert call_args[0][1] == redis_cache.config.ttl_seconds


def test_cache_invalidate(redis_cache, mock_redis_client):
    """Test cache invalidation."""
    redis_cache.invalidate("What are symptoms?")

    assert mock_redis_client.delete.called


def test_cache_clear_all(redis_cache, mock_redis_client):
    """Test clearing all cached entries."""
    mock_redis_client.keys.return_value = ["test:answer:key1", "test:answer:key2"]

    redis_cache.clear_all()

    assert mock_redis_client.keys.called
    assert mock_redis_client.delete.called


def test_cache_get_stats(redis_cache):
    """Test getting cache statistics."""
    redis_cache.stats.total_queries = 10
    redis_cache.stats.cache_hits = 7
    redis_cache.stats.cache_misses = 3

    stats = redis_cache.get_stats()

    assert stats["total_queries"] == 10
    assert stats["cache_hits"] == 7
    assert stats["cache_misses"] == 3
    assert stats["hit_rate"] == 0.7
    assert stats["enabled"] is True


def test_cache_disabled():
    """Test cache behavior when disabled."""
    config = CacheConfig(enabled=False)

    with patch('redis.Redis') as mock_redis:
        cache = RedisCache(config=config)

        # Should not initialize Redis client
        assert cache.enabled is False
        assert cache.client is None

        # Get should return None immediately
        result = cache.get("Test question")
        assert result is None


def test_cache_connection_failure():
    """Test cache behavior when Redis connection fails."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    config = CacheConfig(enabled=True)

    with patch('redis.Redis') as mock_redis:
        # Create a mock client that raises on ping
        mock_client = MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("Connection failed")
        mock_redis.return_value = mock_client

        # The __init__ should catch the exception and disable cache
        cache = RedisCache(config=config)

        # Should disable cache on connection failure
        assert cache.enabled is False


def test_cache_serialization_deserialization(redis_cache):
    """Test that serialization and deserialization are inverse operations."""
    citation = Citation(
        chunk_id="test_001",
        article_title="Breast Cancer",
        section="Symptoms",
        url="https://example.com",
        paragraph_index=0,
        text_excerpt="Test excerpt",
    )

    original_answer = GeneratedAnswer(
        query="What are symptoms?",
        answer="Symptoms include...",
        citations=[citation],
        context_used=None,
        model="gpt-4o-mini",
        tokens_used={"input": 100, "output": 50, "total": 150},
        cost=0.0002,
        generation_time_ms=500.0,
        disclaimer="Test disclaimer",
    )

    # Serialize
    serialized = redis_cache._serialize_answer(original_answer)

    # Deserialize
    deserialized = redis_cache._deserialize_answer(serialized)

    # Verify
    assert deserialized.query == original_answer.query
    assert deserialized.answer == original_answer.answer
    assert len(deserialized.citations) == len(original_answer.citations)
    assert deserialized.model == original_answer.model
    assert deserialized.cost == original_answer.cost


def test_cache_is_healthy(redis_cache, mock_redis_client):
    """Test cache health check."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    # Should be healthy
    mock_redis_client.ping.return_value = True
    assert redis_cache.is_healthy() is True

    # Simulate failure
    mock_redis_client.ping.side_effect = RedisConnectionError("Connection lost")
    assert redis_cache.is_healthy() is False
