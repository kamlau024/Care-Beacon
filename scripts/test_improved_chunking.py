"""Test improved chunking logic with bullet points."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.markdown_parser import MarkdownParser
from src.embeddings.chunking import DocumentChunker

# Test with the BC Cancer prostate article
article_path = project_root / "scraped_data/bc-cancer/articles/health-info/types-of-cancer/pelvic-area/prostate.md"

print("="*80)
print("Testing Improved Chunking Logic")
print("="*80)
print()

# Parse article
parser = MarkdownParser()
article = parser.parse_file(article_path)
article.source = "BC Cancer"

print(f"Article: {article.title}")
print(f"Sections: {len(article.sections)}")
print()

# Chunk article
chunker = DocumentChunker()
chunks = chunker.chunk_article(article)

print(f"Total chunks created: {len(chunks)}")
print()

# Find chunks related to PSA diagnosis
print("="*80)
print("Chunks from 'How is prostate cancer diagnosed?' section:")
print("="*80)
print()

diagnostic_chunks = [c for c in chunks if c.section == "How is prostate cancer diagnosed?"]
print(f"Found {len(diagnostic_chunks)} chunks in this section")
print()

for i, chunk in enumerate(diagnostic_chunks, 1):
    print(f"Chunk {i}:")
    print(f"  ID: {chunk.chunk_id}")
    print(f"  Length: {len(chunk.text)} characters")
    print(f"  Contains '4 and 7': {'Yes' if '4 and 7' in chunk.text else 'No'}")
    print(f"  Preview: {chunk.text[:100]}...")
    print()

# Find the specific chunk with PSA normal range
print("="*80)
print("Searching for chunk with PSA normal range (4-7 ng/mL):")
print("="*80)
print()

psa_chunks = [c for c in chunks if '4 and 7' in c.text]
if psa_chunks:
    for chunk in psa_chunks:
        print(f"✅ FOUND!")
        print(f"  Chunk ID: {chunk.chunk_id}")
        print(f"  Section: {chunk.section}")
        print(f"  Length: {len(chunk.text)} characters")
        print()
        print("Full content:")
        print("-" * 80)
        print(chunk.text)
        print("-" * 80)
else:
    print("❌ NOT FOUND")

print()
print("="*80)
print("Test complete!")
print("="*80)
