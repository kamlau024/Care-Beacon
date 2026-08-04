"""Tests for vector database."""


def test_create_vector_database_rejects_non_qdrant_provider():
    """A stale VECTOR_DB_PROVIDER=chromadb must fail loudly, not silently."""
    import pytest
    from src.storage.vector_db import create_vector_database

    with pytest.raises(ValueError, match="Only 'qdrant' is supported"):
        create_vector_database(provider="chromadb")
