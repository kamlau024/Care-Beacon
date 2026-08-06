"""Embedding generation using OpenAI API."""

import time
from typing import List, Dict, Any, Optional
from openai import OpenAI
from openai import RateLimitError, APIError

from src.caching.stats_store import StatsStore
from src.storage.models import Chunk
from src.config_loader import get_config


class EmbeddingGenerator:
    """Generate embeddings for text chunks using OpenAI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        stats_store: Optional["StatsStore"] = None,
    ):
        """Initialize the embedding generator.

        Args:
            api_key: OpenAI API key (if None, loads from config)
            model: Embedding model to use (if None, loads from config)
            stats_store: Optional shared StatsStore for cross-instance counters
        """
        config = get_config()

        # Get API key
        if api_key is None:
            api_key = config.get_api_key('openai')

        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key)

        # Get model from config or use default
        self.model = model or config.get('embeddings.model', 'text-embedding-3-small')

        # Get configuration
        self.batch_size = config.get('embeddings.batch_size', 100)
        self.max_retries = config.get('embeddings.max_retries', 3)
        self.retry_delay = config.get('embeddings.retry_delay', 1.0)
        self.dimensions = config.get('embeddings.dimensions', 1536)

        # Cost tracking
        self.cost_per_1k_tokens = config.get('cost_tracking.embedding_cost_per_1k', 0.00002)
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.stats_store = stats_store or StatsStore(None)

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            Exception: If embedding generation fails after retries
        """
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(
                    input=text,
                    model=self.model
                )

                # Extract embedding
                embedding = response.data[0].embedding

                # Track usage
                tokens_used = response.usage.total_tokens
                cost = (tokens_used / 1000.0) * self.cost_per_1k_tokens
                self.total_tokens_used += tokens_used
                self.total_cost += cost
                self.stats_store.incr("embed_tokens", tokens_used)
                self.stats_store.incr_float("embed_cost", cost)

                return embedding

            except RateLimitError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"Rate limit hit, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Rate limit exceeded after {self.max_retries} retries") from e

            except APIError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"API error, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"API error after {self.max_retries} retries: {e}") from e

            except Exception as e:
                raise Exception(f"Unexpected error generating embedding: {e}") from e

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            Exception: If embedding generation fails
        """
        if not texts:
            return []

        # Limit batch size
        if len(texts) > self.batch_size:
            # Process in multiple batches
            all_embeddings = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                batch_embeddings = self.embed_batch(batch)
                all_embeddings.extend(batch_embeddings)
            return all_embeddings

        # Single batch processing
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(
                    input=texts,
                    model=self.model
                )

                # Extract embeddings in order
                embeddings = [item.embedding for item in response.data]

                # Track usage
                tokens_used = response.usage.total_tokens
                cost = (tokens_used / 1000.0) * self.cost_per_1k_tokens
                self.total_tokens_used += tokens_used
                self.total_cost += cost
                self.stats_store.incr("embed_tokens", tokens_used)
                self.stats_store.incr_float("embed_cost", cost)

                return embeddings

            except RateLimitError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"Rate limit hit, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Rate limit exceeded after {self.max_retries} retries") from e

            except APIError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"API error, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"API error after {self.max_retries} retries: {e}") from e

            except Exception as e:
                raise Exception(f"Unexpected error generating embeddings: {e}") from e

    def embed_chunks(self, chunks: List[Chunk], show_progress: bool = True) -> List[Chunk]:
        """Generate embeddings for a list of chunks.

        Args:
            chunks: List of Chunk objects
            show_progress: Whether to show progress updates

        Returns:
            List of Chunk objects with embeddings attached
        """
        if not chunks:
            return []

        # Extract texts
        texts = [chunk.text for chunk in chunks]

        # Process in batches
        all_embeddings = []
        total_batches = (len(texts) + self.batch_size - 1) // self.batch_size

        for batch_idx in range(0, len(texts), self.batch_size):
            batch_texts = texts[batch_idx:batch_idx + self.batch_size]

            if show_progress:
                current_batch = batch_idx // self.batch_size + 1
                print(f"Processing batch {current_batch}/{total_batches} ({len(batch_texts)} chunks)...")

            batch_embeddings = self.embed_batch(batch_texts)
            all_embeddings.extend(batch_embeddings)

        # Attach embeddings to chunks
        for chunk, embedding in zip(chunks, all_embeddings):
            chunk.embedding = embedding

        if show_progress:
            print(f"✅ Generated {len(all_embeddings)} embeddings")
            print(f"   Total tokens used: {self.total_tokens_used:,}")
            print(f"   Total cost: ${self.total_cost:.4f}")

        return chunks

    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about embedding generation.

        Returns:
            Dictionary with statistics
        """
        persisted = self.stats_store.get_all()
        tokens = int(persisted.get("embed_tokens", self.total_tokens_used))
        cost = persisted.get("embed_cost", self.total_cost)

        return {
            'model': self.model,
            'dimensions': self.dimensions,
            'total_tokens_used': tokens,
            'total_cost': cost,
            'cost_per_1k_tokens': self.cost_per_1k_tokens,
            'batch_size': self.batch_size
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.stats_store.reset()
