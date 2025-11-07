"""Test script to verify vector database with real embeddings."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.markdown_parser import MarkdownParser
from src.embeddings.chunking import DocumentChunker
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase


def main():
    """Test vector database with real data."""
    print("=" * 70)
    print("Testing Vector Database with Chroma")
    print("=" * 70)
    print()

    # Initialize components
    parser = MarkdownParser()
    chunker = DocumentChunker()
    generator = EmbeddingGenerator()
    db = VectorDatabase()

    print(f"✅ Components initialized")
    print(f"   Database: {db.collection_name}")
    print(f"   Persist directory: {db.persist_directory}")
    print(f"   Current chunk count: {db.count()}")
    print()

    # Parse and chunk sample articles
    print("=" * 70)
    print("Step 1: Parsing and Chunking Sample Articles")
    print("=" * 70)
    print()

    articles_dir = project_root / "scraped_data" / "articles" / "health-info" / "types-of-cancer"

    test_files = [
        articles_dir / "breast-cancer.md",
        articles_dir / "digestive-system" / "pancreas.md",
        articles_dir / "lung" / "lung.md",
    ]

    all_chunks = []
    for file_path in test_files:
        if file_path.exists():
            print(f"📄 Parsing: {file_path.name}")
            article = parser.parse_file(file_path)
            chunks = chunker.chunk_article(article)
            all_chunks.extend(chunks)
            print(f"   Created {len(chunks)} chunks")

    print()
    print(f"✅ Total chunks: {len(all_chunks)}")
    print()

    # Take a sample for testing
    sample_chunks = all_chunks[:20]  # Use first 20 chunks
    print(f"Using {len(sample_chunks)} sample chunks for testing")
    print()

    # Generate embeddings
    print("=" * 70)
    print("Step 2: Generating Embeddings")
    print("=" * 70)
    print()

    generator.reset_stats()
    embedded_chunks = generator.embed_chunks(sample_chunks, show_progress=True)
    print()

    # Add to database
    print("=" * 70)
    print("Step 3: Adding Chunks to Vector Database")
    print("=" * 70)
    print()

    db.add_chunks(embedded_chunks, show_progress=True)
    print()

    # Get database statistics
    stats = db.get_stats()
    print("📊 Database Statistics:")
    print(f"   Collection: {stats['collection_name']}")
    print(f"   Total chunks: {stats['total_chunks']}")
    print(f"   Distance metric: {stats['distance_metric']}")
    print()

    # Test retrieval
    print("=" * 70)
    print("Step 4: Testing Similarity Search")
    print("=" * 70)
    print()

    # Test queries
    test_queries = [
        "What are the symptoms of breast cancer?",
        "How is lung cancer diagnosed?",
        "What causes pancreatic cancer?",
    ]

    for query in test_queries:
        print(f"Query: \"{query}\"")
        print("-" * 70)

        # Generate query embedding
        query_embedding = generator.embed_text(query)

        # Search
        results = db.search(query_embedding, n_results=3)

        print(f"Found {len(results)} results:\n")

        for result in results:
            chunk = result.chunk
            text_preview = chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text

            print(f"  [{result.rank}] Similarity: {result.similarity_score:.4f}")
            print(f"      Article: {chunk.article_title}")
            print(f"      Section: {chunk.section}")
            print(f"      Text: \"{text_preview}\"")
            print()

        print()

    # Test metadata filtering
    print("=" * 70)
    print("Step 5: Testing Metadata Filtering")
    print("=" * 70)
    print()

    query = "What are the treatment options?"
    print(f"Query: \"{query}\"")
    print()

    query_embedding = generator.embed_text(query)

    # Search without filter
    print("Without filter:")
    results_all = db.search(query_embedding, n_results=5)
    print(f"  Found {len(results_all)} results across all articles")
    for r in results_all:
        print(f"    - {r.chunk.article_title} (score: {r.similarity_score:.4f})")
    print()

    # Search with filter (if we have breast cancer chunks)
    breast_cancer_chunks = [c for c in embedded_chunks if c.cancer_type == "Breast Cancer"]
    if breast_cancer_chunks:
        print("With filter (Breast Cancer only):")
        results_filtered = db.search(
            query_embedding,
            n_results=5,
            where={"cancer_type": "Breast Cancer"}
        )
        print(f"  Found {len(results_filtered)} results")
        for r in results_filtered:
            print(f"    - {r.chunk.article_title} (score: {r.similarity_score:.4f})")
        print()

    # Test get chunk by ID
    print("=" * 70)
    print("Step 6: Testing Get Chunk by ID")
    print("=" * 70)
    print()

    if embedded_chunks:
        test_chunk_id = embedded_chunks[0].chunk_id
        print(f"Retrieving chunk: {test_chunk_id}")

        retrieved = db.get_chunk(test_chunk_id)
        if retrieved:
            print(f"✅ Successfully retrieved!")
            print(f"   Article: {retrieved.article_title}")
            print(f"   Section: {retrieved.section}")
            print(f"   Text: \"{retrieved.text[:100]}...\"")
        else:
            print(f"❌ Chunk not found")
        print()

    # Peek at database
    print("=" * 70)
    print("Step 7: Peeking at Database Contents")
    print("=" * 70)
    print()

    samples = db.peek(limit=5)
    print(f"Sample of {len(samples)} chunks from database:")
    for i, chunk in enumerate(samples, 1):
        text_preview = chunk.text[:60] + "..." if len(chunk.text) > 60 else chunk.text
        print(f"  {i}. [{chunk.chunk_id}]")
        print(f"     {chunk.article_title} - {chunk.section}")
        print(f"     \"{text_preview}\"")
        print()

    # Cost summary
    print("=" * 70)
    print("Cost Summary")
    print("=" * 70)
    print()

    embedding_stats = generator.get_embedding_stats()
    print(f"Embeddings generated: {len(embedded_chunks) + len(test_queries)}")
    print(f"Total tokens: {embedding_stats['total_tokens_used']:,}")
    print(f"Total cost: ${embedding_stats['total_cost']:.6f}")
    print()

    print("=" * 70)
    print("Vector Database Test Complete!")
    print("=" * 70)
    print()
    print("💡 Summary:")
    print(f"   - Added {stats['total_chunks']} chunks to database")
    print(f"   - Tested similarity search successfully")
    print(f"   - Tested metadata filtering")
    print(f"   - Database persisted to: {db.persist_directory}")
    print()
    print("Next Steps:")
    print("   - Database is ready for full data ingestion")
    print("   - Proceed to Checkpoint 1.6: Complete Ingestion Pipeline")
    print()


if __name__ == "__main__":
    main()
