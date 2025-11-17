#!/usr/bin/env python3
"""
Ingest all medical articles directly into Qdrant Cloud.

This script processes all markdown articles from scraped_data/ and ingests them
directly into Qdrant Cloud (no ChromaDB migration needed).

Usage:
    # Ingest all sources
    python scripts/ingest_all_articles_to_qdrant.py

    # Ingest only BC Cancer
    python scripts/ingest_all_articles_to_qdrant.py --source bc-cancer

    # Ingest only Canadian Cancer Society
    python scripts/ingest_all_articles_to_qdrant.py --source canadian-cancer-society

Prerequisites:
    - Qdrant Cloud cluster created
    - QDRANT_URL and QDRANT_API_KEY set in .env
    - VECTOR_DB_PROVIDER=qdrant in .env
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.ingestion.markdown_parser import MarkdownParser
from src.embeddings.chunking import DocumentChunker
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.qdrant_db import QdrantVectorDatabase
from src.storage.models import Article, Chunk
from src.config_loader import get_config


def find_all_markdown_files(base_paths):
    """Find all markdown files in the given base paths."""
    markdown_files = []

    for base_path in base_paths:
        path = Path(base_path)
        if not path.exists():
            print(f"⚠️  Warning: Path not found: {base_path}")
            continue

        # Find all .md files recursively
        for md_file in path.rglob("*.md"):
            markdown_files.append(md_file)

    return sorted(markdown_files)


def chunk_articles(articles, chunker):
    """Create chunks from articles."""
    print("Creating chunks from articles...")
    print()

    all_chunks = []

    for i, article in enumerate(articles, 1):
        print(f"Chunking article {i}/{len(articles)}: {article.title}")

        # Create chunks
        chunks = chunker.chunk_article(article)
        all_chunks.extend(chunks)

        print(f"  ✓ Created {len(chunks)} chunks")

    print()
    print(f"✅ Total chunks created: {len(all_chunks)}")
    print()

    return all_chunks


def generate_embeddings(chunks, generator, batch_size=100):
    """Generate embeddings for chunks."""
    print(f"Generating embeddings for {len(chunks)} chunks...")
    print(f"Batch size: {batch_size}")
    print()

    # Generate embeddings in batches
    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_num = i // batch_size + 1

        print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        # Extract text from batch
        texts = [chunk.text for chunk in batch]

        # Generate embeddings using the correct method name
        embeddings = generator.embed_batch(texts)

        # Assign embeddings to chunks
        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding

        print(f"  ✓ Generated {len(embeddings)} embeddings")

    print()
    print("✅ All embeddings generated")
    print()

    return chunks


def store_in_qdrant(chunks, db, batch_size=100):
    """Store chunks in Qdrant Cloud."""
    print(f"Storing {len(chunks)} chunks in Qdrant Cloud...")
    print(f"Batch size: {batch_size}")
    print()

    # Add chunks with progress
    db.add_chunks(chunks, batch_size=batch_size, show_progress=True)

    print()
    print("✅ All chunks stored in Qdrant Cloud")
    print()


def main(source_filter=None):
    """Main ingestion workflow.

    Args:
        source_filter: Optional source name to filter (e.g., "bc-cancer", "canadian-cancer-society")
    """
    print("=" * 70)
    print("Care-Beacon: Ingest Articles to Qdrant Cloud")
    print("=" * 70)
    print()

    # Verify Qdrant configuration
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        print("❌ Error: QDRANT_URL not set in .env file")
        print("   Please add your Qdrant Cloud cluster URL")
        sys.exit(1)

    if not qdrant_api_key:
        print("❌ Error: QDRANT_API_KEY not set in .env file")
        print("   Please add your Qdrant Cloud API key")
        sys.exit(1)

    print(f"✓ Qdrant URL: {qdrant_url}")
    print(f"✓ API Key: {qdrant_api_key[:20]}...")
    print()

    # Define all available source folders
    all_source_folders = {
        "bc-cancer": {
            "path": "scraped_data/bc-cancer/articles",
            "name": "BC Cancer"
        },
        "canadian-cancer-society": {
            "path": "scraped_data/canadian-cancer-society/articles",
            "name": "Canadian Cancer Society"
        },
        "cleveland-clinic": {
            "path": "scraped_data/cleveland-clinic/articles",
            "name": "Cleveland Clinic"
        }
    }

    # Filter sources if specified
    if source_filter:
        if source_filter not in all_source_folders:
            print(f"❌ Error: Unknown source '{source_filter}'")
            print(f"   Available sources: {', '.join(all_source_folders.keys())}")
            sys.exit(1)

        source_folders = {
            all_source_folders[source_filter]["path"]: all_source_folders[source_filter]["name"]
        }
        print(f"📁 Filtering to source: {all_source_folders[source_filter]['name']}")
        print()
    else:
        source_folders = {
            info["path"]: info["name"]
            for info in all_source_folders.values()
        }
        print("📁 Ingesting from all sources")
        print()

    # Initialize components
    print("Initializing components...")
    parser = MarkdownParser()
    chunker = DocumentChunker()
    generator = EmbeddingGenerator()
    db = QdrantVectorDatabase(url=qdrant_url, api_key=qdrant_api_key)
    print("✅ Components initialized")
    print()

    # Check if collection already has data
    existing_count = db.count()
    if existing_count > 0:
        if source_filter:
            # Additive ingestion: delete only data from the specified source
            source_name = all_source_folders[source_filter]["name"]
            print(f"⚠️  Qdrant collection already contains {existing_count:,} chunks")
            print(f"📝 Additive ingestion mode: Will replace data from '{source_name}' only")
            print()

            response = input(f"Delete existing '{source_name}' data and re-ingest? (yes/no): ")
            if response.lower() in ['yes', 'y']:
                print(f"Deleting existing data from '{source_name}'...")

                # Create index on 'source' field if it doesn't exist (required for filtering)
                from qdrant_client.models import Filter, FieldCondition, MatchValue, PayloadSchemaType
                try:
                    db.client.create_payload_index(
                        collection_name=db.collection_name,
                        field_name="source",
                        field_schema=PayloadSchemaType.KEYWORD
                    )
                    print("  ✓ Created index on 'source' field")
                except Exception as e:
                    # Index might already exist, that's OK
                    if "already exists" not in str(e).lower():
                        print(f"  ⚠️  Note: Could not create index: {e}")

                # Delete by source using Qdrant filter
                db.client.delete(
                    collection_name=db.collection_name,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="source",
                                match=MatchValue(value=source_name)
                            )
                        ]
                    )
                )

                new_count = db.count()
                deleted_count = existing_count - new_count
                print(f"✅ Deleted {deleted_count:,} chunks from '{source_name}'")
                print(f"   Remaining chunks from other sources: {new_count:,}")
                print()
            else:
                print("❌ Aborted. Existing data will be kept.")
                print("   Note: This may result in duplicate data!")
                print()
        else:
            # Full ingestion: prompt to delete all data
            print(f"⚠️  Qdrant collection already contains {existing_count:,} chunks")
            response = input("Do you want to DELETE all existing data and start fresh? (yes/no): ")
            if response.lower() in ['yes', 'y']:
                print("Deleting existing collection...")
                db.reset()
                print("✅ Collection reset")
                print()
            else:
                print("❌ Aborted. Existing data will be kept.")
                print("   Note: This may result in duplicate data!")
                print()

    # Find all markdown files
    print("Finding markdown files...")
    print()

    all_files = []
    for folder, source_name in source_folders.items():
        folder_path = project_root / folder
        if folder_path.exists():
            files = find_all_markdown_files([folder_path])
            print(f"  {source_name}: {len(files)} files")
            all_files.extend(files)
        else:
            print(f"  ⚠️  {source_name}: folder not found at {folder}")

    print()
    print(f"✅ Total markdown files found: {len(all_files)}")
    print()

    if len(all_files) == 0:
        print("❌ No markdown files found. Nothing to ingest.")
        return

    # Parse articles
    print("=" * 70)
    print("Step 1: Parsing Markdown Files")
    print("=" * 70)
    print()

    articles = []
    parse_errors = 0

    for i, file_path in enumerate(all_files, 1):
        print(f"[{i}/{len(all_files)}] Parsing: {file_path.name}")

        try:
            article = parser.parse_file(str(file_path))
            articles.append(article)
        except Exception as e:
            print(f"  ❌ Error parsing file: {e}")
            parse_errors += 1

    print()
    print(f"✅ Successfully parsed: {len(articles)} articles")
    if parse_errors > 0:
        print(f"⚠️  Failed to parse: {parse_errors} files")
    print()

    # Chunk articles
    print("=" * 70)
    print("Step 2: Creating Chunks")
    print("=" * 70)
    print()

    all_chunks = chunk_articles(articles, chunker)

    # Generate embeddings
    print("=" * 70)
    print("Step 3: Generating Embeddings")
    print("=" * 70)
    print()

    config = get_config()
    embedding_batch_size = config.get('embeddings.batch_size', 100)

    chunks_with_embeddings = generate_embeddings(
        all_chunks,
        generator,
        batch_size=embedding_batch_size
    )

    # Store in Qdrant
    print("=" * 70)
    print("Step 4: Storing in Qdrant Cloud")
    print("=" * 70)
    print()

    storage_batch_size = config.get('ingestion.chunk_batch_size', 100)

    store_in_qdrant(
        chunks_with_embeddings,
        db,
        batch_size=storage_batch_size
    )

    # Final statistics
    print("=" * 70)
    print("Ingestion Complete!")
    print("=" * 70)
    print()

    final_count = db.count()
    stats = db.get_stats()

    print(f"📊 Final Statistics:")
    print(f"   Total articles processed: {len(articles)}")
    print(f"   Total chunks created: {len(all_chunks)}")
    print(f"   Total chunks in Qdrant: {final_count:,}")
    print(f"   Unique articles (sample): {stats.get('unique_articles_sample', 'N/A')}")
    print(f"   Collection: {stats.get('collection_name', 'N/A')}")
    print()

    if parse_errors > 0:
        print(f"⚠️  Note: {parse_errors} files failed to parse")
        print()

    print("✅ All articles successfully ingested into Qdrant Cloud!")
    print()
    print("Next steps:")
    print("1. Test locally: python scripts/start_api.py")
    print("2. Deploy to Render with QDRANT_URL and QDRANT_API_KEY env vars")
    print()


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Ingest medical articles into Qdrant Cloud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest all sources
  python scripts/ingest_all_articles_to_qdrant.py

  # Ingest only BC Cancer
  python scripts/ingest_all_articles_to_qdrant.py --source bc-cancer

  # Ingest only Canadian Cancer Society
  python scripts/ingest_all_articles_to_qdrant.py --source canadian-cancer-society

  # Ingest only Cleveland Clinic
  python scripts/ingest_all_articles_to_qdrant.py --source cleveland-clinic
        """
    )

    parser.add_argument(
        "--source",
        type=str,
        choices=["bc-cancer", "canadian-cancer-society", "cleveland-clinic"],
        help="Ingest only from the specified source (default: all sources)"
    )

    args = parser.parse_args()

    start_time = time.time()

    try:
        main(source_filter=args.source)
    except KeyboardInterrupt:
        print("\n\n❌ Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed_time = time.time() - start_time
    print(f"Total time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
