"""Quick test script for hybrid search functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.retrieval.retrieval_engine import RetrievalEngine
from src.config_loader import get_config
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO")


def test_hybrid_search():
    """Test hybrid search with sample queries."""

    # Check config
    config = get_config()
    hybrid_enabled = config.get('retrieval.enable_hybrid_search', False)
    hybrid_alpha = config.get('retrieval.hybrid_alpha', 0.7)

    logger.info("=" * 70)
    logger.info("HYBRID SEARCH TEST")
    logger.info("=" * 70)
    logger.info(f"Hybrid search enabled: {hybrid_enabled}")
    logger.info(f"Hybrid alpha (vector weight): {hybrid_alpha}")
    logger.info("")

    # Initialize retrieval engine
    logger.info("Initializing retrieval engine...")
    engine = RetrievalEngine()

    # Check if hybrid search is available
    has_hybrid = hasattr(engine.vector_db, 'hybrid_search')
    has_bm25 = hasattr(engine.vector_db, 'bm25_index') and engine.vector_db.bm25_index is not None

    logger.info(f"Vector DB has hybrid_search method: {has_hybrid}")
    logger.info(f"BM25 index is loaded: {has_bm25}")
    logger.info("")

    if not has_hybrid:
        logger.error("❌ Vector DB does not have hybrid_search method")
        return

    if not has_bm25:
        logger.warning("⚠️  BM25 index not loaded - hybrid search will fall back to vector search")
        logger.info("Building BM25 index now...")
        if hasattr(engine.vector_db, 'rebuild_bm25_index'):
            engine.vector_db.rebuild_bm25_index()
            logger.info("✅ BM25 index built successfully")
        else:
            logger.error("❌ Cannot rebuild BM25 index - method not available")
            return

    # Test queries
    test_queries = [
        "What are the symptoms of breast cancer?",
        "How is lung cancer diagnosed?",
        "What screening tests are available for prostate cancer?"
    ]

    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n--- Test Query {i} ---")
        logger.info(f"Query: {query}")
        logger.info("")

        # Retrieve results
        context = engine.retrieve_text(query, max_results=5)

        logger.info(f"Retrieved {context.total_chunks} chunks in {context.retrieval_time_ms:.0f}ms")

        if context.total_chunks > 0:
            logger.info("\nTop 3 results:")
            for j, result in enumerate(context.results[:3], 1):
                logger.info(f"  {j}. [{result.similarity_score:.4f}] {result.chunk.article_title} - {result.chunk.section}")
                logger.info(f"     {result.chunk.text[:100]}...")
        else:
            logger.warning("  No results returned")
        logger.info("")

    logger.info("=" * 70)
    logger.info("✅ Hybrid search test complete")
    logger.info("=" * 70)


if __name__ == "__main__":
    try:
        test_hybrid_search()
    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
        sys.exit(1)
