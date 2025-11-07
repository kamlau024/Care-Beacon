"""Test script to verify embedding generation with OpenAI API."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.markdown_parser import MarkdownParser
from src.embeddings.chunking import DocumentChunker
from src.embeddings.embedding_generator import EmbeddingGenerator


def main():
    """Test embedding generation on sample chunks."""
    print("=" * 70)
    print("Testing Embedding Generation with OpenAI API")
    print("=" * 70)
    print()

    # Initialize components
    parser = MarkdownParser()
    chunker = DocumentChunker()

    try:
        generator = EmbeddingGenerator()
        print(f"✅ Embedding generator initialized")
        print(f"   Model: {generator.model}")
        print(f"   Dimensions: {generator.dimensions}")
        print(f"   Batch size: {generator.batch_size}")
        print()

    except Exception as e:
        print(f"❌ Failed to initialize embedding generator: {e}")
        print()
        print("Make sure you have:")
        print("  1. Added your OpenAI API key to .env file")
        print("  2. OPENAI_API_KEY=sk-your-key-here")
        print()
        return

    # Test on a small sample
    print("=" * 70)
    print("Test 1: Embedding a Single Text")
    print("=" * 70)
    print()

    sample_text = "Breast cancer is the most common cancer in women. Early detection through screening can improve outcomes."

    try:
        print(f"Text: \"{sample_text}\"")
        print()
        print("Generating embedding...")

        embedding = generator.embed_text(sample_text)

        print(f"✅ Successfully generated embedding!")
        print(f"   Dimensions: {len(embedding)}")
        print(f"   First 5 values: {embedding[:5]}")
        print(f"   Tokens used: {generator.total_tokens_used}")
        print(f"   Cost: ${generator.total_cost:.6f}")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        return

    # Test on real chunks
    print("=" * 70)
    print("Test 2: Embedding Real Article Chunks")
    print("=" * 70)
    print()

    articles_dir = project_root / "scraped_data" / "articles" / "health-info" / "types-of-cancer"
    test_file = articles_dir / "breast-cancer.md"

    if not test_file.exists():
        print(f"⚠️  Test file not found: {test_file}")
        print("   Skipping chunk embedding test")
        print()
    else:
        try:
            # Parse and chunk article
            print(f"📄 Parsing: {test_file.name}")
            article = parser.parse_file(test_file)

            print(f"🔨 Chunking article...")
            chunks = chunker.chunk_article(article)

            # Take first 5 chunks as sample
            sample_chunks = chunks[:5]

            print(f"✅ Using {len(sample_chunks)} sample chunks")
            print()

            # Show sample chunks
            print("Sample chunks:")
            for i, chunk in enumerate(sample_chunks, 1):
                text_preview = chunk.text[:60] + "..." if len(chunk.text) > 60 else chunk.text
                print(f"  {i}. [{chunk.chunk_id}] \"{text_preview}\"")
            print()

            # Reset stats for clean measurement
            generator.reset_stats()

            # Generate embeddings
            print("Generating embeddings...")
            print()

            embedded_chunks = generator.embed_chunks(sample_chunks, show_progress=True)

            print()
            print("✅ Successfully embedded all chunks!")
            print()

            # Show sample embedding
            first_chunk = embedded_chunks[0]
            print(f"Sample embedding (first chunk):")
            print(f"  Chunk ID: {first_chunk.chunk_id}")
            print(f"  Text: \"{first_chunk.text[:80]}...\"")
            print(f"  Embedding dimensions: {len(first_chunk.embedding)}")
            print(f"  First 10 values: {first_chunk.embedding[:10]}")
            print()

            # Get statistics
            stats = generator.get_embedding_stats()
            print("📊 Embedding Statistics:")
            print(f"   Model: {stats['model']}")
            print(f"   Dimensions: {stats['dimensions']}")
            print(f"   Total tokens: {stats['total_tokens_used']:,}")
            print(f"   Total cost: ${stats['total_cost']:.6f}")
            print(f"   Cost per 1K tokens: ${stats['cost_per_1k_tokens']:.6f}")
            print()

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            print()
            return

    # Estimate cost for full corpus
    print("=" * 70)
    print("Cost Estimation for Full Corpus")
    print("=" * 70)
    print()

    try:
        # Parse all articles to get chunk count
        print("📁 Parsing all articles to estimate cost...")
        articles = parser.parse_directory(articles_dir)
        all_chunks = chunker.chunk_articles(articles)

        total_chunks = len(all_chunks)
        total_chars = sum(len(c.text) for c in all_chunks)
        estimated_tokens = total_chars / 4  # Rough estimate: 4 chars per token

        # Cost calculation
        cost_per_1m_tokens = 0.02  # text-embedding-3-small
        estimated_cost = (estimated_tokens / 1_000_000) * cost_per_1m_tokens

        print(f"✅ Analysis complete:")
        print(f"   Total articles: {len(articles)}")
        print(f"   Total chunks: {total_chunks:,}")
        print(f"   Total characters: {total_chars:,}")
        print(f"   Estimated tokens: {estimated_tokens:,.0f}")
        print(f"   Estimated cost: ${estimated_cost:.4f}")
        print()

        # Time estimation
        chunks_per_batch = generator.batch_size
        total_batches = (total_chunks + chunks_per_batch - 1) // chunks_per_batch
        estimated_seconds = total_batches * 1.5  # ~1.5 seconds per batch

        print(f"⏱️  Time Estimation:")
        print(f"   Total batches: {total_batches}")
        print(f"   Estimated time: {estimated_seconds:.0f} seconds (~{estimated_seconds/60:.1f} minutes)")
        print()

    except Exception as e:
        print(f"⚠️  Could not estimate full corpus cost: {e}")
        print()

    print("=" * 70)
    print("Embedding test complete!")
    print("=" * 70)
    print()
    print("💡 Next Steps:")
    print("   - If tests passed, proceed to Checkpoint 1.5: Vector Database Setup")
    print("   - Run full ingestion when ready with: python scripts/ingest_all_articles.py")
    print()


if __name__ == "__main__":
    main()
