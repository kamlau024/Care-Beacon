"""Data models for answer generation."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.retrieval.models import RetrievedContext


@dataclass
class Citation:
    """A citation reference to a source chunk."""

    chunk_id: str
    """Unique identifier for the chunk"""

    article_title: str
    """Title of the source article"""

    section: str
    """Section within the article"""

    url: str
    """URL to the source article"""

    paragraph_index: int
    """Index of the paragraph within the article"""

    text_excerpt: str
    """Excerpt of text being cited (for verification)"""

    similarity_score: float = 0.0
    """Similarity/confidence score (0-1) from vector search"""

    source: str = "BC Cancer"
    """Information source (e.g., BC Cancer, Canadian Cancer Society)"""

    def to_reference(self) -> str:
        """Format as a readable reference.

        Returns:
            Formatted reference string
        """
        return f"{self.article_title} - {self.section} (paragraph {self.paragraph_index + 1})"

    def to_markdown_link(self) -> str:
        """Format as a markdown link.

        Returns:
            Markdown formatted link
        """
        return f"[{self.article_title} - {self.section}]({self.url})"


@dataclass
class GeneratedAnswer:
    """Generated answer with citations and metadata."""

    query: str
    """Original user query"""

    answer: str
    """Generated answer text"""

    citations: List[Citation]
    """List of citations used in the answer"""

    context_used: RetrievedContext
    """Retrieved context that was used"""

    model: str
    """LLM model used for generation"""

    tokens_used: Dict[str, int]
    """Token usage (input, output, total)"""

    cost: float
    """Cost of generation in USD"""

    generation_time_ms: float
    """Time taken to generate answer (milliseconds)"""

    confidence: Optional[float] = None
    """Confidence score (0-1) if available"""

    disclaimer: Optional[str] = None
    """Medical disclaimer if included"""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the answer was generated"""

    def get_formatted_answer(self, include_disclaimer: bool = True) -> str:
        """Get formatted answer with citations.

        Args:
            include_disclaimer: Whether to include medical disclaimer

        Returns:
            Formatted answer with citations and disclaimer
        """
        parts = [self.answer]

        # Add citations
        if self.citations:
            parts.append("\n\n**Sources:**")
            for i, citation in enumerate(self.citations, 1):
                parts.append(f"{i}. {citation.to_reference()}")

        # Add disclaimer
        if include_disclaimer and self.disclaimer:
            parts.append(f"\n\n*{self.disclaimer}*")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "query": self.query,
            "answer": self.answer,
            "citations": [
                {
                    "article_title": c.article_title,
                    "section": c.section,
                    "url": c.url,
                    "paragraph_index": c.paragraph_index,
                    "similarity_score": c.similarity_score,
                }
                for c in self.citations
            ],
            "model": self.model,
            "tokens_used": self.tokens_used,
            "cost": self.cost,
            "generation_time_ms": self.generation_time_ms,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class GenerationConfig:
    """Configuration for answer generation."""

    model: str = "gpt-4o-mini"
    """LLM model to use"""

    max_tokens: int = 1000
    """Maximum tokens in response"""

    temperature: float = 0.1
    """Temperature (0=focused, 1=creative)"""

    max_context_chunks: int = 5
    """Maximum chunks to include in context"""

    require_citations: bool = True
    """Whether to require citations in answers"""

    include_disclaimer: bool = True
    """Whether to include medical disclaimer"""

    disclaimer_text: str = (
        "This information is for educational purposes only. "
        "It is not a substitute for professional medical advice, diagnosis, or treatment. "
        "Please consult with a healthcare provider for medical advice."
    )
    """Default disclaimer text"""

    max_retries: int = 3
    """Maximum retry attempts"""

    timeout: int = 30
    """Timeout in seconds"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "max_context_chunks": self.max_context_chunks,
            "require_citations": self.require_citations,
            "include_disclaimer": self.include_disclaimer,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
        }
