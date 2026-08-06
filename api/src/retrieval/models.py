"""Data models for retrieval system."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.storage.models import Chunk, RetrievalResult


@dataclass
class Query:
    """User query with metadata."""

    text: str
    """The query text"""

    filters: Optional[Dict[str, Any]] = None
    """Optional metadata filters (e.g., {"cancer_type": "Breast Cancer"})"""

    max_results: int = 10
    """Maximum number of results to return"""

    min_similarity: float = 0.0
    """Minimum similarity threshold (0.0 to 1.0)"""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the query was created"""

    query_id: Optional[str] = None
    """Optional unique identifier for the query"""


@dataclass
class RetrievedContext:
    """Retrieved context for a query.

    Contains the retrieved chunks with their relevance scores,
    ready to be used for answer generation.
    """

    query: Query
    """Original query"""

    results: List[RetrievalResult]
    """Retrieved chunks with similarity scores"""

    total_chunks: int
    """Total number of chunks retrieved"""

    retrieval_time_ms: float
    """Time taken to retrieve results (milliseconds)"""

    def get_top_k(self, k: int) -> List[RetrievalResult]:
        """Get top k results.

        Args:
            k: Number of results to return

        Returns:
            Top k results by similarity score
        """
        return self.results[:k]

    def get_above_threshold(self, threshold: float) -> List[RetrievalResult]:
        """Get all results above similarity threshold.

        Args:
            threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            Results with similarity >= threshold
        """
        return [r for r in self.results if r.similarity_score >= threshold]

    def get_by_article(self, article_id: str) -> List[RetrievalResult]:
        """Get results from a specific article.

        Args:
            article_id: Article identifier

        Returns:
            Results from the specified article
        """
        return [r for r in self.results if r.chunk.article_id == article_id]

    def get_unique_articles(self) -> List[str]:
        """Get list of unique articles in results.

        Returns:
            List of unique article IDs
        """
        return list(dict.fromkeys([r.chunk.article_id for r in self.results]))

    def get_context_text(self, max_chunks: Optional[int] = None) -> str:
        """Get combined text from all chunks for context.

        Args:
            max_chunks: Maximum number of chunks to include (None for all)

        Returns:
            Combined text from chunks
        """
        chunks_to_use = self.results[:max_chunks] if max_chunks else self.results

        context_parts = []
        for result in chunks_to_use:
            chunk = result.chunk
            context_parts.append(
                f"[Source: {chunk.article_title} - {chunk.section}]\n{chunk.text}"
            )

        return "\n\n".join(context_parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "query": {
                "text": self.query.text,
                "filters": self.query.filters,
                "max_results": self.query.max_results,
                "min_similarity": self.query.min_similarity,
                "timestamp": self.query.timestamp.isoformat(),
            },
            "total_chunks": self.total_chunks,
            "retrieval_time_ms": self.retrieval_time_ms,
            "results": [
                {
                    "rank": r.rank,
                    "similarity_score": r.similarity_score,
                    "chunk_id": r.chunk.chunk_id,
                    "article_title": r.chunk.article_title,
                    "section": r.chunk.section,
                    "text": r.chunk.text,
                    "url": r.chunk.url,
                }
                for r in self.results
            ],
        }


@dataclass
class RetrievalConfig:
    """Configuration for retrieval engine."""

    default_max_results: int = 10
    """Default maximum results to return"""

    default_min_similarity: float = 0.0
    """Default minimum similarity threshold"""

    rerank_results: bool = False
    """Whether to rerank results (future feature)"""

    include_metadata: bool = True
    """Whether to include full metadata in results"""

    cache_embeddings: bool = True
    """Whether to cache query embeddings"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "default_max_results": self.default_max_results,
            "default_min_similarity": self.default_min_similarity,
            "rerank_results": self.rerank_results,
            "include_metadata": self.include_metadata,
            "cache_embeddings": self.cache_embeddings,
        }
