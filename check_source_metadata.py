"""Quick script to verify source metadata in vector database."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.storage.vector_db import create_vector_database

# Create vector database
vector_db = create_vector_database()

# Get a sample of chunks
print("Getting sample chunks from vector database...")
chunks = vector_db.peek(limit=10)

print(f"\nFound {len(chunks)} sample chunks\n")
print("=" * 70)

# Check source metadata
sources = {}
for i, chunk in enumerate(chunks, 1):
    source = chunk.source if hasattr(chunk, 'source') else 'UNKNOWN'
    sources[source] = sources.get(source, 0) + 1

    print(f"\nChunk {i}:")
    print(f"  ID: {chunk.chunk_id}")
    print(f"  Source: {source}")
    print(f"  Article: {chunk.article_title}")
    print(f"  Section: {chunk.section}")
    print(f"  Text preview: {chunk.text[:100]}...")

print("\n" + "=" * 70)
print("Source distribution:")
for source, count in sources.items():
    print(f"  {source}: {count} chunks")

print("\n" + "=" * 70)
print("\nTo check all chunks, query the database stats:")
stats = vector_db.get_stats()
print(f"Total chunks: {stats.get('total_chunks', 0)}")
