"""Memory-efficient ingestion for Render free tier (512MB limit).

This script processes articles in small batches to avoid running out of memory.
Optimized for Render.com free tier deployment.
"""

import sys
import gc
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

# Memory-efficient batch size (process 50 articles at a time)
BATCH_SIZE = 50


def find_all_articles(base_path: Path, source_name: str) -> List[Tuple[Path, str]]:
    """Find all markdown articles."""
    articles = []
    for md_file in base_path.rglob("*.md"):
        if md_file.name.lower() not in ["readme.md", "index.md"]:
            articles.append((md_file, source_name))
    articles.sort(key=lambda x: x[0])
    return articles


def process_batch(
    article_paths_batch: List[Tuple[Path, str]],
    parser: MarkdownParser,
    chunker: DocumentChunker,
    generator: EmbeddingGenerator,
    db: VectorDatabase,
    batch_num: int,
    total_batches: int,
) -> Tuple[int, int, int]:
    """Process a batch of articles and write to database immediately.

    Returns:
        Tuple of (articles_processed, chunks_created, chunks_stored)
    """
    print(f"\n{'='*70}")
    print(f"Batch {batch_num}/{total_batches} ({len(article_paths_batch)} articles)")
    print(f"{'='*70}\n")

    # Step 1: Parse articles
    print(f"[1/4] Parsing {len(article_paths_batch)} articles...")
    articles = []
    for article_path, source_name in article_paths_batch:
        try:
            article = parser.parse_file(article_path)
            article.source = source_name
            articles.append(article)
        except Exception as e:
            print(f"  ⚠️  Failed to parse {article_path.name}: {e}")

    if not articles:
        print("  No articles parsed in this batch")
        return 0, 0, 0

    print(f"  ✅ Parsed {len(articles)} articles")

    # Step 2: Chunk articles
    print(f"\n[2/4] Chunking articles...")
    all_chunks = []
    for article in articles:
        chunks = chunker.chunk_article(article)
        all_chunks.extend(chunks)

    print(f"  ✅ Created {len(all_chunks)} chunks")

    # Clear articles from memory
    del articles
    gc.collect()

    # Step 3: Generate embeddings
    print(f"\n[3/4] Generating embeddings...")
    embedded_chunks = generator.embed_chunks(all_chunks, show_progress=False)
    print(f"  ✅ Generated {len(embedded_chunks)} embeddings")

    # Clear unembedded chunks from memory
    del all_chunks
    gc.collect()

    # Step 4: Store in database
    print(f"\n[4/4] Storing in database...")
    db.add_chunks(embedded_chunks, batch_size=100, show_progress=False)
    print(f"  ✅ Stored {len(embedded_chunks)} chunks")

    chunks_stored = len(embedded_chunks)

    # Clear embedded chunks from memory
    del embedded_chunks
    gc.collect()

    return len(article_paths_batch), len(all_chunks) if 'all_chunks' in locals() else chunks_stored, chunks_stored


def main():
    """Memory-efficient ingestion pipeline."""
    print("="*70)
    print("Care-Beacon Low-Memory Ingestion (Render Free Tier)")
    print("="*70)
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
    print("✅ Components initialized\n")

    # Check if database already has data
    existing_count = db.count()
    if existing_count > 0:
        print(f"⚠️  Database already contains {existing_count} chunks")
        print("   Clearing database for fresh ingestion...")
        db.reset()
        print("✅ Database cleared\n")

    # Find all articles from all sources
    print("="*70)
    print("Finding Articles")
    print("="*70)
    print()

    all_article_paths = []
    for source_dir, source_name in SOURCES.items():
        articles_dir = project_root / "scraped_data" / source_dir / "articles"

        if not articles_dir.exists():
            print(f"⚠️  Directory not found: {articles_dir}")
            continue

        article_paths = find_all_articles(articles_dir, source_name)
        all_article_paths.extend(article_paths)
        print(f"  {source_name}: {len(article_paths)} articles")

    print(f"\n  Total: {len(all_article_paths)} articles\n")

    if not all_article_paths:
        print("❌ No articles found")
        return

    # Process in batches
    print("="*70)
    print(f"Processing in Batches (batch size: {BATCH_SIZE})")
    print("="*70)

    total_batches = (len(all_article_paths) + BATCH_SIZE - 1) // BATCH_SIZE
    total_articles_processed = 0
    total_chunks_created = 0
    total_chunks_stored = 0

    start_time = time.time()

    for i in range(0, len(all_article_paths), BATCH_SIZE):
        batch = all_article_paths[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1

        articles_processed, chunks_created, chunks_stored = process_batch(
            batch,
            parser,
            chunker,
            generator,
            db,
            batch_num,
            total_batches
        )

        total_articles_processed += articles_processed
        total_chunks_created += chunks_created
        total_chunks_stored += chunks_stored

        # Force garbage collection between batches
        gc.collect()

    elapsed_time = time.time() - start_time

    # Final statistics
    print("\n" + "="*70)
    print("Ingestion Complete!")
    print("="*70)
    print()
    print(f"📊 Summary:")
    print(f"   Total articles processed: {total_articles_processed}")
    print(f"   Total chunks created: {total_chunks_created}")
    print(f"   Total chunks stored: {total_chunks_stored}")
    print(f"   Database size: {db.count()} chunks")
    print(f"   Time elapsed: {elapsed_time:.1f} seconds")
    print()

    # Show embedding stats
    stats = generator.get_embedding_stats()
    print(f"💰 Embedding Cost:")
    print(f"   Model: {stats['model']}")
    print(f"   Total tokens: {stats['total_tokens_used']:,}")
    print(f"   Total cost: ${stats['total_cost']:.6f}")
    print()

    # Verify database
    final_count = db.count()
    if final_count > 0:
        print(f"✅ Verification: Database contains {final_count} chunks")
    else:
        print(f"❌ Warning: Database is empty!")
    print()


if __name__ == "__main__":
    main()
