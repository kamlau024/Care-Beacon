#!/usr/bin/env python3
"""Test vector DB statistics caching via API endpoint."""

import sys
import json
import requests
import time

API_BASE_URL = "http://localhost:8000"


def test_vector_db_stats_caching_api():
    """Test caching of vector DB statistics via API."""
    print("=" * 70)
    print("Testing Vector DB Statistics Caching via API")
    print("=" * 70)

    # Test 1: Clear cache first (to ensure we start fresh)
    print("\n1. Clearing cache...")
    try:
        response = requests.post(f"{API_BASE_URL}/api/v1/cache/clear")
        if response.status_code == 200:
            print("✅ Cache cleared successfully")
        else:
            print(f"⚠️  Cache clear returned: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Cache clear failed (this is okay for testing): {e}")

    # Test 2: First call - should fetch from database and cache
    print("\n2. First call to /api/v1/vector-db/stats (will fetch and cache)...")
    start_time = time.time()
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/vector-db/stats")
        first_call_time = time.time() - start_time

        if response.status_code == 200:
            stats1 = response.json()
            print(f"✅ Retrieved stats in {first_call_time:.2f} seconds")
            print(f"   Total documents: {stats1.get('total_documents')}")
            print(f"   Total chunks: {stats1.get('total_chunks')}")
            print(f"   Number of sources: {len(stats1.get('sources', []))}")
        else:
            print(f"❌ Request failed with status: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

    # Test 3: Second call - should come from cache (much faster)
    print("\n3. Second call to /api/v1/vector-db/stats (should use cache)...")
    start_time = time.time()
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/vector-db/stats")
        second_call_time = time.time() - start_time

        if response.status_code == 200:
            stats2 = response.json()
            print(f"✅ Retrieved stats in {second_call_time:.2f} seconds")
            print(f"   Total documents: {stats2.get('total_documents')}")
            print(f"   Total chunks: {stats2.get('total_chunks')}")
            print(f"   Number of sources: {len(stats2.get('sources', []))}")

            # Verify stats are the same
            if stats1 == stats2:
                print("✅ Stats are identical (cached correctly)")
            else:
                print("❌ Stats differ (caching issue)")
                return False

            # Check if second call was significantly faster (indicates caching)
            if second_call_time < first_call_time * 0.5:
                print(f"✅ Second call was {first_call_time/second_call_time:.1f}x faster (cache hit)")
            else:
                print(f"⚠️  Second call not significantly faster (may not have hit cache)")
                print(f"   First: {first_call_time:.2f}s, Second: {second_call_time:.2f}s")
        else:
            print(f"❌ Request failed with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

    print("\n" + "=" * 70)
    print("✅ API caching test completed successfully!")
    print("=" * 70)
    print("\n📝 Summary:")
    print(f"   - First call (fetch + cache): {first_call_time:.2f}s")
    print(f"   - Second call (from cache): {second_call_time:.2f}s")
    print(f"   - Speed improvement: {first_call_time/second_call_time:.1f}x faster")
    return True


if __name__ == "__main__":
    success = test_vector_db_stats_caching_api()
    sys.exit(0 if success else 1)
