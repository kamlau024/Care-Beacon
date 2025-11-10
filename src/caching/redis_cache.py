"""Redis cache client for query results."""

import os
import json
import hashlib
import time
from typing import Optional, Dict, Any
import redis
from redis.exceptions import RedisError, ConnectionError

from src.caching.models import CacheConfig, CacheStats
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

    def _load_config(self) -> CacheConfig:
        """Load cache configuration.

        Checks environment variables first, then falls back to config file.
        This allows Docker and cloud environment variables to override config.yaml.

        Returns:
            CacheConfig instance
        """
        config = get_config()
        cache_config = config.get("cache", {})

        # Check for REDIS_URL first (used by Render, Heroku, etc.)
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            # Parse Redis URL (format: redis://[user:password@]host:port[/db])
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
        )

    def _generate_cache_key(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
    ) -> str:
        """Generate a unique cache key for a query.

        Creates a hash of the query parameters to use as cache key.

        Args:
            question: User question
            filters: Optional metadata filters
            max_results: Maximum results to retrieve

        Returns:
            Cache key string
        """
        # Create a canonical representation of the query
        query_dict = {
            "question": question.strip().lower(),  # Normalize
            "filters": filters or {},
            "max_results": max_results,
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
    ) -> Optional[GeneratedAnswer]:
        """Get cached answer if available.

        Args:
            question: User question
            filters: Optional metadata filters
            max_results: Maximum results to retrieve

        Returns:
            Cached GeneratedAnswer if found, None otherwise
        """
        if not self.enabled or not self.client:
            return None

        self.stats.total_queries += 1

        try:
            cache_key = self._generate_cache_key(question, filters, max_results)
            cached_data = self.client.get(cache_key)

            if cached_data:
                # Cache hit!
                self.stats.cache_hits += 1

                # Deserialize
                answer_dict = json.loads(cached_data)

                # Reconstruct GeneratedAnswer from cached data
                # Note: We'll store a simplified version in cache
                return self._deserialize_answer(answer_dict)

            else:
                # Cache miss
                self.stats.cache_misses += 1
                return None

        except (RedisError, json.JSONDecodeError) as e:
            self.stats.cache_errors += 1
            print(f"⚠️  Cache get error: {e}")
            return None

    def set(
        self,
        question: str,
        answer: GeneratedAnswer,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
    ):
        """Store answer in cache.

        Args:
            question: User question
            answer: Generated answer to cache
            filters: Optional metadata filters
            max_results: Maximum results used
        """
        if not self.enabled or not self.client:
            return

        try:
            cache_key = self._generate_cache_key(question, filters, max_results)

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
    ):
        """Invalidate (delete) a cached entry.

        Args:
            question: User question
            filters: Optional metadata filters
            max_results: Maximum results used
        """
        if not self.enabled or not self.client:
            return

        try:
            cache_key = self._generate_cache_key(question, filters, max_results)
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
        """Reset cache statistics."""
        self.stats.reset()

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
