"""Tests for vector database."""

import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from src.storage.vector_db import VectorDatabase
from src.storage.models import Chunk


@pytest.fixture
def temp_db_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def vector_db(temp_db_dir):
    """Create a vector database instance for testing."""
    db = VectorDatabase(
        persist_directory=temp_db_dir,
        collection_name="test-collection"
    )
    yield db
    # Cleanup
    db.reset()


@pytest.fixture
def sample_chunks_with_embeddings():
    """Create sample chunks with embeddings."""
    chunks = []

    # Create chunks about different topics
    topics = [
        ("breast-cancer", "Breast Cancer", "Breast cancer is the most common cancer in women.", [0.1] * 1536),
        ("breast-cancer", "Breast Cancer", "Early detection through mammography can save lives.", [0.12] * 1536),
        ("lung-cancer", "Lung Cancer", "Lung cancer is often caused by smoking.", [0.5] * 1536),
        ("lung-cancer", "Lung Cancer", "Symptoms include persistent cough and chest pain.", [0.52] * 1536),
        ("pancreatic", "Pancreatic", "Pancreatic cancer is difficult to detect early.", [0.8] * 1536),
    ]

    for i, (article_id, cancer_type, text, embedding) in enumerate(topics):
        chunk = Chunk(
            chunk_id=f"{article_id}_section_p{i:03d}",
            text=text,
            article_id=article_id,
            article_title=cancer_type,
            url=f"https://example.com/{article_id}",
            breadcrumbs=["Health", "Cancer", cancer_type],
            cancer_type=cancer_type,
            source="BC Cancer",
            date_scraped=datetime.now(),
            section="Test Section",
            paragraph_index=i,
            total_paragraphs=10,
            embedding=embedding
        )
        chunks.append(chunk)

    return chunks


def test_database_initialization(vector_db):
    """Test that database initializes correctly."""
    assert vector_db is not None
    assert vector_db.collection_name == "test-collection"
    assert vector_db.count() == 0


def test_add_single_chunk(vector_db, sample_chunks_with_embeddings):
    """Test adding a single chunk."""
    chunk = sample_chunks_with_embeddings[0]

    vector_db.add_chunk(chunk)

    assert vector_db.count() == 1


def test_add_chunk_without_embedding(vector_db):
    """Test that adding chunk without embedding raises error."""
    chunk = Chunk(
        chunk_id="test_chunk",
        text="Test text",
        article_id="test",
        article_title="Test",
        url="https://example.com",
        breadcrumbs=["Test"],
        section="Test",
        paragraph_index=0,
        total_paragraphs=1
    )

    with pytest.raises(ValueError):
        vector_db.add_chunk(chunk)


def test_add_multiple_chunks(vector_db, sample_chunks_with_embeddings):
    """Test adding multiple chunks in batch."""
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    assert vector_db.count() == len(sample_chunks_with_embeddings)


def test_search_basic(vector_db, sample_chunks_with_embeddings):
    """Test basic similarity search."""
    # Add chunks
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    # Search with a query similar to breast cancer chunks
    query_embedding = [0.11] * 1536  # Similar to breast cancer embeddings

    results = vector_db.search(query_embedding, n_results=3)

    # Should return results
    assert len(results) > 0
    assert len(results) <= 3

    # Results should be ordered by similarity
    for i in range(len(results) - 1):
        assert results[i].similarity_score >= results[i + 1].similarity_score


def test_search_with_metadata_filter(vector_db, sample_chunks_with_embeddings):
    """Test search with metadata filtering."""
    # Add chunks
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    # Search only for breast cancer chunks
    query_embedding = [0.11] * 1536

    results = vector_db.search(
        query_embedding,
        n_results=5,
        where={"cancer_type": "Breast Cancer"}
    )

    # Should only return breast cancer results
    assert len(results) > 0
    for result in results:
        assert result.chunk.cancer_type == "Breast Cancer"


def test_get_chunk(vector_db, sample_chunks_with_embeddings):
    """Test retrieving a specific chunk by ID."""
    # Add chunks
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    # Get a specific chunk
    chunk_id = sample_chunks_with_embeddings[0].chunk_id
    retrieved_chunk = vector_db.get_chunk(chunk_id)

    assert retrieved_chunk is not None
    assert retrieved_chunk.chunk_id == chunk_id
    assert retrieved_chunk.text == sample_chunks_with_embeddings[0].text


def test_get_nonexistent_chunk(vector_db):
    """Test getting a chunk that doesn't exist."""
    chunk = vector_db.get_chunk("nonexistent_id")
    assert chunk is None


def test_delete_chunk(vector_db, sample_chunks_with_embeddings):
    """Test deleting a single chunk."""
    # Add chunks
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)
    initial_count = vector_db.count()

    # Delete one chunk
    chunk_id = sample_chunks_with_embeddings[0].chunk_id
    vector_db.delete_chunk(chunk_id)

    assert vector_db.count() == initial_count - 1
    assert vector_db.get_chunk(chunk_id) is None


def test_delete_multiple_chunks(vector_db, sample_chunks_with_embeddings):
    """Test deleting multiple chunks."""
    # Add chunks
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)
    initial_count = vector_db.count()

    # Delete two chunks
    chunk_ids = [c.chunk_id for c in sample_chunks_with_embeddings[:2]]
    vector_db.delete_chunks(chunk_ids)

    assert vector_db.count() == initial_count - 2


def test_delete_by_article(vector_db, sample_chunks_with_embeddings):
    """Test deleting all chunks from an article."""
    # Add chunks
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    # Delete all breast cancer chunks
    vector_db.delete_by_article("breast-cancer")

    # Verify deletion
    query_embedding = [0.11] * 1536
    results = vector_db.search(
        query_embedding,
        n_results=10,
        where={"article_id": "breast-cancer"}
    )

    assert len(results) == 0


def test_count(vector_db, sample_chunks_with_embeddings):
    """Test counting chunks."""
    assert vector_db.count() == 0

    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    assert vector_db.count() == len(sample_chunks_with_embeddings)


def test_get_stats(vector_db, sample_chunks_with_embeddings):
    """Test getting database statistics."""
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    stats = vector_db.get_stats()

    assert stats['collection_name'] == "test-collection"
    assert stats['total_chunks'] == len(sample_chunks_with_embeddings)
    assert 'unique_articles_sample' in stats
    assert 'distance_metric' in stats


def test_peek(vector_db, sample_chunks_with_embeddings):
    """Test peeking at sample chunks."""
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    samples = vector_db.peek(limit=3)

    assert len(samples) <= 3
    assert all(isinstance(c, Chunk) for c in samples)
    assert all(c.embedding is not None for c in samples)


def test_reset(vector_db, sample_chunks_with_embeddings):
    """Test resetting the database."""
    # Add chunks
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)
    assert vector_db.count() > 0

    # Reset
    vector_db.reset()

    # Should be empty
    assert vector_db.count() == 0


def test_persistence(temp_db_dir, sample_chunks_with_embeddings):
    """Test that data persists across database instances."""
    # Create database and add chunks
    db1 = VectorDatabase(
        persist_directory=temp_db_dir,
        collection_name="persist-test"
    )
    db1.add_chunks(sample_chunks_with_embeddings, show_progress=False)
    count1 = db1.count()

    # Create new database instance with same directory
    db2 = VectorDatabase(
        persist_directory=temp_db_dir,
        collection_name="persist-test"
    )

    # Should have same data
    count2 = db2.count()
    assert count1 == count2

    # Cleanup
    db2.reset()


def test_empty_search(vector_db):
    """Test search on empty database."""
    query_embedding = [0.1] * 1536

    results = vector_db.search(query_embedding, n_results=5)

    assert len(results) == 0


def test_retrieval_result_ordering(vector_db, sample_chunks_with_embeddings):
    """Test that retrieval results have correct rank ordering."""
    vector_db.add_chunks(sample_chunks_with_embeddings, show_progress=False)

    query_embedding = [0.11] * 1536
    results = vector_db.search(query_embedding, n_results=5)

    # Check rank is sequential
    for i, result in enumerate(results):
        assert result.rank == i + 1


def test_add_chunks_with_batch_size(vector_db, sample_chunks_with_embeddings):
    """Test adding chunks with custom batch size."""
    # Add with small batch size
    vector_db.add_chunks(sample_chunks_with_embeddings, batch_size=2, show_progress=False)

    assert vector_db.count() == len(sample_chunks_with_embeddings)


def test_add_empty_chunks_list(vector_db):
    """Test adding empty list of chunks."""
    vector_db.add_chunks([], show_progress=False)

    assert vector_db.count() == 0
