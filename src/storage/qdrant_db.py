"""Vector database implementation using Qdrant Cloud."""

import os
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest
)

from src.storage.models import Chunk, RetrievalResult
from src.config_loader import get_config


class QdrantVectorDatabase:
    """Qdrant Cloud vector database for storing and retrieving embeddings."""

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None
    ):
        """Initialize the Qdrant vector database.

        Args:
            url: Qdrant Cloud URL (if None, reads from config or QDRANT_URL env var)
            api_key: Qdrant API key (if None, reads from config or QDRANT_API_KEY env var)
            collection_name: Name of the collection (if None, loads from config)
        """
        config = get_config()

        # Get configuration
        self.url = url or config.get('vector_db.qdrant_url') or os.getenv('QDRANT_URL')
        self.api_key = api_key or config.get('vector_db.qdrant_api_key') or os.getenv('QDRANT_API_KEY')
        self.collection_name = collection_name or config.get('vector_db.collection_name', 'care-beacon-medical')
        self.distance_metric = config.get('vector_db.distance_metric', 'cosine')
        self.vector_size = config.get('embeddings.dimensions', 1536)

        if not self.url:
            raise ValueError("Qdrant URL not configured. Set QDRANT_URL environment variable or in config.")
        if not self.api_key:
            raise ValueError("Qdrant API key not configured. Set QDRANT_API_KEY environment variable or in config.")

        # Initialize Qdrant client with extended timeout for large batch operations
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=300,  # 5 minutes timeout for large batch operations
        )

        # Map distance metric to Qdrant Distance enum
        distance_map = {
            'cosine': Distance.COSINE,
            'l2': Distance.EUCLID,
            'ip': Distance.DOT
        }
        self.qdrant_distance = distance_map.get(self.distance_metric, Distance.COSINE)

        # Create collection if it doesn't exist
        self._ensure_collection_exists()

    def _ensure_collection_exists(self) -> None:
        """Ensure the collection exists, create if it doesn't."""
        collection_exists = False
        try:
            # Try to get the collection
            self.client.get_collection(collection_name=self.collection_name)
            collection_exists = True
        except Exception:
            # Collection doesn't exist, try to create it
            try:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=self.qdrant_distance
                    ),
                )
                collection_exists = True
            except Exception as e:
                # If creation fails because collection already exists (race condition), that's OK
                if "already exists" not in str(e).lower():
                    raise  # Re-raise if it's a different error
                collection_exists = True

        # Create payload indexes for commonly filtered fields
        if collection_exists:
            self._ensure_payload_indexes()

    def _ensure_payload_indexes(self) -> None:
        """Create payload indexes for commonly filtered fields."""
        from qdrant_client.models import PayloadSchemaType

        # Index fields that are commonly used for filtering
        index_fields = {
            "source": PayloadSchemaType.KEYWORD,
            "article_id": PayloadSchemaType.KEYWORD,
            "cancer_type": PayloadSchemaType.KEYWORD,
        }

        for field_name, field_type in index_fields.items():
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type
                )
            except Exception as e:
                # Index might already exist, that's OK
                if "already exists" not in str(e).lower() and "index with name" not in str(e).lower():
                    # Log warning but don't fail
                    pass

    def _chunk_to_point(self, chunk: Chunk) -> PointStruct:
        """Convert a Chunk to a Qdrant PointStruct.

        Args:
            chunk: Chunk object

        Returns:
            PointStruct for Qdrant
        """
        if chunk.embedding is None:
            raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")

        # Use hash of chunk_id as numeric ID (Qdrant requires valid IDs)
        # String IDs don't support special characters like &, so we use numeric hash
        import hashlib
        # Create a stable hash and convert to positive integer within Qdrant's range
        hash_bytes = hashlib.sha256(chunk.chunk_id.encode()).digest()
        # Take first 8 bytes and convert to int (unsigned 64-bit max)
        point_id = int.from_bytes(hash_bytes[:8], 'big') % (2**63 - 1)

        # Create payload with text and metadata
        # Store original chunk_id in payload for retrieval
        payload = {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            **chunk.to_metadata()
        }

        return PointStruct(
            id=point_id,
            vector=chunk.embedding,
            payload=payload
        )

    def add_chunk(self, chunk: Chunk) -> None:
        """Add a single chunk to the database.

        Args:
            chunk: Chunk object with embedding

        Raises:
            ValueError: If chunk doesn't have an embedding
        """
        if chunk.embedding is None:
            raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")

        point = self._chunk_to_point(chunk)

        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )

    def add_chunks(self, chunks: List[Chunk], batch_size: int = 100, show_progress: bool = True) -> None:
        """Add multiple chunks to the database in batches.

        Args:
            chunks: List of Chunk objects with embeddings
            batch_size: Number of chunks to add per batch
            show_progress: Whether to show progress updates
        """
        import time

        if not chunks:
            return

        # Filter out chunks without embeddings
        chunks_with_embeddings = [c for c in chunks if c.embedding is not None]

        if len(chunks_with_embeddings) < len(chunks):
            missing = len(chunks) - len(chunks_with_embeddings)
            print(f"⚠️  Skipping {missing} chunks without embeddings")

        if not chunks_with_embeddings:
            print("⚠️  No chunks with embeddings to add")
            return

        # Process in batches
        total_batches = (len(chunks_with_embeddings) + batch_size - 1) // batch_size

        for i in range(0, len(chunks_with_embeddings), batch_size):
            batch = chunks_with_embeddings[i:i + batch_size]

            if show_progress:
                batch_num = i // batch_size + 1
                print(f"Adding batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

            # Convert chunks to points
            points = [self._chunk_to_point(chunk) for chunk in batch]

            # Upsert to Qdrant with retry logic
            max_retries = 3
            retry_delay = 5  # seconds

            for attempt in range(max_retries):
                try:
                    self.client.upsert(
                        collection_name=self.collection_name,
                        points=points
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                            print(f"  ⚠️  Timeout error, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                            time.sleep(wait_time)
                        else:
                            # Non-timeout error, re-raise immediately
                            raise
                    else:
                        # Final attempt failed, re-raise
                        print(f"  ❌ Failed after {max_retries} attempts")
                        raise

        if show_progress:
            print(f"✅ Added {len(chunks_with_embeddings)} chunks to database")

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Search for similar chunks using vector similarity.

        Args:
            query_embedding: Query vector
            n_results: Number of results to return
            where: Metadata filters (e.g., {"cancer_type": "Breast Cancer"})
            where_document: Document content filters (not fully supported in Qdrant)

        Returns:
            List of RetrievalResult objects
        """
        # Build filter from where clause
        query_filter = None
        if where:
            # Convert ChromaDB-style where clause to Qdrant filter
            must_conditions = []

            for key, value in where.items():
                if key == "$and":
                    # Handle $and from ChromaDB format
                    for condition in value:
                        for k, v in condition.items():
                            must_conditions.append(
                                FieldCondition(
                                    key=k,
                                    match=MatchValue(value=v)
                                )
                            )
                else:
                    must_conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )

            if must_conditions:
                query_filter = Filter(must=must_conditions)

        # Search in Qdrant
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=n_results,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=True
        )

        # Convert to RetrievalResult objects
        retrieval_results = []

        for i, result in enumerate(search_results):
            # Extract data from Qdrant result
            chunk_id = result.payload.get('chunk_id', str(result.id))
            text = result.payload.get('text', '')
            similarity_score = result.score  # Qdrant returns similarity score directly

            # Create metadata dict (exclude text and chunk_id as they're separate)
            metadata = {k: v for k, v in result.payload.items() if k not in ['text', 'chunk_id']}

            # Create chunk from result
            chunk = Chunk.from_metadata(chunk_id, text, metadata)
            if result.vector is not None:
                chunk.embedding = result.vector

            # Create retrieval result
            retrieval_result = RetrievalResult(
                chunk=chunk,
                similarity_score=similarity_score,
                rank=i + 1
            )
            retrieval_results.append(retrieval_result)

        return retrieval_results

    def search_by_text(
        self,
        query_text: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Search using text query (requires embedding the query first).

        Args:
            query_text: Text query
            n_results: Number of results to return
            where: Metadata filters

        Returns:
            List of RetrievalResult objects
        """
        raise NotImplementedError(
            "search_by_text requires an embedding generator. "
            "Use search() with a pre-computed query embedding instead."
        )

    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """Get a specific chunk by ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            Chunk object or None if not found
        """
        try:
            # Convert chunk_id to numeric point_id
            import hashlib
            hash_bytes = hashlib.sha256(chunk_id.encode()).digest()
            point_id = int.from_bytes(hash_bytes[:8], 'big') % (2**63 - 1)

            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_payload=True,
                with_vectors=True
            )

            if not result:
                return None

            point = result[0]
            text = point.payload.get('text', '')
            # Get original chunk_id from payload
            original_chunk_id = point.payload.get('chunk_id', chunk_id)
            metadata = {k: v for k, v in point.payload.items() if k not in ['text', 'chunk_id']}

            chunk = Chunk.from_metadata(original_chunk_id, text, metadata)
            if point.vector is not None:
                chunk.embedding = point.vector

            return chunk

        except Exception:
            return None

    def delete_chunk(self, chunk_id: str) -> None:
        """Delete a chunk from the database.

        Args:
            chunk_id: Chunk identifier
        """
        # Convert chunk_id to numeric point_id
        import hashlib
        hash_bytes = hashlib.sha256(chunk_id.encode()).digest()
        point_id = int.from_bytes(hash_bytes[:8], 'big') % (2**63 - 1)

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=[point_id]
        )

    def delete_chunks(self, chunk_ids: List[str]) -> None:
        """Delete multiple chunks from the database.

        Args:
            chunk_ids: List of chunk identifiers
        """
        if chunk_ids:
            # Convert all chunk_ids to numeric point_ids
            import hashlib
            point_ids = []
            for chunk_id in chunk_ids:
                hash_bytes = hashlib.sha256(chunk_id.encode()).digest()
                point_id = int.from_bytes(hash_bytes[:8], 'big') % (2**63 - 1)
                point_ids.append(point_id)

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=point_ids
            )

    def delete_by_article(self, article_id: str) -> None:
        """Delete all chunks from a specific article.

        Args:
            article_id: Article identifier
        """
        # Delete by filter
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="article_id",
                        match=MatchValue(value=article_id)
                    )
                ]
            )
        )

    def count(self) -> int:
        """Get the number of chunks in the database.

        Returns:
            Number of chunks
        """
        collection_info = self.client.get_collection(collection_name=self.collection_name)
        return collection_info.points_count

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the database.

        Returns:
            Dictionary with statistics
        """
        collection_info = self.client.get_collection(collection_name=self.collection_name)
        count = collection_info.points_count

        # Get sample to analyze metadata
        sample_size = min(100, count)
        stats = {
            'collection_name': self.collection_name,
            'total_chunks': count,
            'unique_articles_sample': 0,
            'unique_sections_sample': 0,
            'distance_metric': self.distance_metric,
            'qdrant_url': self.url,
            'vector_size': self.vector_size
        }

        if sample_size > 0:
            # Scroll through sample to get metadata
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=sample_size,
                with_payload=True,
                with_vectors=False
            )

            points = scroll_result[0]

            # Count unique articles and sections
            unique_articles = len(set(p.payload.get('article_id', '') for p in points))
            unique_sections = len(set(p.payload.get('section', '') for p in points))

            stats['unique_articles_sample'] = unique_articles
            stats['unique_sections_sample'] = unique_sections

        return stats

    def reset(self) -> None:
        """Delete all data from the collection.

        Warning: This cannot be undone!
        """
        # Delete the collection
        self.client.delete_collection(collection_name=self.collection_name)

        # Recreate empty collection
        self._ensure_collection_exists()

    def peek(self, limit: int = 5) -> List[Chunk]:
        """Get a few sample chunks from the database.

        Args:
            limit: Number of samples to return

        Returns:
            List of Chunk objects
        """
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=True
        )

        points = scroll_result[0]

        chunks = []
        for point in points:
            chunk_id = point.payload.get('chunk_id', str(point.id))
            text = point.payload.get('text', '')
            metadata = {k: v for k, v in point.payload.items() if k not in ['text', 'chunk_id']}

            chunk = Chunk.from_metadata(chunk_id, text, metadata)
            if point.vector is not None:
                chunk.embedding = point.vector
            chunks.append(chunk)

        return chunks
