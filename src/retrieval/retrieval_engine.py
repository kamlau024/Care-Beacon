"""Retrieval engine for querying the vector database.

This module provides the main interface for retrieving relevant medical
information from the vector database based on user queries.
"""

import time
from typing import List, Dict, Any, Optional

from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase
from src.retrieval.models import Query, RetrievedContext, RetrievalConfig
from src.storage.models import RetrievalResult
from src.config_loader import get_config


class RetrievalEngine:
    """Engine for retrieving relevant medical information from queries.

    This class coordinates between:
    - Embedding generation (query -> vector)
    - Vector database search (vector -> relevant chunks)
    - Result processing and filtering

    Example:
        >>> engine = RetrievalEngine()
        >>> query = Query(text="What are symptoms of breast cancer?", max_results=5)
        >>> context = engine.retrieve(query)
        >>> for result in context.results:
        ...     print(f"{result.chunk.article_title}: {result.similarity_score:.4f}")
    """

    def __init__(
        self,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        vector_db: Optional[VectorDatabase] = None,
        config: Optional[RetrievalConfig] = None,
    ):
        """Initialize the retrieval engine.

        Args:
            embedding_generator: Optional EmbeddingGenerator instance
            vector_db: Optional VectorDatabase instance
            config: Optional retrieval configuration
        """
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.vector_db = vector_db or VectorDatabase()
        self.config = config or self._load_config()

    def _load_config(self) -> RetrievalConfig:
        """Load retrieval configuration from config file.

        Returns:
            RetrievalConfig instance
        """
        config = get_config()
        retrieval_config = config.get("retrieval", {})

        return RetrievalConfig(
            default_max_results=retrieval_config.get("top_k", 10),
            default_min_similarity=retrieval_config.get("min_similarity_threshold", 0.0),
            rerank_results=retrieval_config.get("rerank_results", False),
            include_metadata=retrieval_config.get("include_metadata", True),
            cache_embeddings=retrieval_config.get("cache_query_embeddings", True),
        )

    def retrieve(self, query: Query) -> RetrievedContext:
        """Retrieve relevant chunks for a query.

        This is the main retrieval method. It:
        1. Generates embedding for the query text
        2. Searches the vector database
        3. Filters results by similarity threshold
        4. Returns structured context

        Args:
            query: Query object with text and optional filters

        Returns:
            RetrievedContext with retrieved chunks and metadata
        """
        start_time = time.time()

        # Generate query embedding
        query_embedding = self.embedding_generator.embed_text(query.text)

        # Search vector database
        results = self.vector_db.search(
            query_embedding=query_embedding,
            n_results=query.max_results,
            where=query.filters,
        )

        # Filter by minimum similarity if specified
        if query.min_similarity > 0.0:
            results = [r for r in results if r.similarity_score >= query.min_similarity]

        # Calculate retrieval time
        retrieval_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Create and return context
        return RetrievedContext(
            query=query,
            results=results,
            total_chunks=len(results),
            retrieval_time_ms=retrieval_time,
        )

    def retrieve_text(
        self,
        query_text: str,
        max_results: Optional[int] = None,
        min_similarity: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievedContext:
        """Convenience method to retrieve using just query text.

        Args:
            query_text: The query text
            max_results: Maximum number of results (uses default if None)
            min_similarity: Minimum similarity threshold (uses default if None)
            filters: Optional metadata filters

        Returns:
            RetrievedContext with retrieved chunks
        """
        query = Query(
            text=query_text,
            max_results=max_results or self.config.default_max_results,
            min_similarity=min_similarity or self.config.default_min_similarity,
            filters=filters,
        )

        return self.retrieve(query)

    def retrieve_for_cancer_type(
        self,
        query_text: str,
        cancer_type: str,
        max_results: Optional[int] = None,
    ) -> RetrievedContext:
        """Retrieve results filtered by cancer type.

        Args:
            query_text: The query text
            cancer_type: Cancer type to filter by (e.g., "Breast Cancer")
            max_results: Maximum number of results

        Returns:
            RetrievedContext with results filtered by cancer type
        """
        return self.retrieve_text(
            query_text=query_text,
            max_results=max_results,
            filters={"cancer_type": cancer_type},
        )

    def retrieve_for_article(
        self,
        query_text: str,
        article_id: str,
        max_results: Optional[int] = None,
    ) -> RetrievedContext:
        """Retrieve results filtered by article.

        Args:
            query_text: The query text
            article_id: Article ID to filter by (e.g., "breast-cancer")
            max_results: Maximum number of results

        Returns:
            RetrievedContext with results filtered by article
        """
        return self.retrieve_text(
            query_text=query_text,
            max_results=max_results,
            filters={"article_id": article_id},
        )

    def get_similar_chunks(
        self,
        chunk_id: str,
        max_results: int = 5,
    ) -> List[RetrievalResult]:
        """Find chunks similar to a given chunk.

        Useful for "related content" features.

        Args:
            chunk_id: ID of the chunk to find similar chunks for
            max_results: Maximum number of similar chunks to return

        Returns:
            List of similar chunks (excluding the original chunk)
        """
        # Get the chunk
        chunk = self.vector_db.get_chunk(chunk_id)
        if not chunk or not chunk.embedding:
            return []

        # Search using the chunk's embedding
        results = self.vector_db.search(
            query_embedding=chunk.embedding,
            n_results=max_results + 1,  # +1 because the chunk itself will be included
        )

        # Filter out the original chunk
        return [r for r in results if r.chunk.chunk_id != chunk_id]

    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about embedding generation.

        Returns:
            Dictionary with embedding statistics
        """
        return self.embedding_generator.get_embedding_stats()

    def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector database.

        Returns:
            Dictionary with database statistics
        """
        return self.vector_db.get_stats()

    def get_config_dict(self) -> Dict[str, Any]:
        """Get current retrieval configuration.

        Returns:
            Dictionary with configuration
        """
        return self.config.to_dict()
