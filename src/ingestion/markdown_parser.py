"""Markdown parser for medical articles with YAML frontmatter."""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import frontmatter

from src.storage.models import Article, ArticleSection


class MarkdownParser:
    """Parser for markdown files with YAML frontmatter."""

    def __init__(self):
        """Initialize the parser."""
        # Regex patterns
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        self.list_item_pattern = re.compile(r'^\s*[\*\-\+]\s+(.+)$')
        self.blockquote_pattern = re.compile(r'^\s*>\s+(.+)$')

    def parse_file(self, file_path: str | Path) -> Article:
        """Parse a markdown file and return an Article object.

        Args:
            file_path: Path to the markdown file

        Returns:
            Article object with parsed content

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If frontmatter is missing required fields
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Parse frontmatter and content
        with open(file_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)

        # Extract metadata from frontmatter
        metadata = post.metadata
        title = metadata.get('title', '')
        url = metadata.get('url', '')
        breadcrumbs = metadata.get('breadcrumbs', [])
        images = metadata.get('images', [])

        # Parse date_scraped
        date_scraped_raw = metadata.get('date_scraped', '')
        if date_scraped_raw:
            # Convert to string if it's not already
            date_scraped_str = str(date_scraped_raw)
            # Handle ISO format with or without microseconds
            try:
                # Replace 'Z' with '+00:00' for UTC timezone
                date_scraped_str = date_scraped_str.replace('Z', '+00:00')
                # Remove timezone info if present (keep it simple)
                if '+' in date_scraped_str:
                    date_scraped_str = date_scraped_str.split('+')[0]
                if 'T' in date_scraped_str:
                    # ISO format with time
                    date_scraped = datetime.fromisoformat(date_scraped_str)
                else:
                    # Date only
                    date_scraped = datetime.strptime(date_scraped_str, '%Y-%m-%d')
            except (ValueError, AttributeError, TypeError) as e:
                # If parsing fails, use current time
                date_scraped = datetime.now()
        else:
            date_scraped = datetime.now()

        # Parse content into sections
        content = post.content
        sections = self._parse_sections(content)

        # Create article
        article = Article(
            title=title,
            url=url,
            date_scraped=date_scraped,
            breadcrumbs=breadcrumbs,
            images=images,
            sections=sections
        )

        return article

    def _parse_sections(self, content: str) -> List[ArticleSection]:
        """Parse markdown content into sections with paragraphs.

        Args:
            content: Markdown content string

        Returns:
            List of ArticleSection objects
        """
        sections: List[ArticleSection] = []
        lines = content.split('\n')

        current_section: Optional[ArticleSection] = None
        current_paragraph_lines: List[str] = []

        for line in lines:
            # Check if line is a header
            header_match = self.header_pattern.match(line)

            if header_match:
                # Save previous paragraph if exists
                if current_paragraph_lines and current_section:
                    paragraph = ' '.join(current_paragraph_lines).strip()
                    if paragraph:
                        current_section.paragraphs.append(paragraph)
                    current_paragraph_lines = []

                # Save previous section if exists
                if current_section:
                    sections.append(current_section)

                # Start new section
                header_level = len(header_match.group(1))
                section_name = header_match.group(2).strip()

                current_section = ArticleSection(
                    name=section_name,
                    level=header_level,
                    paragraphs=[]
                )

            elif not line.strip():
                # Empty line - end current paragraph
                if current_paragraph_lines and current_section:
                    paragraph = ' '.join(current_paragraph_lines).strip()
                    if paragraph:
                        current_section.paragraphs.append(paragraph)
                    current_paragraph_lines = []

            else:
                # Regular content line
                if current_section:
                    # Clean the line
                    cleaned_line = self._clean_line(line)
                    if cleaned_line:
                        current_paragraph_lines.append(cleaned_line)

        # Save final paragraph
        if current_paragraph_lines and current_section:
            paragraph = ' '.join(current_paragraph_lines).strip()
            if paragraph:
                current_section.paragraphs.append(paragraph)

        # Save final section
        if current_section:
            sections.append(current_section)

        return sections

    def _clean_line(self, line: str) -> str:
        """Clean a line of markdown formatting.

        Args:
            line: Raw line from markdown

        Returns:
            Cleaned line with minimal markdown
        """
        # Handle list items
        list_match = self.list_item_pattern.match(line)
        if list_match:
            return list_match.group(1).strip()

        # Handle blockquotes
        blockquote_match = self.blockquote_pattern.match(line)
        if blockquote_match:
            return blockquote_match.group(1).strip()

        # Remove inline markdown (bold, italic, links)
        cleaned = line.strip()

        # Remove bold/italic
        cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', cleaned)  # **bold**
        cleaned = re.sub(r'\*(.+?)\*', r'\1', cleaned)  # *italic*
        cleaned = re.sub(r'__(.+?)__', r'\1', cleaned)  # __bold__
        cleaned = re.sub(r'_(.+?)_', r'\1', cleaned)  # _italic_

        # Convert markdown links to just text with URL
        cleaned = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1 (\2)', cleaned)

        # Remove inline code
        cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)

        return cleaned

    def parse_directory(self, directory: str | Path, pattern: str = "**/*.md") -> List[Article]:
        """Parse all markdown files in a directory.

        Args:
            directory: Path to directory containing markdown files
            pattern: Glob pattern for finding files (default: **/*.md)

        Returns:
            List of Article objects

        Raises:
            FileNotFoundError: If directory doesn't exist
        """
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        articles = []
        for file_path in directory.glob(pattern):
            try:
                article = self.parse_file(file_path)
                articles.append(article)
            except Exception as e:
                print(f"Warning: Failed to parse {file_path}: {e}")
                continue

        return articles

    def get_article_stats(self, article: Article) -> Dict[str, Any]:
        """Get statistics about an article.

        Args:
            article: Article object

        Returns:
            Dictionary with statistics
        """
        total_paragraphs = article.get_total_paragraph_count()
        sections_count = len(article.sections)

        # Calculate text statistics
        all_text = ' '.join(article.get_all_paragraphs())
        word_count = len(all_text.split())
        char_count = len(all_text)

        return {
            'title': article.title,
            'article_id': article.article_id,
            'cancer_type': article.cancer_type,
            'sections_count': sections_count,
            'total_paragraphs': total_paragraphs,
            'word_count': word_count,
            'char_count': char_count,
            'avg_paragraph_length': word_count / total_paragraphs if total_paragraphs > 0 else 0
        }


def normalize_section_name(section_name: str) -> str:
    """Normalize section names to standard medical article sections.

    Args:
        section_name: Raw section name from markdown

    Returns:
        Normalized section name
    """
    section_lower = section_name.lower().strip()

    # Mapping of common variations to standard names
    mappings = {
        'diagnosis & staging': 'Diagnosis and Staging',
        'diagnosis and staging': 'Diagnosis and Staging',
        'diagnosis': 'Diagnosis and Staging',
        'staging': 'Diagnosis and Staging',

        'signs and symptoms': 'Signs and Symptoms',
        'symptoms': 'Signs and Symptoms',

        'treatment': 'Treatment',
        'treatments': 'Treatment',

        'surgery': 'Surgery',
        'chemotherapy': 'Chemotherapy',
        'radiation': 'Radiation Therapy',
        'radiation therapy': 'Radiation Therapy',
        'radiotherapy': 'Radiation Therapy',

        'side effects': 'Side Effects',
        'side effect': 'Side Effects',

        'follow-up': 'Follow-up',
        'followup': 'Follow-up',
        'follow up': 'Follow-up',

        'causes': 'Causes and Risk Factors',
        'risk factors': 'Causes and Risk Factors',
        'causes and risk factors': 'Causes and Risk Factors',

        'prevention': 'Prevention',
        'screening': 'Screening',

        'support': 'Support and Resources',
        'resources': 'Support and Resources',
        'support and resources': 'Support and Resources',
    }

    return mappings.get(section_lower, section_name)
