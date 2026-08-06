"""Retrieval engine for querying the vector database.

This module provides the main interface for retrieving relevant medical
information from the vector database based on user queries.
"""

import time
from typing import List, Dict, Any, Optional
from loguru import logger

from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import create_vector_database
from src.retrieval.models import Query, RetrievedContext, RetrievalConfig
from src.storage.models import RetrievalResult
from src.retrieval.reranker import LLMReranker
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
        vector_db: Optional[Any] = None,
        config: Optional[RetrievalConfig] = None,
        reranker: Optional[LLMReranker] = None,
    ):
        """Initialize the retrieval engine.

        Args:
            embedding_generator: Optional EmbeddingGenerator instance
            vector_db: Optional Qdrant vector database instance
            config: Optional retrieval configuration
            reranker: Optional LLMReranker instance for re-ranking results
        """
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.vector_db = vector_db or create_vector_database()
        self.config = config or self._load_config()
        self.reranker = reranker or (LLMReranker() if self.config.rerank_results else None)

        # Log initialization
        if self.reranker:
            logger.info("✅ RetrievalEngine initialized with LLM re-ranking ENABLED")
        else:
            logger.info("ℹ️  RetrievalEngine initialized with re-ranking DISABLED")

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

        # Retrieve more results if re-ranking is enabled (retrieve 6x to ensure completeness)
        initial_n_results = query.max_results * 6 if self.reranker else query.max_results

        logger.info(
            f"🔍 Vector search: fetching {initial_n_results} results "
            f"(reranker={'enabled' if self.reranker else 'disabled'})"
        )
        results = self.vector_db.search(
            query_embedding=query_embedding,
            n_results=initial_n_results,
            where=query.filters,
        )
        logger.info(f"📊 Vector search returned {len(results)} results")

        # When re-ranking is enabled, skip or loosen pre-filter
        # Re-ranked scores are more accurate than raw vector similarity
        if self.reranker and len(results) > 0:
            # Apply loose pre-filter to keep more candidates for re-ranking
            # Use min_similarity / 2 or minimum 0.3 to keep reasonable candidates
            pre_filter_threshold = max(0.3, query.min_similarity / 2) if query.min_similarity > 0.0 else 0.0
            if pre_filter_threshold > 0.0:
                before_filter = len(results)
                results = [r for r in results if r.similarity_score >= pre_filter_threshold]
                logger.info(f"🔽 Pre-filter for re-ranking (threshold={pre_filter_threshold:.2f}): {before_filter} → {len(results)} results")

            # Re-rank using LLM - re-rank ALL candidates, don't limit yet
            logger.info(f"🎯 Calling reranker with {len(results)} results, will re-rank all candidates")
            results = self.reranker.rerank(
                query=query.text,
                results=results,
                top_k=len(results)  # Re-rank all candidates, filter will select best ones
            )
            logger.info(f"✅ Re-ranking returned {len(results)} results")

            # Apply strict filter AFTER re-ranking (on re-ranked scores)
            if query.min_similarity > 0.0:
                before_filter = len(results)
                results = [r for r in results if r.similarity_score >= query.min_similarity]
                logger.info(f"🔽 Post-rerank filter (min_similarity={query.min_similarity}): {before_filter} → {len(results)} results")

            # When re-ranking is enabled, return ALL results that pass threshold (no limit)
            # This ensures completeness - if 6 chunks are relevant, return all 6
            logger.info(f"✅ Returning all {len(results)} results that passed threshold (no limit applied)")
        else:
            # No re-ranking, apply filter directly to vector scores
            if query.min_similarity > 0.0:
                before_filter = len(results)
                results = [r for r in results if r.similarity_score >= query.min_similarity]
                logger.info(f"🔽 Filtered by min_similarity={query.min_similarity}: {before_filter} → {len(results)} results")

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
        # Debug: Log what values we're using
        resolved_min_similarity = min_similarity if min_similarity is not None else self.config.default_min_similarity
        logger.info(f"🔧 retrieve_text: min_similarity={min_similarity} (passed) → using {resolved_min_similarity} (config default={self.config.default_min_similarity})")

        query = Query(
            text=query_text,
            max_results=max_results if max_results is not None else self.config.default_max_results,
            min_similarity=resolved_min_similarity,
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
