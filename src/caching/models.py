"""Data models for caching."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class CacheConfig:
    """Configuration for Redis cache.

    Attributes:
        enabled: Whether caching is enabled
        host: Redis host address
        port: Redis port
        db: Redis database number
        password: Redis password (optional)
        ttl_seconds: Time-to-live for cached items (default: 1 hour)
        key_prefix: Prefix for all cache keys
        max_retries: Maximum retry attempts for Redis operations
        timeout: Operation timeout in seconds
    """
    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl_seconds: int = 3600  # 1 hour default
    key_prefix: str = "care_beacon:"
    max_retries: int = 3
    timeout: int = 5

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "ttl_seconds": self.ttl_seconds,
            "key_prefix": self.key_prefix,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
        }


@dataclass
class CacheStats:
    """Statistics for cache usage.

    Tracks cache performance and cost savings.
    """
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_errors: int = 0
    total_cost_saved: float = 0.0
    total_time_saved_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate.

        Returns:
            Hit rate as percentage (0.0-1.0)
        """
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate.

        Returns:
            Miss rate as percentage (0.0-1.0)
        """
        if self.total_queries == 0:
            return 0.0
        return self.cache_misses / self.total_queries

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "total_queries": self.total_queries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_errors": self.cache_errors,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "total_cost_saved": self.total_cost_saved,
            "total_time_saved_ms": self.total_time_saved_ms,
            "avg_time_saved_per_hit_ms": (
                self.total_time_saved_ms / self.cache_hits
                if self.cache_hits > 0 else 0.0
            ),
        }

    def reset(self):
        """Reset all statistics."""
        self.total_queries = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_errors = 0
        self.total_cost_saved = 0.0
        self.total_time_saved_ms = 0.0
