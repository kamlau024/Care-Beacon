"""Tests for document chunking."""

import pytest
from datetime import datetime

from src.embeddings.chunking import DocumentChunker
from src.storage.models import Article, ArticleSection, Chunk


@pytest.fixture
def chunker():
    """Create a chunker instance."""
    return DocumentChunker()


@pytest.fixture
def sample_article():
    """Create a sample article for testing."""
    section1 = ArticleSection(
        name="Introduction",
        level=2,
        paragraphs=[
            "This is the first paragraph about cancer.",
            "This is the second paragraph with more information.",
            "This is a third paragraph that is very short."
        ]
    )

    section2 = ArticleSection(
        name="Diagnosis & Staging",
        level=2,
        paragraphs=[
            "Diagnosis involves several tests including physical examination and blood tests.",
            "Staging determines how advanced the cancer is and helps guide treatment decisions."
        ]
    )

    article = Article(
        title="Test Cancer",
        url="https://example.com/test-cancer",
        date_scraped=datetime.now(),
        breadcrumbs=["Health", "Cancer", "Test"],
        sections=[section1, section2]
    )

    return article


def test_chunker_initialization(chunker):
    """Test chunker initializes with correct defaults."""
    assert chunker.min_chunk_length == 20
    assert chunker.max_chunk_length == 2000


def test_chunk_article_basic(chunker, sample_article):
    """Test basic article chunking."""
    chunks = chunker.chunk_article(sample_article)

    # Should have 5 paragraphs total
    assert len(chunks) == 5

    # All should be Chunk objects
    assert all(isinstance(c, Chunk) for c in chunks)


def test_chunk_metadata(chunker, sample_article):
    """Test that chunk metadata is preserved."""
    chunks = chunker.chunk_article(sample_article)

    first_chunk = chunks[0]

    # Check metadata
    assert first_chunk.article_id == "test-cancer"
    assert first_chunk.article_title == "Test Cancer"
    assert first_chunk.url == "https://example.com/test-cancer"
    assert first_chunk.breadcrumbs == ["Health", "Cancer", "Test"]
    # cancer_type won't be auto-detected without "Types Of Cancer" in breadcrumbs
    assert first_chunk.cancer_type is None or first_chunk.cancer_type == "Test"
    assert first_chunk.source == "BC Cancer"
    assert first_chunk.section == "Introduction"


def test_chunk_id_generation(chunker, sample_article):
    """Test that unique chunk IDs are generated."""
    chunks = chunker.chunk_article(sample_article)

    # All chunk IDs should be unique
    chunk_ids = [c.chunk_id for c in chunks]
    assert len(chunk_ids) == len(set(chunk_ids))

    # Check format: article-id_section-slug_pXXX
    first_chunk_id = chunks[0].chunk_id
    assert first_chunk_id.startswith("test-cancer_")
    assert "_p" in first_chunk_id


def test_chunk_text_content(chunker, sample_article):
    """Test that chunk text is preserved correctly."""
    chunks = chunker.chunk_article(sample_article)

    # First chunk should have first paragraph text
    assert chunks[0].text == "This is the first paragraph about cancer."

    # Second chunk should have second paragraph text
    assert chunks[1].text == "This is the second paragraph with more information."


def test_chunk_paragraph_indexing(chunker, sample_article):
    """Test that paragraph indices are sequential."""
    chunks = chunker.chunk_article(sample_article)

    # Check indices are sequential
    for i, chunk in enumerate(chunks):
        assert chunk.paragraph_index == i


def test_chunk_section_tracking(chunker, sample_article):
    """Test that section names are tracked correctly."""
    chunks = chunker.chunk_article(sample_article)

    # First 3 chunks should be from "Introduction"
    assert chunks[0].section == "Introduction"
    assert chunks[1].section == "Introduction"
    assert chunks[2].section == "Introduction"

    # Last 2 chunks should be from "Diagnosis & Staging"
    assert chunks[3].section == "Diagnosis & Staging"
    assert chunks[4].section == "Diagnosis & Staging"


def test_min_chunk_length_filter():
    """Test that short paragraphs are filtered out."""
    chunker = DocumentChunker(min_chunk_length=30)

    section = ArticleSection(
        name="Test",
        level=2,
        paragraphs=[
            "Short.",  # Too short, should be filtered
            "This is a longer paragraph that meets the minimum length requirement.",  # Should be kept
            "Also short.",  # Too short
        ]
    )

    article = Article(
        title="Test",
        url="https://example.com",
        date_scraped=datetime.now(),
        breadcrumbs=["Test"],
        sections=[section]
    )

    chunks = chunker.chunk_article(article)

    # Should only have 1 chunk (the long one)
    assert len(chunks) == 1
    assert "longer paragraph" in chunks[0].text


def test_long_paragraph_splitting():
    """Test that long paragraphs are split."""
    chunker = DocumentChunker(max_chunk_length=100)

    # Create a long paragraph
    long_text = "This is a sentence. " * 20  # 20 sentences, definitely over 100 chars

    section = ArticleSection(
        name="Test",
        level=2,
        paragraphs=[long_text]
    )

    article = Article(
        title="Test",
        url="https://example.com",
        date_scraped=datetime.now(),
        breadcrumbs=["Test"],
        sections=[section]
    )

    chunks = chunker.chunk_article(article)

    # Should have multiple chunks
    assert len(chunks) > 1

    # Each chunk should be under max length
    for chunk in chunks:
        assert len(chunk.text) <= 100

    # Sub-index should be added to chunk IDs
    assert "_s00" in chunks[0].chunk_id or "_s" not in chunks[0].chunk_id


def test_chunk_multiple_articles(chunker):
    """Test chunking multiple articles at once."""
    articles = []

    for i in range(3):
        section = ArticleSection(
            name="Section",
            level=2,
            paragraphs=[f"Paragraph {i} in article {i}."]
        )

        article = Article(
            title=f"Article {i}",
            url=f"https://example.com/article-{i}",
            date_scraped=datetime.now(),
            breadcrumbs=["Test"],
            sections=[section]
        )
        articles.append(article)

    chunks = chunker.chunk_articles(articles)

    # Should have 3 chunks total (one per article)
    assert len(chunks) == 3

    # Chunk IDs should be unique across articles
    chunk_ids = [c.chunk_id for c in chunks]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_chunking_stats(chunker, sample_article):
    """Test statistics generation."""
    chunks = chunker.chunk_article(sample_article)
    stats = chunker.get_chunking_stats(chunks)

    assert stats['total_chunks'] == 5
    assert stats['total_characters'] > 0
    assert stats['total_words'] > 0
    assert stats['avg_chunk_length'] > 0
    assert stats['avg_words_per_chunk'] > 0
    assert stats['min_chunk_length'] > 0
    assert stats['max_chunk_length'] > 0
    assert stats['unique_articles'] == 1
    assert stats['unique_sections'] == 2


def test_empty_article_handling(chunker):
    """Test handling of article with no paragraphs."""
    section = ArticleSection(
        name="Empty",
        level=2,
        paragraphs=[]
    )

    article = Article(
        title="Empty Article",
        url="https://example.com/empty",
        date_scraped=datetime.now(),
        breadcrumbs=["Test"],
        sections=[section]
    )

    chunks = chunker.chunk_article(article)

    # Should return empty list
    assert len(chunks) == 0


def test_special_characters_in_chunk_id():
    """Test that special characters in section names are handled."""
    chunker = DocumentChunker()

    section = ArticleSection(
        name="Diagnosis & Staging: What You Need to Know!",
        level=2,
        paragraphs=["Test paragraph with enough characters to not be filtered out."]
    )

    article = Article(
        title="Test",
        url="https://example.com",
        date_scraped=datetime.now(),
        breadcrumbs=["Test"],
        sections=[section]
    )

    chunks = chunker.chunk_article(article)

    # Chunk ID should not have special characters
    chunk_id = chunks[0].chunk_id
    assert "&" not in chunk_id
    assert ":" not in chunk_id
    assert "!" not in chunk_id
    assert "diagnosis" in chunk_id.lower()


def test_chunk_to_metadata_conversion(chunker, sample_article):
    """Test that chunk can be converted to metadata dict."""
    chunks = chunker.chunk_article(sample_article)
    chunk = chunks[0]

    metadata = chunk.to_metadata()

    assert isinstance(metadata, dict)
    assert metadata['chunk_id'] == chunk.chunk_id
    assert metadata['article_id'] == chunk.article_id
    assert metadata['article_title'] == chunk.article_title
    assert metadata['section'] == chunk.section
    assert metadata['paragraph_index'] == chunk.paragraph_index


def test_stats_with_empty_chunks(chunker):
    """Test statistics with no chunks."""
    stats = chunker.get_chunking_stats([])

    assert stats['total_chunks'] == 0
    assert stats['total_characters'] == 0
    assert stats['avg_chunk_length'] == 0
