"""Tests for vector database."""

from unittest.mock import MagicMock, patch


def test_create_vector_database_rejects_non_qdrant_provider():
    """A stale VECTOR_DB_PROVIDER=chromadb must fail loudly, not silently."""
    import pytest
    from src.storage.vector_db import create_vector_database

    with pytest.raises(ValueError, match="Only 'qdrant' is supported"):
        create_vector_database(provider="chromadb")


def test_create_if_missing_false_never_creates_collection():
    """create_if_missing=False must observe the collection, never create it.

    A health check (or any other read-only caller) must not resurrect a
    reclaimed/missing collection as an empty one and mask the failure.
    """
    from src.storage.qdrant_db import QdrantVectorDatabase

    with patch("src.storage.qdrant_db.QdrantClient") as mock_client_cls:
        mock_client = MagicMock()
        # Simulate a missing collection: any read against it fails.
        mock_client.get_collection.side_effect = Exception("Not found: doesn't exist!")
        mock_client_cls.return_value = mock_client

        db = QdrantVectorDatabase(
            url="https://example.qdrant.io",
            api_key="test-key",
            create_if_missing=False,
        )

        # Construction itself must not have attempted to create anything.
        assert not mock_client.create_collection.called
        assert not mock_client.create_payload_index.called

        # Observing the (missing) collection must surface the failure, not
        # silently succeed against a collection nobody created.
        import pytest
        with pytest.raises(Exception):
            db.client.get_collection(collection_name=db.collection_name)

        assert not mock_client.create_collection.called


def test_create_if_missing_true_creates_missing_collection():
    """The default (create_if_missing=True) must still auto-create for
    normal query/ingestion callers -- only the health check opts out."""
    from src.storage.qdrant_db import QdrantVectorDatabase

    with patch("src.storage.qdrant_db.QdrantClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("Not found: doesn't exist!")
        mock_client_cls.return_value = mock_client

        QdrantVectorDatabase(url="https://example.qdrant.io", api_key="test-key")

        assert mock_client.create_collection.called
