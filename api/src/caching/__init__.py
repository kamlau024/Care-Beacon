"""Caching module for Care-Beacon.

Provides Redis-based caching for query results to reduce API costs
and improve response times.
"""

from src.caching.redis_cache import RedisCache
from src.caching.models import CacheConfig, CacheStats

__all__ = ["RedisCache", "CacheConfig", "CacheStats"]
