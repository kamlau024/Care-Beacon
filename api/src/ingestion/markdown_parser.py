"""Markdown parser for medical articles with YAML frontmatter."""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import frontmatter

from src.storage.models import Article, ArticleSection

# A cleaned list-item line, as _clean_line writes it: "- text" or "1. text"
LIST_LINE = re.compile(r'^(?:- |\d+[.)] )', re.MULTILINE)


class MedicalArticleParser:
    """Parser for markdown files with YAML frontmatter."""

    def __init__(self):
        """Initialize the parser."""
        # Regex patterns
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        # Bullet (*, -, +) or numbered (1. / 1)) list item; group 1 is the marker
        self.list_item_pattern = re.compile(r'^\s*([\*\-\+]|\d+[.)])\s+(.+)$')
        self.blockquote_pattern = re.compile(r'^\s*>\s+(.+)$')

        # Source detection patterns (order matters - more specific patterns first)
        self.source_mappings = {
            'cleveland-clinic': 'Cleveland Clinic',  # Check this before canadian-cancer-society
            'bc-cancer': 'BC Cancer',
            'bccancer': 'BC Cancer',
            'canadian-cancer-society': 'Canadian Cancer Society',
            'cancer.ca': 'Canadian Cancer Society',
        }

    def _detect_source_from_path(self, file_path: Path) -> str:
        """Detect the source organization from the file path.

        Args:
            file_path: Path to the markdown file

        Returns:
            Source name (e.g., "BC Cancer", "Canadian Cancer Society")
            Defaults to "BC Cancer" if no pattern matches
        """
        # Convert path to lowercase string for matching
        path_str = str(file_path).lower()

        # Check each pattern
        for pattern, source_name in self.source_mappings.items():
            if pattern in path_str:
                return source_name

        # Default to BC Cancer
        return "BC Cancer"

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

        # Detect source from file path
        source = self._detect_source_from_path(file_path)

        # Create article
        article = Article(
            title=title,
            url=url,
            date_scraped=date_scraped,
            breadcrumbs=breadcrumbs,
            images=images,
            sections=sections,
            source=source,
            file_path=str(file_path)  # Store file path for unique ID generation
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
        # (cleaned text, is_list_item) for the paragraph being collected
        current_paragraph_lines: List[Tuple[str, bool]] = []

        def flush_paragraph() -> None:
            if current_paragraph_lines and current_section:
                paragraph = self._join_paragraph_lines(current_paragraph_lines)
                if paragraph:
                    current_section.paragraphs.append(paragraph)
            current_paragraph_lines.clear()

        def flush_section() -> None:
            if current_section:
                current_section.paragraphs = self._merge_lists_with_lead_ins(
                    current_section.paragraphs
                )
                sections.append(current_section)

        for line in lines:
            header_match = self.header_pattern.match(line)

            if header_match:
                flush_paragraph()
                flush_section()

                current_section = ArticleSection(
                    name=header_match.group(2).strip(),
                    level=len(header_match.group(1)),
                    paragraphs=[]
                )

            elif not line.strip():
                # Empty line - end current paragraph
                flush_paragraph()

            elif line.strip() == "Advertisement":
                # Cleveland Clinic ad slot marker. It often sits between a
                # lead-in and its list, which would keep them apart.
                continue

            elif current_section:
                is_list_item = bool(self.list_item_pattern.match(line))
                cleaned_line = self._clean_line(line)
                if cleaned_line:
                    current_paragraph_lines.append((cleaned_line, is_list_item))

        flush_paragraph()
        flush_section()

        return sections

    def _clean_line(self, line: str) -> str:
        """Clean a line of markdown formatting.

        List items keep a marker ("- " for bullets, "1. " for numbered items) so
        the chunker can tell a list from prose. Links keep only their text: the
        URL is noise in an embedding, and the article URL is already in the
        chunk metadata for citations. Images are dropped.

        Args:
            line: Raw line from markdown

        Returns:
            Cleaned line with minimal markdown
        """
        marker = ""
        list_match = self.list_item_pattern.match(line)
        blockquote_match = self.blockquote_pattern.match(line)
        if list_match:
            bullet = list_match.group(1)
            marker = f"{bullet} " if bullet[0].isdigit() else "- "
            cleaned = list_match.group(2).strip()
        elif blockquote_match:
            cleaned = blockquote_match.group(1).strip()
        else:
            cleaned = line.strip()

        # Images, then links (before italics, so underscores in URLs can't
        # be read as _italic_ markers)
        cleaned = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', cleaned)
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', cleaned)

        # Remove bold/italic
        cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', cleaned)  # **bold**
        cleaned = re.sub(r'\*(.+?)\*', r'\1', cleaned)  # *italic*
        cleaned = re.sub(r'__(.+?)__', r'\1', cleaned)  # __bold__
        cleaned = re.sub(r'_(.+?)_', r'\1', cleaned)  # _italic_

        # Remove inline code
        cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)

        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        return f"{marker}{cleaned}" if cleaned else ""

    @staticmethod
    def _join_paragraph_lines(lines: List[Tuple[str, bool]]) -> str:
        """Join a paragraph's lines: prose with spaces, list items one per line.

        A non-item line that follows a list item is a wrapped continuation of
        that item and is appended to it.
        """
        parts: List[str] = []
        for text, is_item in lines:
            if is_item or not parts:
                parts.append(text)
            else:
                # Prose continues the previous prose run or list item
                parts[-1] = f"{parts[-1]} {text}"
        return "\n".join(parts).strip()

    @staticmethod
    def _is_list_paragraph(paragraph: str) -> bool:
        return bool(LIST_LINE.match(paragraph))

    def _merge_lists_with_lead_ins(self, paragraphs: List[str]) -> List[str]:
        """Attach each list to the paragraph that introduces it.

        In the source markdown a lead-in such as "Common side effects include:"
        is separated from its list by a blank line, so it arrives as a paragraph
        of its own. On its own it holds no information but matches questions
        very closely, so it would outrank the list it introduces. Loose lists
        (blank lines between items) are rejoined the same way.
        """
        merged: List[str] = []
        for paragraph in paragraphs:
            if merged and self._is_list_paragraph(paragraph):
                previous = merged[-1]
                last_line = previous.rsplit("\n", 1)[-1]
                if previous.rstrip().endswith(":") or LIST_LINE.match(last_line):
                    merged[-1] = f"{previous}\n{paragraph}"
                    continue
            merged.append(paragraph)
        return merged

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
