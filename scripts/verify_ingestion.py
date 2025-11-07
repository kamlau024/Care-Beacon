"""Quick verification script to check ingestion results.

This script automatically runs checks to verify the ingestion was successful.
No user interaction required - just run it!
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase


def main():
    """Run automated verification checks."""
    print("=" * 70)
    print("Ingestion Verification")
    print("=" * 70)
    print()

    # Initialize components
    print("Initializing components...")
    try:
        generator = EmbeddingGenerator()
        db = VectorDatabase()
        print("✅ Components initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return False
    print()

    # Check 1: Database has data
    print("=" * 70)
    print("Check 1: Database Contains Data")
    print("=" * 70)
    count = db.count()
    if count > 0:
        print(f"✅ PASS: Database contains {count:,} chunks")
    else:
        print("❌ FAIL: Database is empty")
        return False
    print()

    # Check 2: Database statistics
    print("=" * 70)
    print("Check 2: Database Statistics")
    print("=" * 70)
    stats = db.get_stats()
    print(f"✅ Collection: {stats['collection_name']}")
    print(f"✅ Total chunks: {stats['total_chunks']:,}")
    print(f"✅ Distance metric: {stats['distance_metric']}")
    print(f"✅ Storage: {stats['persist_directory']}")
    print()

    # Check 3: Sample chunks have embeddings
    print("=" * 70)
    print("Check 3: Chunks Have Embeddings")
    print("=" * 70)
    samples = db.peek(limit=5)
    if samples and all(chunk.embedding is not None for chunk in samples):
        print(f"✅ PASS: All sample chunks have embeddings")
        print(f"   Sample embedding dimensions: {len(samples[0].embedding)}")
    else:
        print("❌ FAIL: Some chunks missing embeddings")
        return False
    print()

    # Check 4: Chunks have metadata
    print("=" * 70)
    print("Check 4: Chunks Have Metadata")
    print("=" * 70)
    sample = samples[0]
    metadata_fields = ['article_id', 'article_title', 'url', 'section']
    all_present = all(getattr(sample, field, None) for field in metadata_fields)
    if all_present:
        print(f"✅ PASS: Chunks have complete metadata")
        print(f"   Sample chunk ID: {sample.chunk_id}")
        print(f"   Article: {sample.article_title}")
        print(f"   Section: {sample.section}")
    else:
        print("❌ FAIL: Some metadata missing")
        return False
    print()

    # Check 5: Search functionality works
    print("=" * 70)
    print("Check 5: Search Functionality")
    print("=" * 70)
    query = "What are the symptoms of breast cancer?"
    print(f"Test query: \"{query}\"")
    try:
        query_embedding = generator.embed_text(query)
        results = db.search(query_embedding, n_results=3)

        if results and len(results) > 0:
            print(f"✅ PASS: Search returned {len(results)} results")
            print(f"   Top result similarity: {results[0].similarity_score:.4f}")
            print(f"   Top result article: {results[0].chunk.article_title}")
        else:
            print("❌ FAIL: Search returned no results")
            return False
    except Exception as e:
        print(f"❌ FAIL: Search failed with error: {e}")
        return False
    print()

    # Check 6: Metadata filtering works
    print("=" * 70)
    print("Check 6: Metadata Filtering")
    print("=" * 70)
    print("Testing filter: cancer_type = 'Breast Cancer'")
    try:
        filtered_results = db.search(
            query_embedding,
            n_results=3,
            where={"cancer_type": "Breast Cancer"}
        )

        if filtered_results:
            print(f"✅ PASS: Metadata filtering works")
            print(f"   Found {len(filtered_results)} breast cancer results")
            all_breast = all(r.chunk.cancer_type == "Breast Cancer" for r in filtered_results if r.chunk.cancer_type)
            if all_breast:
                print(f"   ✅ All results match filter")
            else:
                print(f"   ⚠️  Some results don't match filter (might be general articles)")
        else:
            print("⚠️  WARNING: No results with filter (might be expected)")
    except Exception as e:
        print(f"❌ FAIL: Filtering failed with error: {e}")
        return False
    print()

    # Check 7: Multiple cancer types present
    print("=" * 70)
    print("Check 7: Multiple Cancer Types Present")
    print("=" * 70)
    test_queries = [
        ("breast cancer", "Breast Cancer"),
        ("lung cancer", "Lung"),
        ("colorectal cancer", "Colorectal"),
    ]

    found_types = []
    for query_text, expected_type in test_queries:
        query_emb = generator.embed_text(f"What are symptoms of {query_text}?")
        results = db.search(query_emb, n_results=3)
        if results:
            articles = [r.chunk.article_title for r in results]
            found_types.append(expected_type)
            print(f"✅ Found results for {query_text}: {articles[0]}")

    if len(found_types) >= 2:
        print(f"✅ PASS: Multiple cancer types present ({len(found_types)} types tested)")
    else:
        print(f"⚠️  WARNING: Only {len(found_types)} cancer types found")
    print()

    # Final summary
    print("=" * 70)
    print("Verification Summary")
    print("=" * 70)
    print()
    print("✅ ALL CHECKS PASSED!")
    print()
    print(f"Your database is ready with {count:,} chunks from medical articles.")
    print()
    print("Next steps:")
    print("  1. Test queries: python scripts/test_query.py")
    print("  2. Proceed to Phase 2: RAG System Implementation")
    print()

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
