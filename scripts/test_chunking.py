"""Test script to verify chunking on actual BC Cancer articles."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.markdown_parser import MarkdownParser
from src.embeddings.chunking import DocumentChunker


def main():
    """Test chunking on actual articles."""
    parser = MarkdownParser()
    chunker = DocumentChunker()

    # Test on a few sample articles
    articles_dir = project_root / "scraped_data" / "articles" / "health-info" / "types-of-cancer"

    test_files = [
        articles_dir / "breast-cancer.md",
        articles_dir / "digestive-system" / "pancreas.md",
        articles_dir / "lung" / "lung.md",
    ]

    print("=" * 70)
    print("Testing Document Chunking on BC Cancer Articles")
    print("=" * 70)
    print()

    all_chunks = []

    for file_path in test_files:
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            print()
            continue

        print(f"📄 Processing: {file_path.name}")
        print("-" * 70)

        try:
            # Parse the article
            article = parser.parse_file(file_path)

            # Chunk the article
            chunks = chunker.chunk_article(article)

            # Get statistics
            stats = chunker.get_chunking_stats(chunks)

            # Display results
            print(f"✅ Successfully chunked!")
            print(f"   Article: {article.title}")
            print(f"   Total paragraphs: {article.get_total_paragraph_count()}")
            print(f"   Total chunks: {stats['total_chunks']}")
            print(f"   Avg chunk length: {stats['avg_chunk_length']:.1f} characters")
            print(f"   Avg words per chunk: {stats['avg_words_per_chunk']:.1f} words")
            print(f"   Unique sections: {stats['unique_sections']}")
            print()

            # Show first 3 chunks
            print("   First 3 chunks:")
            for i, chunk in enumerate(chunks[:3], 1):
                text_preview = chunk.text[:80] + "..." if len(chunk.text) > 80 else chunk.text
                print(f"     {i}. [{chunk.chunk_id}]")
                print(f"        Section: {chunk.section}")
                print(f"        Text: \"{text_preview}\"")
                print()

            all_chunks.extend(chunks)

        except Exception as e:
            print(f"❌ Error processing file: {e}")
            import traceback
            traceback.print_exc()

        print()

    # Process all articles in directory
    print("=" * 70)
    print("Processing All Articles in Directory")
    print("=" * 70)
    print()

    try:
        print(f"📁 Parsing all articles in: {articles_dir}")
        articles = parser.parse_directory(articles_dir)
        print(f"✅ Parsed {len(articles)} articles")
        print()

        print(f"🔨 Chunking all articles...")
        all_chunks = chunker.chunk_articles(articles)
        print(f"✅ Created {len(all_chunks)} chunks")
        print()

        # Get overall statistics
        stats = chunker.get_chunking_stats(all_chunks)

        print("📊 Overall Statistics:")
        print(f"   Total chunks: {stats['total_chunks']:,}")
        print(f"   Total characters: {stats['total_characters']:,}")
        print(f"   Total words: {stats['total_words']:,}")
        print(f"   Avg chunk length: {stats['avg_chunk_length']:.1f} characters")
        print(f"   Avg words per chunk: {stats['avg_words_per_chunk']:.1f} words")
        print(f"   Min chunk length: {stats['min_chunk_length']} characters")
        print(f"   Max chunk length: {stats['max_chunk_length']} characters")
        print(f"   Unique articles: {stats['unique_articles']}")
        print(f"   Unique sections: {stats['unique_sections']}")
        print()

        # Analyze chunk distribution
        chunk_lengths = [len(c.text) for c in all_chunks]
        small_chunks = len([l for l in chunk_lengths if l < 100])
        medium_chunks = len([l for l in chunk_lengths if 100 <= l < 500])
        large_chunks = len([l for l in chunk_lengths if l >= 500])

        print("📈 Chunk Size Distribution:")
        print(f"   Small (<100 chars): {small_chunks} ({small_chunks/len(all_chunks)*100:.1f}%)")
        print(f"   Medium (100-500 chars): {medium_chunks} ({medium_chunks/len(all_chunks)*100:.1f}%)")
        print(f"   Large (≥500 chars): {large_chunks} ({large_chunks/len(all_chunks)*100:.1f}%)")
        print()

        # Sample chunks for quality check
        print("🔍 Sample Chunks (Quality Check):")
        import random
        sample_chunks = random.sample(all_chunks, min(5, len(all_chunks)))

        for i, chunk in enumerate(sample_chunks, 1):
            print(f"\n   {i}. Article: {chunk.article_title}")
            print(f"      Section: {chunk.section}")
            print(f"      Chunk ID: {chunk.chunk_id}")
            print(f"      Length: {len(chunk.text)} chars, {len(chunk.text.split())} words")
            text_preview = chunk.text[:150] + "..." if len(chunk.text) > 150 else chunk.text
            print(f"      Text: \"{text_preview}\"")

        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 70)
    print("Chunking test complete!")
    print("=" * 70)
    print()
    print("💡 Next Steps:")
    print("   - Review chunk quality and sizes")
    print("   - Proceed to Checkpoint 1.4: Embedding Generation")
    print()


if __name__ == "__main__":
    main()
