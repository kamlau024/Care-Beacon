"""Tests for markdown parser."""

import pytest
from pathlib import Path
from datetime import datetime

from src.ingestion.markdown_parser import MarkdownParser, normalize_section_name
from src.storage.models import Article, ArticleSection


@pytest.fixture
def parser():
    """Create a parser instance."""
    return MarkdownParser()


@pytest.fixture
def sample_markdown_file(tmp_path):
    """Create a temporary markdown file for testing."""
    content = """---
title: "Test Cancer Article"
url: https://example.com/test-cancer
date_scraped: 2025-11-07T00:00:00
breadcrumbs:
  - Health Info
  - Types Of Cancer
  - Test Cancer
images:
  - src: https://example.com/image.png
---

# Test Cancer

This is a test article about cancer.

## Diagnosis & Staging

### What are the signs and symptoms?

Some symptoms of test cancer include:

  * Symptom one
  * Symptom two
  * Symptom three

If you have any symptoms that you are worried about, please talk to your family doctor.

### How is it diagnosed?

Tests that may help diagnose test cancer include:

  * Physical examination
  * Blood tests
  * Imaging scans

## Treatment

Treatment options depend on the stage and type of cancer.

### Surgery

Surgery may be an option for early-stage cancers.

### Chemotherapy

Chemotherapy uses **drugs** to kill cancer cells. This is a *very important* treatment option.

For more information, see [this link](https://example.com).
"""
    file_path = tmp_path / "test_cancer.md"
    file_path.write_text(content)
    return file_path


def test_parser_initialization(parser):
    """Test parser initializes correctly."""
    assert parser is not None
    assert parser.header_pattern is not None


def test_parse_file_basic(parser, sample_markdown_file):
    """Test basic file parsing."""
    article = parser.parse_file(sample_markdown_file)

    assert isinstance(article, Article)
    assert article.title == "Test Cancer Article"
    assert article.url == "https://example.com/test-cancer"
    assert len(article.breadcrumbs) == 3
    assert article.breadcrumbs[0] == "Health Info"


def test_parse_file_metadata(parser, sample_markdown_file):
    """Test metadata extraction."""
    article = parser.parse_file(sample_markdown_file)

    assert article.title == "Test Cancer Article"
    assert article.url == "https://example.com/test-cancer"
    assert isinstance(article.date_scraped, datetime)
    assert len(article.images) == 1
    assert article.images[0]['src'] == "https://example.com/image.png"


def test_parse_file_sections(parser, sample_markdown_file):
    """Test section extraction."""
    article = parser.parse_file(sample_markdown_file)

    # Should have sections for "Diagnosis & Staging" and "Treatment"
    # (ignoring the # Test Cancer title)
    assert len(article.sections) >= 2

    # Find sections by name
    section_names = [s.name for s in article.sections]
    assert "Diagnosis & Staging" in section_names or "What are the signs and symptoms?" in section_names
    assert "Treatment" in section_names or "Surgery" in section_names


def test_parse_file_paragraphs(parser, sample_markdown_file):
    """Test paragraph extraction."""
    article = parser.parse_file(sample_markdown_file)

    # Get all paragraphs
    all_paragraphs = article.get_all_paragraphs()

    assert len(all_paragraphs) > 0

    # Check that some expected content is present
    all_text = ' '.join(all_paragraphs)
    assert "symptoms" in all_text.lower()
    assert "treatment" in all_text.lower()


def test_parse_file_list_items(parser, sample_markdown_file):
    """Test that list items are properly parsed."""
    article = parser.parse_file(sample_markdown_file)

    all_text = ' '.join(article.get_all_paragraphs())

    # List items should be extracted
    assert "Symptom one" in all_text or "symptom one" in all_text.lower()
    assert "Blood tests" in all_text or "blood tests" in all_text.lower()


def test_parse_file_markdown_cleaning(parser, sample_markdown_file):
    """Test that markdown formatting is cleaned."""
    article = parser.parse_file(sample_markdown_file)

    all_text = ' '.join(article.get_all_paragraphs())

    # Bold and italic markers should be removed
    assert "**" not in all_text
    assert "drugs" in all_text  # Bold text should remain as plain text


def test_article_derived_metadata(parser, sample_markdown_file):
    """Test that derived metadata is generated."""
    article = parser.parse_file(sample_markdown_file)

    # Article ID should be generated from title
    assert article.article_id == "test-cancer-article"

    # Cancer type should be extracted from breadcrumbs
    assert article.cancer_type == "Test Cancer"

    # Source should be set
    assert article.source == "BC Cancer"


def test_article_stats(parser, sample_markdown_file):
    """Test article statistics generation."""
    article = parser.parse_file(sample_markdown_file)
    stats = parser.get_article_stats(article)

    assert 'title' in stats
    assert 'sections_count' in stats
    assert 'total_paragraphs' in stats
    assert 'word_count' in stats
    assert 'char_count' in stats

    assert stats['sections_count'] > 0
    assert stats['total_paragraphs'] > 0
    assert stats['word_count'] > 0


def test_parse_file_not_found(parser):
    """Test handling of non-existent file."""
    with pytest.raises(FileNotFoundError):
        parser.parse_file("nonexistent_file.md")


def test_parse_directory(parser, tmp_path):
    """Test parsing multiple files in a directory."""
    # Create multiple test files
    for i in range(3):
        content = f"""---
title: "Test Article {i}"
url: https://example.com/test-{i}
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Health", "Cancer"]
---

# Test Article {i}

## Section 1

Paragraph {i}.
"""
        file_path = tmp_path / f"article_{i}.md"
        file_path.write_text(content)

    # Parse all files
    articles = parser.parse_directory(tmp_path)

    assert len(articles) == 3
    assert all(isinstance(a, Article) for a in articles)


def test_normalize_section_name():
    """Test section name normalization."""
    assert normalize_section_name("Diagnosis & Staging") == "Diagnosis and Staging"
    assert normalize_section_name("diagnosis") == "Diagnosis and Staging"
    assert normalize_section_name("TREATMENT") == "Treatment"
    assert normalize_section_name("Side Effects") == "Side Effects"
    assert normalize_section_name("Follow-up") == "Follow-up"


def test_empty_sections_handling(parser, tmp_path):
    """Test handling of empty sections."""
    content = """---
title: "Empty Test"
url: https://example.com/empty
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---

## Empty Section

## Another Section

Some content here.
"""
    file_path = tmp_path / "empty.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should handle empty sections gracefully
    assert len(article.sections) >= 1


def test_nested_headers(parser, tmp_path):
    """Test handling of nested headers (##, ###, ####)."""
    content = """---
title: "Nested Headers"
url: https://example.com/nested
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---

## Level 2 Header

Some content.

### Level 3 Header

More content.

#### Level 4 Header

Even more content.
"""
    file_path = tmp_path / "nested.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should create separate sections for each header level
    assert len(article.sections) >= 2

    # Check that levels are captured
    levels = [s.level for s in article.sections]
    assert 2 in levels
    assert 3 in levels or 4 in levels


def test_special_characters_handling(parser, tmp_path):
    """Test handling of special characters."""
    content = """---
title: "Special Characters & Symbols"
url: https://example.com/special
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---

## Diagnosis & Staging

Content with special characters: <, >, &, ", '.

Some text with "quotes" and 'apostrophes'.
"""
    file_path = tmp_path / "special.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should handle special characters without errors
    assert article.title == "Special Characters & Symbols"
    all_text = ' '.join(article.get_all_paragraphs())
    assert len(all_text) > 0
