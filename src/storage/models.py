"""Data models for Care-Beacon RAG system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class ArticleSection:
    """Represents a section within an article."""

    name: str
    level: int  # Header level (2 for ##, 3 for ###, etc.)
    paragraphs: List[str] = field(default_factory=list)


@dataclass
class Article:
    """Represents a parsed medical article."""

    # Metadata from frontmatter
    title: str
    url: str
    date_scraped: datetime
    breadcrumbs: List[str]
    images: List[Dict[str, str]] = field(default_factory=list)

    # Parsed content
    sections: List[ArticleSection] = field(default_factory=list)

    # Derived metadata
    article_id: Optional[str] = None
    cancer_type: Optional[str] = None
    specialty: Optional[str] = None
    source: str = "BC Cancer"
    file_path: Optional[str] = None  # Store file path for uniqueness

    def __post_init__(self):
        """Generate article_id from title, source, and file path if not provided."""
        if self.article_id is None:
            # Create source prefix (lowercase, no spaces)
            source_prefix = self.source.lower().replace(' ', '-').replace('/', '-')
            # Create slug from title
            title_slug = self.title.lower().replace(' ', '-').replace('/', '-')

            # If file_path is provided, use it to ensure uniqueness
            # This handles cases where same title appears in different folders
            if self.file_path:
                # Get a hash of the file path to keep ID reasonable length
                import hashlib
                path_hash = hashlib.md5(self.file_path.encode()).hexdigest()[:8]
                self.article_id = f"{source_prefix}_{title_slug}_{path_hash}"
            else:
                # Fallback to source + title (for backward compatibility)
                self.article_id = f"{source_prefix}_{title_slug}"

        # Extract cancer type from breadcrumbs if available
        if self.cancer_type is None and len(self.breadcrumbs) >= 3:
            # Usually: ["Health Info", "Types Of Cancer", "Specific Cancer"]
            if "Types Of Cancer" in self.breadcrumbs:
                idx = self.breadcrumbs.index("Types Of Cancer")
                if idx + 1 < len(self.breadcrumbs):
                    self.cancer_type = self.breadcrumbs[idx + 1]

    def get_all_paragraphs(self) -> List[str]:
        """Get all paragraphs from all sections."""
        paragraphs = []
        for section in self.sections:
            paragraphs.extend(section.paragraphs)
        return paragraphs

    def get_total_paragraph_count(self) -> int:
        """Get total number of paragraphs across all sections."""
        return sum(len(section.paragraphs) for section in self.sections)


@dataclass
class Chunk:
    """Represents a text chunk for embedding and retrieval."""

    # Unique identifier
    chunk_id: str

    # Content
    text: str

    # Article metadata
    article_id: str
    article_title: str
    url: str
    breadcrumbs: List[str]
    cancer_type: Optional[str] = None
    source: str = "BC Cancer"
    date_scraped: Optional[datetime] = None

    # Section context
    section: str = ""
    paragraph_index: int = 0
    total_paragraphs: int = 0

    # Embedding (populated after generation)
    embedding: Optional[List[float]] = None

    def to_metadata(self) -> Dict[str, Any]:
        """Convert chunk to metadata dictionary for vector database.

        Returns:
            Dictionary with metadata fields
        """
        metadata = {
            "chunk_id": self.chunk_id,
            "article_id": self.article_id,
            "article_title": self.article_title,
            "url": self.url,
            "breadcrumbs": ",".join(str(b) for b in self.breadcrumbs),
            "source": self.source,
            "section": self.section,
            "paragraph_index": self.paragraph_index,
            "total_paragraphs": self.total_paragraphs,
        }

        if self.cancer_type:
            metadata["cancer_type"] = self.cancer_type

        if self.date_scraped:
            metadata["date_scraped"] = self.date_scraped.isoformat()

        return metadata

    @classmethod
    def from_metadata(cls, chunk_id: str, text: str, metadata: Dict[str, Any]) -> "Chunk":
        """Create a Chunk from metadata dictionary.

        Args:
            chunk_id: Unique chunk identifier
            text: Chunk text content
            metadata: Metadata dictionary

        Returns:
            Chunk instance
        """
        breadcrumbs = metadata.get("breadcrumbs", "").split(",")

        date_scraped = None
        if "date_scraped" in metadata:
            date_scraped = datetime.fromisoformat(metadata["date_scraped"])

        return cls(
            chunk_id=chunk_id,
            text=text,
            article_id=metadata.get("article_id", ""),
            article_title=metadata.get("article_title", ""),
            url=metadata.get("url", ""),
            breadcrumbs=breadcrumbs,
            cancer_type=metadata.get("cancer_type"),
            source=metadata.get("source", "BC Cancer"),
            date_scraped=date_scraped,
            section=metadata.get("section", ""),
            paragraph_index=metadata.get("paragraph_index", 0),
            total_paragraphs=metadata.get("total_paragraphs", 0),
        )


@dataclass
class RetrievalResult:
    """Represents a retrieved chunk with similarity score."""

    chunk: Chunk
    similarity_score: float
    rank: int = 0


@dataclass
class QueryResponse:
    """Represents the final response to a user query."""

    query: str
    answer: str
    sources: List[RetrievalResult]
    processing_time: float
    cached: bool = False
    cost: Optional[Dict[str, float]] = None

    def format_citations(self) -> str:
        """Format the answer with citation list.

        Returns:
            Formatted answer with references
        """
        output = self.answer + "\n\n"

        if self.sources:
            output += "**References:**\n\n"
            for i, result in enumerate(self.sources, 1):
                chunk = result.chunk
                output += f"[{i}] \"{chunk.article_title}\" - {chunk.source}\n"
                output += f"    Section: {chunk.section}, Paragraph {chunk.paragraph_index}\n"
                output += f"    URL: {chunk.url}\n\n"

        return output
