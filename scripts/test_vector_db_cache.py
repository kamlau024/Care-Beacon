#!/usr/bin/env python3
"""Test vector DB statistics caching."""

import sys
import json
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.caching.redis_cache import RedisCache


def test_vector_db_stats_caching():
    """Test caching of vector DB statistics."""
    print("=" * 70)
    print("Testing Vector DB Statistics Caching")
    print("=" * 70)

    # Initialize cache
    print("\n1. Initializing Redis cache...")
    cache = RedisCache()

    if not cache.enabled:
        print("❌ Cache is not enabled. Please ensure Redis is running.")
        return False

    if not cache.is_healthy():
        print("❌ Cache is not healthy. Please ensure Redis is running.")
        return False

    print("✅ Cache is enabled and healthy")

    # Test 1: Get stats when cache is empty
    print("\n2. Testing get_vector_db_stats() when cache is empty...")
    stats = cache.get_vector_db_stats()
    if stats is None:
        print("✅ Correctly returned None when cache is empty")
    else:
        print(f"❌ Expected None, got: {stats}")
        return False

    # Test 2: Set stats in cache
    print("\n3. Testing set_vector_db_stats()...")
    test_stats = {
        "total_documents": 100,
        "total_chunks": 1000,
        "sources": [
            {"name": "Test Source", "articles": 50, "chunks": 500, "storage_mb": 10.5}
        ],
        "collection_name": "test_collection",
        "distance_metric": "cosine",
        "vector_size": 1536
    }

    cache.set_vector_db_stats(test_stats)
    print("✅ Stats cached successfully")

    # Test 3: Retrieve cached stats
    print("\n4. Testing get_vector_db_stats() after caching...")
    cached_stats = cache.get_vector_db_stats()

    if cached_stats is None:
        print("❌ Expected cached stats, got None")
        return False

    if cached_stats == test_stats:
        print("✅ Retrieved correct stats from cache")
        print(f"   Cached stats: {json.dumps(cached_stats, indent=2)}")
    else:
        print(f"❌ Stats mismatch!")
        print(f"   Expected: {test_stats}")
        print(f"   Got: {cached_stats}")
        return False

    # Test 4: Clear cache
    print("\n5. Testing clear_all()...")
    cache.clear_all()

    # Test 5: Verify stats are cleared
    print("\n6. Verifying stats are cleared after clear_all()...")
    stats_after_clear = cache.get_vector_db_stats()
    if stats_after_clear is None:
        print("✅ Stats correctly cleared from cache")
    else:
        print(f"❌ Expected None after clear, got: {stats_after_clear}")
        return False

    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = test_vector_db_stats_caching()
    sys.exit(0 if success else 1)
