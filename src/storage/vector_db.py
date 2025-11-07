"""Vector database implementation using Chroma."""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.storage.models import Chunk, RetrievalResult
from src.config_loader import get_config


class VectorDatabase:
    """Chroma vector database for storing and retrieving embeddings."""

    def __init__(self, persist_directory: Optional[str] = None, collection_name: Optional[str] = None):
        """Initialize the vector database.

        Args:
            persist_directory: Directory to persist the database (if None, loads from config)
            collection_name: Name of the collection (if None, loads from config)
        """
        config = get_config()

        # Get configuration
        self.persist_directory = persist_directory or config.get('vector_db.persist_directory', 'data/vector_db')
        self.collection_name = collection_name or config.get('vector_db.collection_name', 'care-beacon-medical')
        self.distance_metric = config.get('vector_db.distance_metric', 'cosine')

        # Create persist directory if it doesn't exist
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        # Initialize Chroma client with telemetry disabled
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True
            )
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": self.distance_metric}
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

        # Add to collection
        self.collection.add(
            ids=[chunk.chunk_id],
            embeddings=[chunk.embedding],
            documents=[chunk.text],
            metadatas=[chunk.to_metadata()]
        )

    def add_chunks(self, chunks: List[Chunk], batch_size: int = 100, show_progress: bool = True) -> None:
        """Add multiple chunks to the database in batches.

        Args:
            chunks: List of Chunk objects with embeddings
            batch_size: Number of chunks to add per batch
            show_progress: Whether to show progress updates
        """
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

            # Prepare batch data
            ids = [c.chunk_id for c in batch]
            embeddings = [c.embedding for c in batch]
            documents = [c.text for c in batch]
            metadatas = [c.to_metadata() for c in batch]

            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )

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
            where_document: Document content filters

        Returns:
            List of RetrievalResult objects
        """
        # Query the collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=['embeddings', 'documents', 'metadatas', 'distances']
        )

        # Convert to RetrievalResult objects
        retrieval_results = []

        if not results['ids'] or not results['ids'][0]:
            return retrieval_results

        for i, chunk_id in enumerate(results['ids'][0]):
            # Extract data
            text = results['documents'][0][i]
            metadata = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            embedding = results['embeddings'][0][i] if results['embeddings'] is not None and len(results['embeddings']) > 0 and len(results['embeddings'][0]) > i else None

            # Convert distance to similarity score (1 - distance for cosine)
            similarity_score = 1.0 - distance

            # Create chunk from metadata
            chunk = Chunk.from_metadata(chunk_id, text, metadata)
            if embedding is not None:
                chunk.embedding = embedding

            # Create retrieval result
            result = RetrievalResult(
                chunk=chunk,
                similarity_score=similarity_score,
                rank=i + 1
            )
            retrieval_results.append(result)

        return retrieval_results

    def search_by_text(
        self,
        query_text: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Search using text query (requires embedding the query first).

        Note: This is a convenience method. For production use, you should
        embed the query separately and use the search() method.

        Args:
            query_text: Text query
            n_results: Number of results to return
            where: Metadata filters

        Returns:
            List of RetrievalResult objects
        """
        # This would require having an embedding generator available
        # For now, this is a placeholder that would need to be implemented
        # when integrating with the full pipeline
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
        results = self.collection.get(
            ids=[chunk_id],
            include=['embeddings', 'documents', 'metadatas']
        )

        if not results['ids']:
            return None

        # Create chunk from results
        text = results['documents'][0]
        metadata = results['metadatas'][0]
        embedding = results['embeddings'][0] if results['embeddings'] is not None and len(results['embeddings']) > 0 else None

        chunk = Chunk.from_metadata(chunk_id, text, metadata)
        if embedding is not None:
            chunk.embedding = embedding

        return chunk

    def delete_chunk(self, chunk_id: str) -> None:
        """Delete a chunk from the database.

        Args:
            chunk_id: Chunk identifier
        """
        self.collection.delete(ids=[chunk_id])

    def delete_chunks(self, chunk_ids: List[str]) -> None:
        """Delete multiple chunks from the database.

        Args:
            chunk_ids: List of chunk identifiers
        """
        if chunk_ids:
            self.collection.delete(ids=chunk_ids)

    def delete_by_article(self, article_id: str) -> None:
        """Delete all chunks from a specific article.

        Args:
            article_id: Article identifier
        """
        self.collection.delete(where={"article_id": article_id})

    def count(self) -> int:
        """Get the number of chunks in the database.

        Returns:
            Number of chunks
        """
        return self.collection.count()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the database.

        Returns:
            Dictionary with statistics
        """
        count = self.count()

        # Get sample to analyze metadata
        sample_size = min(100, count)
        if sample_size > 0:
            sample = self.collection.get(
                limit=sample_size,
                include=['metadatas']
            )

            # Count unique articles and sections
            unique_articles = len(set(m.get('article_id', '') for m in sample['metadatas']))
            unique_sections = len(set(m.get('section', '') for m in sample['metadatas']))
        else:
            unique_articles = 0
            unique_sections = 0

        return {
            'collection_name': self.collection_name,
            'total_chunks': count,
            'unique_articles_sample': unique_articles,
            'unique_sections_sample': unique_sections,
            'distance_metric': self.distance_metric,
            'persist_directory': self.persist_directory
        }

    def reset(self) -> None:
        """Delete all data from the collection.

        Warning: This cannot be undone!
        """
        # Delete the collection
        self.client.delete_collection(self.collection_name)

        # Recreate empty collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": self.distance_metric}
        )

    def peek(self, limit: int = 5) -> List[Chunk]:
        """Get a few sample chunks from the database.

        Args:
            limit: Number of samples to return

        Returns:
            List of Chunk objects
        """
        results = self.collection.get(
            limit=limit,
            include=['embeddings', 'documents', 'metadatas']
        )

        chunks = []
        for i, chunk_id in enumerate(results['ids']):
            text = results['documents'][i]
            metadata = results['metadatas'][i]
            embedding = results['embeddings'][i] if results['embeddings'] is not None and len(results['embeddings']) > i else None

            chunk = Chunk.from_metadata(chunk_id, text, metadata)
            if embedding is not None:
                chunk.embedding = embedding
            chunks.append(chunk)

        return chunks
