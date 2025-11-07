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
    assert config.get("retrieval.min_similarity") == 0.5


def test_get_config_singleton():
    """Test that get_config returns same instance."""
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2
