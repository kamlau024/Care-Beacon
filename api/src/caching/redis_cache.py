"""Redis cache client for query results."""

import os
import json
import hashlib
import time
from typing import Optional, Dict, Any
import redis
from redis.exceptions import RedisError, ConnectionError

from src.caching.models import CacheConfig, CacheStats
from src.caching.stats_store import StatsStore
from src.generation.models import GeneratedAnswer
from src.config_loader import get_config


class RedisCache:
    """Redis-based cache for query results.

    Provides caching for generated answers to reduce API costs
    and improve response times for repeated queries.
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize Redis cache.

        Args:
            config: Optional cache configuration
        """
        self.config = config or self._load_config()
        self.stats = CacheStats()

        # Initialize Redis client
        if self.config.enabled:
            try:
                if self.config.url:
                    # A full connection URL was supplied (e.g. REDIS_URL). Hand it
                    # to from_url() unmodified so the scheme is honoured -- Upstash
                    # (used in production) is rediss:// (TLS) only, and
                    # reassembling host/port/password by hand silently drops that.
                    self.client = redis.Redis.from_url(
                        self.config.url,
                        socket_timeout=self.config.timeout,
                        socket_connect_timeout=self.config.timeout,
                        decode_responses=True,  # Automatically decode to strings
                    )
                else:
                    # No URL: connect with discrete host/port (local development).
                    self.client = redis.Redis(
                        host=self.config.host,
                        port=self.config.port,
                        db=self.config.db,
                        password=self.config.password,
                        socket_timeout=self.config.timeout,
                        socket_connect_timeout=self.config.timeout,
                        decode_responses=True,  # Automatically decode to strings
                    )
                # Test connection
                self.client.ping()
                self.enabled = True
            except (RedisError, ConnectionError) as e:
                print(f"⚠️  Redis connection failed: {e}")
                print("   Cache will be disabled. Queries will always hit the API.")
                self.enabled = False
                self.client = None
        else:
            self.enabled = False
            self.client = None

        # Cumulative counters shared across instances
        self.stats_store = StatsStore(self.client, self.config.key_prefix)

    def _load_config(self) -> CacheConfig:
        """Load cache configuration.

        Checks environment variables first, then falls back to config file.
        This allows Docker and cloud environment variables to override config.yaml.

        Returns:
            CacheConfig instance
        """
        config = get_config()
        cache_config = config.get("cache", {})

        # Check for REDIS_URL first (used by Upstash, Render, Heroku, etc.)
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            # Parse the URL for the informational host/port/db/password fields
            # below (used for local visibility/logging). The connection itself
            # is opened from the raw URL (see __init__) so the scheme -- notably
            # rediss:// for TLS-only providers like Upstash -- is never lost.
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            db = int(parsed.path.lstrip("/")) if parsed.path and parsed.path != "/" else 0
            password = parsed.password
        else:
            # Fall back to individual environment variables or config
            host = os.getenv("REDIS_HOST", cache_config.get("redis_host", "localhost"))
            port = int(os.getenv("REDIS_PORT", cache_config.get("redis_port", 6379)))
            db = int(os.getenv("REDIS_DB", cache_config.get("redis_db", 0)))
            password = os.getenv("REDIS_PASSWORD", cache_config.get("redis_password"))

        return CacheConfig(
            enabled=cache_config.get("enabled", True),
            host=host,
            port=port,
            db=db,
            password=password,
            ttl_seconds=cache_config.get("ttl_seconds", 3600),
            key_prefix=cache_config.get("key_prefix", "care_beacon:"),
            max_retries=cache_config.get("max_retries", 3),
            timeout=cache_config.get("timeout", 5),
            url=redis_url,
        )

    def _generate_cache_key(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
        min_similarity: Optional[float] = None,
    ) -> str:
        """Generate a unique cache key for a query.

        Creates a hash of the query parameters to use as cache key.

        Args:
            question: User question
            filters: Optional metadata filters
            max_results: Maximum results to retrieve
            min_similarity: Minimum similarity threshold

        Returns:
            Cache key string
        """
        # Create a canonical representation of the query
        query_dict = {
            "question": question.strip().lower(),  # Normalize
            "filters": filters or {},
            "max_results": max_results,
            "min_similarity": min_similarity,
        }

        # Convert to JSON string (sorted for consistency)
        query_str = json.dumps(query_dict, sort_keys=True)

        # Hash to create fixed-length key
        query_hash = hashlib.sha256(query_str.encode()).hexdigest()

        # Add prefix
        return f"{self.config.key_prefix}answer:{query_hash}"

    def get(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
        min_similarity: Optional[float] = None,
    ) -> Optional[GeneratedAnswer]:
        """Get cached answer if available.

        Args:
            question: User question
            filters: Optional metadata filters
            max_results: Maximum results to retrieve
            min_similarity: Minimum similarity threshold

        Returns:
            Cached GeneratedAnswer if found, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        self.stats.total_queries += 1
        self.stats_store.incr("cache_queries")

        try:
            cache_key = self._generate_cache_key(question, filters, max_results, min_similarity)
            cached_data = self.client.get(cache_key)

            if cached_data:
                # Cache hit!
                self.stats.cache_hits += 1
                self.stats_store.incr("cache_hits")

                # Deserialize
                answer_dict = json.loads(cached_data)

                # Reconstruct GeneratedAnswer from cached data
                # Note: We'll store a simplified version in cache
                return self._deserialize_answer(answer_dict)

            else:
                # Cache miss
                self.stats.cache_misses += 1
                self.stats_store.incr("cache_misses")
                return None

        except (RedisError, json.JSONDecodeError) as e:
            self.stats.cache_errors += 1
            self.stats_store.incr("cache_errors")
            print(f"⚠️  Cache get error: {e}")
            return None

    def set(
        self,
        question: str,
        answer: GeneratedAnswer,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
        min_similarity: Optional[float] = None,
    ):
        """Store answer in cache.

        Args:
            question: User question
            answer: Generated answer to cache
            filters: Optional metadata filters
            max_results: Maximum results used
            min_similarity: Minimum similarity threshold used
        """
        if not self.enabled or not self.client:
            return

        try:
            cache_key = self._generate_cache_key(question, filters, max_results, min_similarity)

            # Serialize answer to JSON
            answer_dict = self._serialize_answer(answer)
            cached_data = json.dumps(answer_dict)

            # Store with TTL
            self.client.setex(
                cache_key,
                self.config.ttl_seconds,
                cached_data,
            )

        except (RedisError, TypeError) as e:
            self.stats.cache_errors += 1
            self.stats_store.incr("cache_errors")
            print(f"⚠️  Cache set error: {e}")

    def _serialize_answer(self, answer: GeneratedAnswer) -> Dict[str, Any]:
        """Serialize GeneratedAnswer for caching.

        We store a simplified version without the full RetrievedContext
        to reduce cache size.

        Args:
            answer: GeneratedAnswer to serialize

        Returns:
            Dictionary suitable for JSON serialization
        """
        return {
            "query": answer.query,
            "answer": answer.answer,
            "citations": [
                {
                    "chunk_id": c.chunk_id,
                    "article_title": c.article_title,
                    "section": c.section,
                    "url": c.url,
                    "paragraph_index": c.paragraph_index,
                    "text_excerpt": c.text_excerpt,
                    "similarity_score": c.similarity_score,
                    "source": c.source,
                }
                for c in answer.citations
            ],
            "model": answer.model,
            "tokens_used": answer.tokens_used,
            "cost": answer.cost,
            "generation_time_ms": answer.generation_time_ms,
            "disclaimer": answer.disclaimer,
            # We don't cache the full context_used to save space
            "cached_at": time.time(),
        }

    def _deserialize_answer(self, answer_dict: Dict[str, Any]) -> GeneratedAnswer:
        """Reconstruct GeneratedAnswer from cached data.

        Args:
            answer_dict: Cached answer dictionary

        Returns:
            GeneratedAnswer instance
        """
        from src.generation.models import Citation

        citations = [
            Citation(
                chunk_id=c["chunk_id"],
                article_title=c["article_title"],
                section=c["section"],
                url=c["url"],
                paragraph_index=c["paragraph_index"],
                text_excerpt=c["text_excerpt"],
                similarity_score=c.get("similarity_score", 0.0),
                source=c.get("source", "Unknown"),
            )
            for c in answer_dict.get("citations", [])
        ]

        return GeneratedAnswer(
            query=answer_dict["query"],
            answer=answer_dict["answer"],
            citations=citations,
            context_used=None,  # Not cached
            model=answer_dict["model"],
            tokens_used=answer_dict["tokens_used"],
            cost=answer_dict["cost"],
            generation_time_ms=answer_dict["generation_time_ms"],
            disclaimer=answer_dict.get("disclaimer"),
        )

    def invalidate(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
        min_similarity: Optional[float] = None,
    ):
        """Invalidate (delete) a cached entry.

        Args:
            question: User question
            filters: Optional metadata filters
            max_results: Maximum results used
            min_similarity: Minimum similarity threshold used
        """
        if not self.enabled or not self.client:
            return

        try:
            cache_key = self._generate_cache_key(question, filters, max_results, min_similarity)
            self.client.delete(cache_key)
        except RedisError as e:
            print(f"⚠️  Cache invalidate error: {e}")

    def clear_all(self):
        """Clear all cached entries with our prefix.

        Use with caution!
        """
        if not self.enabled or not self.client:
            return

        try:
            # Find all keys with our prefix
            pattern = f"{self.config.key_prefix}*"
            keys = self.client.keys(pattern)

            if keys:
                self.client.delete(*keys)
                print(f"✅ Cleared {len(keys)} cached entries")
            else:
                print("ℹ️  No cached entries to clear")

        except RedisError as e:
            print(f"⚠️  Cache clear error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats_dict = self.stats.to_dict()
        persisted = self.stats_store.get_all()
        if persisted:
            queries = persisted.get("cache_queries", 0.0)
            hits = persisted.get("cache_hits", 0.0)
            stats_dict.update({
                "total_queries": int(queries),
                "cache_hits": int(hits),
                "cache_misses": int(persisted.get("cache_misses", 0.0)),
                "cache_errors": int(persisted.get("cache_errors", 0.0)),
                "hit_rate": (hits / queries) if queries else 0.0,
                "miss_rate": (persisted.get("cache_misses", 0.0) / queries) if queries else 0.0,
                "total_cost_saved": persisted.get("cache_cost_saved", 0.0),
                "total_time_saved_ms": persisted.get("cache_time_saved_ms", 0.0),
            })
        stats_dict["enabled"] = self.enabled
        stats_dict["config"] = self.config.to_dict()

        # Add Redis info if connected
        if self.enabled and self.client:
            try:
                info = self.client.info("stats")
                stats_dict["redis_total_commands"] = info.get("total_commands_processed", 0)
                stats_dict["redis_keyspace_hits"] = info.get("keyspace_hits", 0)
                stats_dict["redis_keyspace_misses"] = info.get("keyspace_misses", 0)
            except RedisError:
                pass

        return stats_dict

    def reset_stats(self):
        """Reset cache statistics, in-process and persisted."""
        self.stats.reset()
        self.stats_store.reset()

    def get_vector_db_stats(self) -> Optional[Dict[str, Any]]:
        """Get cached vector database statistics.

        Returns:
            Cached vector DB statistics if found, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        try:
            cache_key = f"{self.config.key_prefix}vector_db_stats"
            cached_data = self.client.get(cache_key)

            if cached_data:
                # Deserialize and return the stats
                return json.loads(cached_data)
            else:
                return None

        except (RedisError, json.JSONDecodeError) as e:
            print(f"⚠️  Cache get vector DB stats error: {e}")
            return None

    def set_vector_db_stats(self, stats: Dict[str, Any], ttl_seconds: Optional[int] = None):
        """Store vector database statistics in cache.

        Args:
            stats: Vector database statistics to cache
            ttl_seconds: Time to live in seconds (defaults to config.ttl_seconds)
        """
        if not self.enabled or not self.client:
            return

        try:
            cache_key = f"{self.config.key_prefix}vector_db_stats"
            cached_data = json.dumps(stats)

            # Use provided TTL or default from config
            ttl = ttl_seconds if ttl_seconds is not None else self.config.ttl_seconds

            # Store with TTL
            self.client.setex(cache_key, ttl, cached_data)

        except (RedisError, TypeError) as e:
            print(f"⚠️  Cache set vector DB stats error: {e}")

    def is_healthy(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if connected, False otherwise
        """
        if not self.enabled or not self.client:
            return False

        try:
            self.client.ping()
            return True
        except (RedisError, ConnectionError):
            return False
