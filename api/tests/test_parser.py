"""Tests for markdown parser."""

import pytest
from pathlib import Path
from datetime import datetime

from src.ingestion.markdown_parser import MedicalArticleParser, normalize_section_name
from src.storage.models import Article, ArticleSection


@pytest.fixture
def parser():
    """Create a parser instance."""
    return MedicalArticleParser()


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


def test_source_defaults_to_bc_cancer(parser, sample_markdown_file):
    """Test that source defaults to BC Cancer when not specified."""
    article = parser.parse_file(sample_markdown_file)

    assert article.source == "BC Cancer"


def test_source_from_bc_cancer_path(parser, tmp_path):
    """Test source detection from bc-cancer directory path."""
    # Create a file in bc-cancer directory structure
    bc_dir = tmp_path / "bc-cancer" / "articles"
    bc_dir.mkdir(parents=True)

    content = """---
title: "BC Cancer Test Article"
url: https://www.bccancer.bc.ca/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---

## Content

Test content from BC Cancer.
"""
    file_path = bc_dir / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should detect BC Cancer from path
    assert article.source == "BC Cancer"


def test_source_from_canadian_cancer_society_path(parser, tmp_path):
    """Test source detection from canadian-cancer-society directory path."""
    # Create a file in canadian-cancer-society directory structure
    ccs_dir = tmp_path / "canadian-cancer-society" / "articles"
    ccs_dir.mkdir(parents=True)

    content = """---
title: "Canadian Cancer Society Test Article"
url: https://cancer.ca/en/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---

## Content

Test content from Canadian Cancer Society.
"""
    file_path = ccs_dir / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should detect Canadian Cancer Society from path
    assert article.source == "Canadian Cancer Society"


def test_source_detection_case_insensitive(parser, tmp_path):
    """Test that source detection is case-insensitive."""
    # Test with uppercase
    dir1 = tmp_path / "BC-CANCER" / "articles"
    dir1.mkdir(parents=True)

    content = """---
title: "Test Article"
url: https://example.com/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## Content
Test content.
"""
    file1 = dir1 / "test.md"
    file1.write_text(content)

    article1 = parser.parse_file(file1)
    assert article1.source == "BC Cancer"

    # Test with mixed case
    dir2 = tmp_path / "Canadian-Cancer-Society" / "articles"
    dir2.mkdir(parents=True)
    file2 = dir2 / "test2.md"
    file2.write_text(content)

    article2 = parser.parse_file(file2)
    assert article2.source == "Canadian Cancer Society"


def test_source_detection_from_url_pattern(parser, tmp_path):
    """Test source detection from cancer.ca URL pattern."""
    # Create file with cancer.ca in path
    dir = tmp_path / "data" / "cancer.ca" / "articles"
    dir.mkdir(parents=True)

    content = """---
title: "Test Article"
url: https://cancer.ca/en/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## Content
Test content.
"""
    file_path = dir / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should detect Canadian Cancer Society from cancer.ca pattern
    assert article.source == "Canadian Cancer Society"


def test_source_detection_bccancer_variant(parser, tmp_path):
    """Test source detection with bccancer (no hyphen) variant."""
    dir = tmp_path / "data" / "bccancer" / "articles"
    dir.mkdir(parents=True)

    content = """---
title: "Test Article"
url: https://example.com/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## Content
Test content.
"""
    file_path = dir / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should detect BC Cancer from bccancer pattern
    assert article.source == "BC Cancer"


def test_source_defaults_to_bc_cancer_with_no_match(parser, tmp_path):
    """Test that source defaults to BC Cancer when no pattern matches."""
    # Create file with no recognizable source pattern
    dir = tmp_path / "unknown" / "source" / "articles"
    dir.mkdir(parents=True)

    content = """---
title: "Test Article"
url: https://example.com/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## Content
Test content.
"""
    file_path = dir / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should default to BC Cancer
    assert article.source == "BC Cancer"


def test_multiple_sources_in_dataset(parser, tmp_path):
    """Test parsing articles from different sources."""
    # Create BC Cancer file
    bc_dir = tmp_path / "bc-cancer"
    bc_dir.mkdir(parents=True)
    bc_content = """---
title: "BC Cancer Article"
url: https://www.bccancer.bc.ca/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## Content
BC Cancer content.
"""
    bc_file = bc_dir / "bc_article.md"
    bc_file.write_text(bc_content)

    # Create Canadian Cancer Society file
    ccs_dir = tmp_path / "canadian-cancer-society"
    ccs_dir.mkdir(parents=True)
    ccs_content = """---
title: "CCS Article"
url: https://cancer.ca/en/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## Content
Canadian Cancer Society content.
"""
    ccs_file = ccs_dir / "ccs_article.md"
    ccs_file.write_text(ccs_content)

    # Parse both articles
    bc_article = parser.parse_file(bc_file)
    ccs_article = parser.parse_file(ccs_file)

    # Verify both have source information
    assert bc_article.source is not None
    assert ccs_article.source is not None
    assert bc_article.source == "BC Cancer"
    assert ccs_article.source == "Canadian Cancer Society"


def test_date_parsing_with_timezone_plus_sign(parser, tmp_path):
    """Test date parsing with '+' timezone (line 91)."""
    # Use datetime objects that will work with fromisoformat
    from datetime import datetime

    content = """---
title: "Test Article"
url: https://example.com/test
date_scraped: "2024-01-15 10:30:00+05:00"
breadcrumbs: ["Test"]
---
## Content
Test content.
"""
    file_path = tmp_path / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should parse successfully and extract date (lines 91, 94)
    assert article.date_scraped is not None
    # Just verify that we got a datetime object - the parsing logic
    # splits on '+' and uses datetime parsing


def test_date_parsing_iso_format_with_time(parser, tmp_path):
    """Test date parsing with ISO format containing time (line 94)."""
    # Use ISO format with 'T' but no timezone - this will hit line 94 directly
    content = """---
title: "Test Article"
url: https://example.com/test
date_scraped: "2024-03-15T14:30:45"
breadcrumbs: ["Test"]
---
## Content
Test content.
"""
    file_path = tmp_path / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should parse ISO format with time using fromisoformat (line 94)
    assert article.date_scraped is not None
    assert article.date_scraped.year == 2024
    assert article.date_scraped.month == 3
    assert article.date_scraped.day == 15
    assert article.date_scraped.hour == 14
    assert article.date_scraped.minute == 30
    assert article.date_scraped.second == 45


def test_date_parsing_missing_date_scraped(parser, tmp_path):
    """Test date parsing when date_scraped is missing (line 102)."""
    content = """---
title: "Test Article"
url: https://example.com/test
breadcrumbs: ["Test"]
---
## Content
Test content without date_scraped field.
"""
    file_path = tmp_path / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should use current time as fallback
    assert article.date_scraped is not None
    # Date should be recent (within last minute)
    from datetime import datetime, timedelta
    assert datetime.now() - article.date_scraped < timedelta(minutes=1)


def test_parse_sections_with_paragraph_before_new_header(parser, tmp_path):
    """Test parsing when there's a paragraph before a new header (lines 146-149)."""
    content = """---
title: "Test Article"
url: https://example.com/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## First Section
This is content in the first section.
More content without blank lines.
## Second Section
This is the second paragraph.
"""
    file_path = tmp_path / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should have two sections
    assert len(article.sections) >= 2

    # First section should have saved the paragraph before the new header (lines 146-149)
    first_section = article.sections[0]
    assert len(first_section.paragraphs) > 0
    assert "first section" in first_section.paragraphs[0].lower()


def test_parse_blockquote_content(parser, tmp_path):
    """Test parsing content with blockquotes (line 210)."""
    content = """---
title: "Test Article"
url: https://example.com/test
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## Section With Blockquote

> This is a blockquote
> It spans multiple lines

Regular paragraph after blockquote.
"""
    file_path = tmp_path / "test.md"
    file_path.write_text(content)

    article = parser.parse_file(file_path)

    # Should parse blockquote content
    assert len(article.sections) > 0
    assert len(article.sections[0].paragraphs) > 0

    # Blockquote content should be extracted (without '>')
    all_text = ' '.join(article.sections[0].paragraphs)
    assert "blockquote" in all_text.lower()
    assert ">" not in all_text  # '>' should be stripped


def test_parse_directory_not_found(parser, tmp_path):
    """Test parse_directory with non-existent directory (line 244)."""
    nonexistent_dir = tmp_path / "nonexistent"

    with pytest.raises(FileNotFoundError) as exc_info:
        parser.parse_directory(nonexistent_dir)

    assert "Directory not found" in str(exc_info.value)


def test_parse_directory_with_invalid_file(parser, tmp_path):
    """Test parse_directory with a file that fails to parse (lines 251-253)."""
    # Create one valid file
    valid_content = """---
title: "Valid Article"
url: https://example.com/valid
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"]
---
## Content
Valid content.
"""
    valid_file = tmp_path / "valid.md"
    valid_file.write_text(valid_content)

    # Create one invalid file (corrupted YAML frontmatter)
    invalid_content = """---
title: "Invalid Article
url: https://example.com/invalid
date_scraped: 2025-11-07T00:00:00
breadcrumbs: ["Test"
---
## Content
Invalid content with broken YAML.
"""
    invalid_file = tmp_path / "invalid.md"
    invalid_file.write_text(invalid_content)

    # Parse directory - should skip invalid file and continue (lines 251-253)
    articles = parser.parse_directory(tmp_path)

    # Should still parse the valid file successfully
    # The invalid file should be skipped with exception handling
    assert len(articles) >= 1
    assert any(a.title == "Valid Article" for a in articles)

    # Should not include the invalid article
    assert not any("Invalid Article" in a.title for a in articles)
