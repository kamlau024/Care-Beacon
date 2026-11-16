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
    """Ingestion opts in to creating a missing collection."""
    from src.storage.qdrant_db import QdrantVectorDatabase

    with patch("src.storage.qdrant_db.QdrantClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("Not found: doesn't exist!")
        mock_client_cls.return_value = mock_client

        QdrantVectorDatabase(url="https://example.qdrant.io", api_key="test-key", create_if_missing=True)

        assert mock_client.create_collection.called
        assert mock_client.create_collection.call_args.kwargs["quantization_config"] is None


def test_default_never_creates_collection():
    """Query paths use the default, which must not turn a missing alias into
    an empty collection of the same name."""
    from src.storage.qdrant_db import QdrantVectorDatabase

    with patch("src.storage.qdrant_db.QdrantClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("Not found: doesn't exist!")
        mock_client_cls.return_value = mock_client

        QdrantVectorDatabase(url="https://example.qdrant.io", api_key="test-key")

        assert not mock_client.create_collection.called


def test_quantize_creates_int8_collection():
    from qdrant_client.models import ScalarType
    from src.storage.qdrant_db import QdrantVectorDatabase

    with patch("src.storage.qdrant_db.QdrantClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("Not found: doesn't exist!")
        mock_client_cls.return_value = mock_client

        QdrantVectorDatabase(
            url="https://example.qdrant.io", api_key="test-key", create_if_missing=True, quantize=True
        )

        kwargs = mock_client.create_collection.call_args.kwargs
        assert kwargs["quantization_config"].scalar.type == ScalarType.INT8
        assert kwargs["vectors_config"].on_disk is True


def test_reset_refuses_an_alias():
    """Deleting through an alias would delete the collection the app serves."""
    import pytest
    from src.storage.qdrant_db import QdrantVectorDatabase

    with patch("src.storage.qdrant_db.QdrantClient") as mock_client_cls:
        mock_client = MagicMock()
        alias = MagicMock(alias_name="care-beacon-live", collection_name="care-beacon-medical")
        mock_client.get_aliases.return_value = MagicMock(aliases=[alias])
        mock_client_cls.return_value = mock_client

        db = QdrantVectorDatabase(
            url="https://example.qdrant.io", api_key="test-key", collection_name="care-beacon-live"
        )
        with pytest.raises(RuntimeError, match="is an alias"):
            db.reset()

        assert not mock_client.delete_collection.called


def test_list_filter_value_uses_match_any():
    from qdrant_client.models import MatchAny
    from src.storage.qdrant_db import build_qdrant_filter

    f = build_qdrant_filter({"source": ["BC Cancer", "Cleveland Clinic"]})
    assert isinstance(f.must[0].match, MatchAny)
    assert f.must[0].match.any == ["BC Cancer", "Cleveland Clinic"]


def test_scalar_filter_value_still_uses_match_value():
    from qdrant_client.models import MatchValue
    from src.storage.qdrant_db import build_qdrant_filter

    f = build_qdrant_filter({"source": "BC Cancer"})
    assert isinstance(f.must[0].match, MatchValue)


def test_no_filter_returns_none():
    from src.storage.qdrant_db import build_qdrant_filter

    assert build_qdrant_filter(None) is None
    assert build_qdrant_filter({}) is None


def test_create_with_float16_and_deferred_indexing():
    from unittest.mock import MagicMock, patch
    from qdrant_client.models import Datatype
    from src.storage.qdrant_db import QdrantVectorDatabase

    with patch("src.storage.qdrant_db.QdrantClient") as cls:
        client = MagicMock()
        client.get_collection.side_effect = Exception("not found")
        cls.return_value = client
        db = QdrantVectorDatabase(url="http://x", api_key="k", collection_name="c", create_if_missing=True,
                                  quantize=True, float16=True, defer_indexing=True)
        kwargs = client.create_collection.call_args.kwargs
        assert kwargs["vectors_config"].datatype == Datatype.FLOAT16
        assert kwargs["optimizers_config"].indexing_threshold == 0
        assert kwargs["optimizers_config"].max_segment_size == QdrantVectorDatabase.MAX_SEGMENT_KB
        db.enable_indexing()
        assert client.update_collection.call_args.kwargs["optimizers_config"].indexing_threshold == 10000
