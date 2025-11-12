"""Tests for configuration loader."""

import pytest
from src.config_loader import Config, get_config


def test_config_loads_successfully(config_path):
    """Test that configuration loads without errors."""
    config = Config(str(config_path))
    assert config is not None
    assert config.config is not None


def test_config_get_method(config_path):
    """Test the get method with dot notation."""
    config = Config(str(config_path))

    # Test simple key
    assert config.get("data.articles_path") == "scraped_data/articles"

    # Test nested key
    assert config.get("embeddings.model") == "text-embedding-3-small"

    # Test default value
    assert config.get("nonexistent.key", "default") == "default"


def test_config_embedding_settings(config_path):
    """Test embedding configuration values."""
    config = Config(str(config_path))

    assert config.get("embeddings.provider") == "openai"
    assert config.get("embeddings.dimensions") == 1536
    assert config.get("embeddings.batch_size") == 100


def test_config_vector_db_settings(config_path):
    """Test vector database configuration."""
    config = Config(str(config_path))

    assert config.get("vector_db.collection_name") == "care-beacon-medical"
    assert config.get("vector_db.distance_metric") == "cosine"


def test_config_retrieval_settings(config_path):
    """Test retrieval configuration."""
    config = Config(str(config_path))

    assert config.get("retrieval.top_k") == 10
    assert config.get("retrieval.min_similarity_threshold") == 0.0


def test_get_config_singleton():
    """Test that get_config returns same instance."""
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2


def test_config_file_not_found():
    """Test that Config raises FileNotFoundError when file doesn't exist (line 26)."""
    with pytest.raises(FileNotFoundError) as exc_info:
        Config("nonexistent_config.yaml")

    assert "Configuration file not found" in str(exc_info.value)


def test_config_env_override_anthropic_api_key(config_path, monkeypatch):
    """Test ANTHROPIC_API_KEY environment variable override (line 41)."""
    # Set ANTHROPIC_API_KEY environment variable
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key-123")

    config = Config(str(config_path))

    # Verify the API key was set from environment
    api_keys = config.get("api_keys", {})
    assert "anthropic" in api_keys
    assert api_keys["anthropic"] == "test-anthropic-key-123"


def test_config_env_override_redis_password(config_path, monkeypatch):
    """Test REDIS_PASSWORD environment variable override (line 49)."""
    # Set REDIS_PASSWORD environment variable
    monkeypatch.setenv("REDIS_PASSWORD", "test-redis-password-456")

    config = Config(str(config_path))

    # Verify the Redis password was set from environment
    redis_password = config.get("cache.password")
    assert redis_password == "test-redis-password-456"


def test_config_env_override_log_level(config_path, monkeypatch):
    """Test LOG_LEVEL environment variable override (line 53)."""
    # Set LOG_LEVEL environment variable
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    config = Config(str(config_path))

    # Verify the log level was set from environment
    log_level = config.get("logging.level")
    assert log_level == "DEBUG"


def test_config_get_api_key_not_found(config_path):
    """Test get_api_key raises ValueError when provider not found (line 90)."""
    config = Config(str(config_path))

    # Try to get API key for non-existent provider
    with pytest.raises(ValueError) as exc_info:
        config.get_api_key("nonexistent_provider")

    assert "API key for 'nonexistent_provider' not found" in str(exc_info.value)


def test_config_get_api_key_openai(config_path, monkeypatch):
    """Test get_api_key for OpenAI provider."""
    # Set OPENAI_API_KEY environment variable
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-789")

    config = Config(str(config_path))

    # Get OpenAI API key
    api_key = config.get_api_key("openai")
    assert api_key == "test-openai-key-789"
