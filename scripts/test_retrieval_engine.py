"""Test script for the retrieval engine with real database.

This script demonstrates the retrieval engine functionality using
the actual ingested database.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.retrieval.retrieval_engine import RetrievalEngine
from src.retrieval.models import Query


def print_divider(title: str = ""):
    """Print a formatted divider."""
    if title:
        print()
        print("=" * 70)
        print(title)
        print("=" * 70)
        print()
    else:
        print("-" * 70)


def print_results(context):
    """Print retrieval results in a formatted way."""
    print(f"✅ Retrieved {context.total_chunks} chunks in {context.retrieval_time_ms:.1f}ms")
    print()

    for result in context.results:
        chunk = result.chunk
        text_preview = chunk.text[:150] + "..." if len(chunk.text) > 150 else chunk.text

        print(f"[{result.rank}] Similarity: {result.similarity_score:.4f}")
        print(f"    Article: {chunk.article_title}")
        print(f"    Section: {chunk.section}")
        if chunk.cancer_type:
            print(f"    Cancer Type: {chunk.cancer_type}")
        print(f"    Text: \"{text_preview}\"")
        print()


def test_basic_retrieval(engine: RetrievalEngine):
    """Test basic retrieval functionality."""
    print_divider("Test 1: Basic Retrieval")

    query_text = "What are the symptoms of breast cancer?"
    print(f"Query: \"{query_text}\"")
    print()

    context = engine.retrieve_text(query_text, max_results=3)
    print_results(context)


def test_filtered_retrieval(engine: RetrievalEngine):
    """Test retrieval with metadata filtering."""
    print_divider("Test 2: Filtered Retrieval (Breast Cancer Only)")

    query_text = "What are treatment options?"
    print(f"Query: \"{query_text}\"")
    print(f"Filter: cancer_type = 'Breast Cancer'")
    print()

    context = engine.retrieve_for_cancer_type(query_text, "Breast Cancer", max_results=3)
    print_results(context)


def test_similarity_threshold(engine: RetrievalEngine):
    """Test retrieval with similarity threshold."""
    print_divider("Test 3: Similarity Threshold Filtering")

    query = Query(
        text="How is cancer diagnosed?",
        max_results=10,
        min_similarity=0.6  # Only results with similarity >= 0.6
    )

    print(f"Query: \"{query.text}\"")
    print(f"Min Similarity: {query.min_similarity}")
    print()

    context = engine.retrieve(query)
    print_results(context)


def test_multiple_queries(engine: RetrievalEngine):
    """Test multiple different queries."""
    print_divider("Test 4: Multiple Queries")

    queries = [
        "What causes lung cancer?",
        "How can I prevent colorectal cancer?",
        "What are side effects of chemotherapy?",
    ]

    for i, query_text in enumerate(queries, 1):
        print(f"Query {i}: \"{query_text}\"")
        print()

        context = engine.retrieve_text(query_text, max_results=2)

        print(f"Top result: {context.results[0].chunk.article_title}")
        print(f"Similarity: {context.results[0].similarity_score:.4f}")
        print()

        if i < len(queries):
            print_divider()


def test_context_text(engine: RetrievalEngine):
    """Test getting combined context text."""
    print_divider("Test 5: Context Text Generation")

    query_text = "What are symptoms of pancreatic cancer?"
    print(f"Query: \"{query_text}\"")
    print()

    context = engine.retrieve_text(query_text, max_results=3)

    print(f"Retrieved {context.total_chunks} chunks")
    print()
    print("Combined context text:")
    print_divider()
    print(context.get_context_text(max_chunks=2))
    print_divider()


def test_unique_articles(engine: RetrievalEngine):
    """Test getting unique articles from results."""
    print_divider("Test 6: Unique Articles in Results")

    query_text = "What are treatment options for cancer?"
    print(f"Query: \"{query_text}\"")
    print()

    context = engine.retrieve_text(query_text, max_results=10)

    unique_articles = context.get_unique_articles()

    print(f"Total results: {context.total_chunks}")
    print(f"Unique articles: {len(unique_articles)}")
    print()
    print("Articles:")
    for article_id in unique_articles[:5]:  # Show first 5
        print(f"  - {article_id}")


def test_similar_chunks(engine: RetrievalEngine):
    """Test finding similar chunks."""
    print_divider("Test 7: Similar Chunks")

    # First, get a chunk
    context = engine.retrieve_text("breast cancer symptoms", max_results=1)
    original_chunk = context.results[0].chunk

    print(f"Original chunk: {original_chunk.chunk_id}")
    print(f"Article: {original_chunk.article_title}")
    print(f"Text: \"{original_chunk.text[:100]}...\"")
    print()

    # Find similar chunks
    similar = engine.get_similar_chunks(original_chunk.chunk_id, max_results=3)

    print(f"Found {len(similar)} similar chunks:")
    print()

    for result in similar:
        chunk = result.chunk
        print(f"[{result.rank}] Similarity: {result.similarity_score:.4f}")
        print(f"    {chunk.article_title} - {chunk.section}")
        print()


def test_retrieval_stats(engine: RetrievalEngine):
    """Test getting statistics."""
    print_divider("Test 8: Retrieval Statistics")

    # Run a query
    context = engine.retrieve_text("cancer symptoms", max_results=5)

    print("Query Statistics:")
    print(f"  Results retrieved: {context.total_chunks}")
    print(f"  Retrieval time: {context.retrieval_time_ms:.1f}ms")
    print()

    # Get database stats
    db_stats = engine.get_database_stats()
    print("Database Statistics:")
    print(f"  Total chunks: {db_stats['total_chunks']:,}")
    print(f"  Collection: {db_stats['collection_name']}")
    print()

    # Get config
    config = engine.get_config_dict()
    print("Configuration:")
    print(f"  Default max results: {config['default_max_results']}")
    print(f"  Default min similarity: {config['default_min_similarity']}")
    print(f"  Include metadata: {config['include_metadata']}")


def main():
    """Main test function."""
    print()
    print("=" * 70)
    print("Retrieval Engine Test - Real Database")
    print("=" * 70)
    print()

    # Initialize retrieval engine
    print("Initializing retrieval engine...")
    try:
        engine = RetrievalEngine()
        print("✅ Retrieval engine initialized")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return

    # Check database has data
    stats = engine.get_database_stats()
    if stats['total_chunks'] == 0:
        print("❌ Database is empty. Run ingest_all_articles.py first.")
        return

    print(f"✅ Database ready with {stats['total_chunks']:,} chunks")
    print()

    # Run tests
    try:
        test_basic_retrieval(engine)
        test_filtered_retrieval(engine)
        test_similarity_threshold(engine)
        test_multiple_queries(engine)
        test_context_text(engine)
        test_unique_articles(engine)
        test_similar_chunks(engine)
        test_retrieval_stats(engine)

        # Final summary
        print_divider("Summary")
        print("✅ All retrieval tests completed successfully!")
        print()
        print("Key Features Demonstrated:")
        print("  1. Basic text retrieval with embeddings")
        print("  2. Metadata filtering (by cancer type)")
        print("  3. Similarity threshold filtering")
        print("  4. Multiple query handling")
        print("  5. Context text generation")
        print("  6. Unique article identification")
        print("  7. Similar chunk finding")
        print("  8. Statistics and configuration")
        print()
        print("Next Steps:")
        print("  - Proceed to Checkpoint 2.2: LLM Integration")
        print("  - Build answer generation with citations")
        print()

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
