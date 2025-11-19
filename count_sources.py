"""Count chunks by source in the vector database."""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from src.storage.vector_db import create_vector_database

# Create vector database
vector_db = create_vector_database()

print("Sampling chunks to count sources...")
print("(Fetching 1000 chunks)")
print()

# Get a larger sample
chunks = vector_db.peek(limit=1000)

# Count by source
source_counts = defaultdict(int)
for chunk in chunks:
    source = chunk.source if hasattr(chunk, 'source') else 'UNKNOWN'
    source_counts[source] += 1

print("=" * 70)
print("SOURCE DISTRIBUTION (1000 chunk sample):")
print("=" * 70)

for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
    percentage = (count / len(chunks)) * 100
    print(f"{source:40} {count:6} chunks  ({percentage:5.1f}%)")

print("=" * 70)
print(f"Total chunks sampled: {len(chunks)}")
print(f"Total chunks in database: {vector_db.count()}")
print()

# Check for BC Cancer specifically
bc_cancer_count = source_counts.get("BC Cancer", 0)
if bc_cancer_count == 0:
    print("⚠️  WARNING: No 'BC Cancer' chunks found in sample!")
    print()
    print("Possible source names that might match:")
    for source in source_counts.keys():
        if "bc" in source.lower() or "cancer" in source.lower():
            print(f"  - '{source}'")
