"""Ingest all medical articles into the vector database.

This script:
1. Finds all markdown articles in scraped_data/
2. Parses each article with MarkdownParser
3. Chunks articles into paragraphs with DocumentChunker
4. Generates embeddings with EmbeddingGenerator
5. Stores chunks in VectorDatabase
6. Reports statistics and costs
"""

import sys
from pathlib import Path
from typing import List, Tuple
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.markdown_parser import MarkdownParser
from src.embeddings.chunking import DocumentChunker
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase
from src.storage.models import Article, Chunk


def find_all_articles(base_path: Path, source_name: str) -> List[Tuple[Path, str]]:
    """Find all markdown articles in the scraped_data directory.

    Args:
        base_path: Base directory to search (e.g., scraped_data/bc-cancer/articles)
        source_name: Name of the source (e.g., "BC Cancer")

    Returns:
        List of tuples (path, source_name)
    """
    articles = []

    # Find all .md files recursively
    for md_file in base_path.rglob("*.md"):
        # Skip non-article files (like README)
        if md_file.name.lower() not in ["readme.md", "index.md"]:
            articles.append((md_file, source_name))

    # Sort for consistent ordering
    articles.sort(key=lambda x: x[0])

    return articles


def parse_articles(article_paths_with_source: List[Tuple[Path, str]], parser: MarkdownParser) -> Tuple[List[Article], List[Tuple[Path, str]]]:
    """Parse all articles, collecting successes and failures.

    Args:
        article_paths_with_source: List of tuples (path, source_name)
        parser: MarkdownParser instance

    Returns:
        Tuple of (successful articles, failed paths with source)
    """
    articles = []
    failed = []

    print(f"Parsing {len(article_paths_with_source)} articles...")
    print()

    for i, (article_path, source_name) in enumerate(article_paths_with_source, 1):
        try:
            print(f"[{i}/{len(article_paths_with_source)}] Parsing: {article_path.name} (Source: {source_name})")
            article = parser.parse_file(article_path)
            # Set the source on the parsed article
            article.source = source_name
            articles.append(article)
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            failed.append((article_path, source_name))

    print()
    print(f"✅ Successfully parsed: {len(articles)} articles")
    if failed:
        print(f"❌ Failed to parse: {len(failed)} articles")
        for path, source in failed:
            print(f"   - {path.name} ({source})")
    print()

    return articles, failed


def chunk_articles(articles: List[Article], chunker: DocumentChunker) -> List[Chunk]:
    """Chunk all articles into paragraphs.

    Args:
        articles: List of parsed articles
        chunker: DocumentChunker instance

    Returns:
        List of all chunks
    """
    all_chunks = []

    print(f"Chunking {len(articles)} articles...")
    print()

    for i, article in enumerate(articles, 1):
        chunks = chunker.chunk_article(article)
        all_chunks.extend(chunks)

        if i % 10 == 0:  # Progress every 10 articles
            print(f"   Processed {i}/{len(articles)} articles ({len(all_chunks)} chunks so far)")

    print()
    print(f"✅ Created {len(all_chunks)} total chunks")
    print()

    return all_chunks


def generate_embeddings(chunks: List[Chunk], generator: EmbeddingGenerator) -> List[Chunk]:
    """Generate embeddings for all chunks.

    Args:
        chunks: List of chunks without embeddings
        generator: EmbeddingGenerator instance

    Returns:
        List of chunks with embeddings
    """
    print(f"Generating embeddings for {len(chunks)} chunks...")
    print(f"(Using batch size: {generator.batch_size})")
    print()

    # Reset stats for clean measurement
    generator.reset_stats()

    # Generate embeddings with progress
    start_time = time.time()
    embedded_chunks = generator.embed_chunks(chunks, show_progress=True)
    elapsed_time = time.time() - start_time

    print()
    print(f"✅ Generated {len(embedded_chunks)} embeddings in {elapsed_time:.1f} seconds")

    # Show cost statistics
    stats = generator.get_embedding_stats()
    print()
    print("📊 Embedding Statistics:")
    print(f"   Model: {stats['model']}")
    print(f"   Total tokens: {stats['total_tokens_used']:,}")
    print(f"   Total cost: ${stats['total_cost']:.6f}")
    print(f"   Cost per 1K tokens: ${stats['cost_per_1k_tokens']:.6f}")
    print()

    return embedded_chunks


def store_in_database(chunks: List[Chunk], db: VectorDatabase) -> None:
    """Store chunks in the vector database.

    Args:
        chunks: List of chunks with embeddings
        db: VectorDatabase instance
    """
    print(f"Storing {len(chunks)} chunks in vector database...")
    print()

    # Add chunks with progress
    db.add_chunks(chunks, batch_size=100, show_progress=True)

    print()
    print("✅ All chunks stored in database")
    print()


def show_database_stats(db: VectorDatabase) -> None:
    """Display database statistics.

    Args:
        db: VectorDatabase instance
    """
    stats = db.get_stats()

    print("=" * 70)
    print("Database Statistics")
    print("=" * 70)
    print()
    print(f"Collection: {stats['collection_name']}")
    print(f"Total chunks: {stats['total_chunks']:,}")
    print(f"Unique articles (sample): {stats.get('unique_articles_sample', 'N/A')}")
    print(f"Unique sections (sample): {stats.get('unique_sections_sample', 'N/A')}")
    print(f"Distance metric: {stats['distance_metric']}")
    print(f"Persist directory: {stats['persist_directory']}")
    print()


def test_search_quality(db: VectorDatabase, generator: EmbeddingGenerator) -> None:
    """Test search quality with sample queries.

    Args:
        db: VectorDatabase instance
        generator: EmbeddingGenerator instance
    """
    print("=" * 70)
    print("Testing Search Quality")
    print("=" * 70)
    print()

    test_queries = [
        "What are the symptoms of breast cancer?",
        "How is lung cancer diagnosed?",
        "What are treatment options for pancreatic cancer?",
        "What causes colorectal cancer?",
        "How can I prevent skin cancer?",
    ]

    for query in test_queries:
        print(f"Query: \"{query}\"")
        print("-" * 70)

        # Generate query embedding
        query_embedding = generator.embed_text(query)

        # Search
        results = db.search(query_embedding, n_results=3)

        if not results:
            print("   No results found")
        else:
            for result in results:
                chunk = result.chunk
                text_preview = chunk.text[:80] + "..." if len(chunk.text) > 80 else chunk.text

                print(f"  [{result.rank}] Score: {result.similarity_score:.4f}")
                print(f"      Article: {chunk.article_title}")
                print(f"      Section: {chunk.section}")
                print(f"      Text: \"{text_preview}\"")

        print()


def main():
    """Main ingestion pipeline."""
    print("=" * 70)
    print("Care-Beacon Medical RAG - Full Corpus Ingestion")
    print("=" * 70)
    print()

    # Define source directories
    SOURCES = {
        "bc-cancer": "BC Cancer",
        "canadian-cancer-society": "Canadian Cancer Society"
    }

    # Initialize components
    print("Initializing components...")
    parser = MarkdownParser()
    chunker = DocumentChunker()
    generator = EmbeddingGenerator()
    db = VectorDatabase()
    print("✅ Components initialized")
    print()

    # Check if database already has data
    existing_count = db.count()
    if existing_count > 0:
        print(f"⚠️  Database already contains {existing_count} chunks")
        print("   Clearing database for fresh ingestion...")
        db.reset()
        print("✅ Database cleared")
        print()

    # Step 1: Find all articles from all sources
    print("=" * 70)
    print("Step 1: Finding All Articles")
    print("=" * 70)
    print()

    all_article_paths = []
    source_counts = {}

    for source_dir, source_name in SOURCES.items():
        articles_dir = project_root / "scraped_data" / source_dir / "articles"

        if not articles_dir.exists():
            print(f"⚠️  Directory not found: {articles_dir}")
            print(f"   Skipping {source_name}")
            continue

        article_paths = find_all_articles(articles_dir, source_name)
        all_article_paths.extend(article_paths)
        source_counts[source_name] = len(article_paths)

        print(f"Found {len(article_paths)} articles from {source_name}")

    print()
    print(f"Total: {len(all_article_paths)} markdown files from {len(source_counts)} sources")
    print()

    if not all_article_paths:
        print("❌ No articles found. Check the scraped_data directory structure.")
        print("   Expected structure:")
        for source_dir in SOURCES.keys():
            print(f"   - scraped_data/{source_dir}/articles/")
        return

    # Step 2: Parse articles
    print("=" * 70)
    print("Step 2: Parsing Articles")
    print("=" * 70)
    print()

    articles, failed_paths = parse_articles(all_article_paths, parser)

    if not articles:
        print("❌ No articles were successfully parsed.")
        return

    # Step 3: Chunk articles
    print("=" * 70)
    print("Step 3: Chunking Articles")
    print("=" * 70)
    print()

    all_chunks = chunk_articles(articles, chunker)

    if not all_chunks:
        print("❌ No chunks were created.")
        return

    # Show chunking statistics
    print("📊 Chunking Statistics:")
    avg_chunk_length = sum(len(c.text) for c in all_chunks) / len(all_chunks)
    print(f"   Total chunks: {len(all_chunks):,}")
    print(f"   Average chunk length: {avg_chunk_length:.0f} characters")
    print(f"   Min chunk length: {min(len(c.text) for c in all_chunks)} characters")
    print(f"   Max chunk length: {max(len(c.text) for c in all_chunks)} characters")
    print()

    # Step 4: Generate embeddings
    print("=" * 70)
    print("Step 4: Generating Embeddings")
    print("=" * 70)
    print()

    embedded_chunks = generate_embeddings(all_chunks, generator)

    # Step 5: Store in database
    print("=" * 70)
    print("Step 5: Storing in Vector Database")
    print("=" * 70)
    print()

    store_in_database(embedded_chunks, db)

    # Step 6: Show database statistics
    show_database_stats(db)

    # Step 7: Test search quality
    test_search_quality(db, generator)

    # Final summary
    print("=" * 70)
    print("Ingestion Complete!")
    print("=" * 70)
    print()
    print("📊 Final Summary:")
    print(f"   Total articles processed: {len(articles)}")

    # Count articles by source
    articles_by_source = {}
    for article in articles:
        source = article.source
        articles_by_source[source] = articles_by_source.get(source, 0) + 1

    print()
    print("   Articles by source:")
    for source, count in sorted(articles_by_source.items()):
        print(f"      - {source}: {count} articles")

    print()
    print(f"   Total chunks: {len(embedded_chunks):,}")
    print(f"   Database size: {db.count():,} chunks")

    embedding_stats = generator.get_embedding_stats()
    print(f"   Embedding cost: ${embedding_stats['total_cost']:.6f}")
    print()

    if failed_paths:
        print(f"⚠️  {len(failed_paths)} articles failed to parse:")
        for path, source in failed_paths:
            print(f"   - {path.name} ({source})")
        print()

    print("Next Steps:")
    print("   - Database is ready for querying")
    print("   - Source filtering is available in vector search")
    print("   - Proceed to update UI for source filtering")
    print()


if __name__ == "__main__":
    main()
