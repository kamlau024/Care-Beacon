# Testing Guide - How to Test Your Ingestion

This guide shows you how to verify and test the ingested medical articles in the vector database.

## Quick Verification (Automated)

The fastest way to verify the ingestion worked:

```bash
# Activate environment
conda activate care-beacon

# Run automated verification
python scripts/verify_ingestion.py
```

**What it checks**:
- ✅ Database has data
- ✅ Chunks have embeddings
- ✅ Metadata is complete
- ✅ Search functionality works
- ✅ Metadata filtering works
- ✅ Multiple cancer types present

**Expected output**: All checks pass ✅

## Interactive Testing (Manual)

For hands-on testing with your own queries:

```bash
# Activate environment
conda activate care-beacon

# Run interactive query tool
python scripts/test_query.py
```

### Test Menu Options

**1. Show database statistics**
- Shows total chunks, collection name, storage location
- Quick overview of what's in the database

**2. View sample chunks**
- Shows actual chunks from the database
- See chunk IDs, article titles, sections, and text

**3. Run predefined sample queries**
- Tests 5 common medical questions
- Shows search quality with real queries
- Examples:
  - "What are the symptoms of breast cancer?"
  - "How is lung cancer diagnosed?"
  - "What are treatment options for pancreatic cancer?"

**4. Enter custom query**
- Ask your own questions
- Specify number of results to return
- See similarity scores and matching chunks

**5. Test metadata filtering**
- Filter by cancer type, article, or section
- Example: Find only "Breast Cancer" articles
- Verify targeted search works

**6. Interactive query mode**
- Continuous query session
- Ask multiple questions in a row
- Great for testing different query types

**7. Exit**
- Quit the program

## Example Usage

### Test Search Quality

```bash
$ python scripts/test_query.py

# Select option 4: Enter custom query
> 4

Enter your question: What are the side effects of chemotherapy?
Number of results (default 5): 3

[1] Similarity Score: 0.7234
    Article: Managing Symptoms & Side Effects
    Section: Side Effects of Treatment
    Text: "Chemotherapy can cause various side effects including..."
```

### Test Metadata Filtering

```bash
# Select option 5: Test metadata filtering

Enter your question: What are treatment options?
Filter field: cancer_type
Filter value: Lung Cancer
Number of results: 3

# Results will only show Lung Cancer articles
```

### Interactive Mode

```bash
# Select option 6: Interactive query mode

Your question: What are symptoms of breast cancer?
Number of results: 3

# Shows results...

Your question: How is it diagnosed?
Number of results: 3

# Shows more results...

Your question: quit
```

## Command Line Quick Tests

### Check Database Count

```bash
python -c "
from src.storage.vector_db import VectorDatabase
db = VectorDatabase()
print(f'Total chunks: {db.count():,}')
"
```

Expected output:
```
Total chunks: 4,064
```

### Test a Single Query

```bash
python -c "
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase

generator = EmbeddingGenerator()
db = VectorDatabase()

query = 'What are symptoms of breast cancer?'
embedding = generator.embed_text(query)
results = db.search(embedding, n_results=3)

for result in results:
    print(f'{result.similarity_score:.4f}: {result.chunk.article_title}')
"
```

### View Sample Chunks

```bash
python -c "
from src.storage.vector_db import VectorDatabase

db = VectorDatabase()
samples = db.peek(limit=3)

for i, chunk in enumerate(samples, 1):
    print(f'{i}. {chunk.article_title} - {chunk.section}')
    print(f'   {chunk.text[:100]}...')
    print()
"
```

## Testing Specific Features

### Test Different Cancer Types

```python
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase

generator = EmbeddingGenerator()
db = VectorDatabase()

cancer_types = ["breast cancer", "lung cancer", "colorectal cancer", "pancreatic cancer"]

for cancer in cancer_types:
    query = f"What are symptoms of {cancer}?"
    embedding = generator.embed_text(query)
    results = db.search(embedding, n_results=1)

    if results:
        print(f"{cancer.title()}: {results[0].similarity_score:.4f}")
        print(f"  Found: {results[0].chunk.article_title}")
    print()
```

### Test Metadata Filtering

```python
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase

generator = EmbeddingGenerator()
db = VectorDatabase()

query = "What are treatment options?"
embedding = generator.embed_text(query)

# Without filter
results_all = db.search(embedding, n_results=5)
print(f"Without filter: {len(results_all)} results")

# With filter
results_filtered = db.search(
    embedding,
    n_results=5,
    where={"cancer_type": "Breast Cancer"}
)
print(f"With filter (Breast Cancer): {len(results_filtered)} results")
```

### Test Search Quality

```python
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase

generator = EmbeddingGenerator()
db = VectorDatabase()

# Test queries with expected articles
test_cases = [
    ("What are symptoms of breast cancer?", "Breast Cancer"),
    ("How is lung cancer diagnosed?", "Lung"),
    ("Prevention of colorectal cancer?", "Colorectal"),
]

print("Search Quality Test:")
print("-" * 50)

for query, expected_article in test_cases:
    embedding = generator.embed_text(query)
    results = db.search(embedding, n_results=1)

    if results:
        top_result = results[0]
        article = top_result.chunk.article_title
        score = top_result.similarity_score

        # Check if top result matches expected article
        match = expected_article.lower() in article.lower()
        status = "✅" if match else "⚠️"

        print(f"{status} Query: {query[:50]}...")
        print(f"   Expected: {expected_article}")
        print(f"   Got: {article} (score: {score:.4f})")
    print()
```

## Common Issues

### Issue: "Database is empty"

**Cause**: Ingestion hasn't been run or database was cleared

**Solution**:
```bash
python scripts/ingest_all_articles.py
```

### Issue: "No results found"

**Possible causes**:
1. Query is too specific or uses uncommon terms
2. Database doesn't have articles on that topic
3. Embeddings not generated properly

**Troubleshooting**:
```bash
# Check database has data
python scripts/verify_ingestion.py

# Try simpler queries
python scripts/test_query.py
# Select option 3 to run sample queries
```

### Issue: Low similarity scores

**Expected behavior**:
- Excellent match: 0.7 - 1.0
- Good match: 0.5 - 0.7
- Moderate match: 0.3 - 0.5
- Poor match: < 0.3

If all scores are consistently low (< 0.4), check if embeddings were generated correctly.

### Issue: Telemetry warnings

**Warning**: `Failed to send telemetry event...`

**Cause**: ChromaDB trying to send anonymous usage statistics

**Impact**: None - these warnings are harmless and don't affect functionality

**Solution**: Ignore them, or disable in ChromaDB settings if desired

## Interpreting Results

### Similarity Scores

- **0.8+**: Excellent - nearly perfect match
- **0.6-0.8**: Very good - highly relevant
- **0.4-0.6**: Good - relevant content
- **0.2-0.4**: Fair - somewhat related
- **< 0.2**: Poor - not very relevant

### Example Results

Good result:
```
[1] Similarity Score: 0.8224
    Article: Breast Cancer
    Section: What are the signs and symptoms of breast cancer?
    Text: "These are some symptoms of breast cancer:"
```

This is excellent! Query directly matches content.

Fair result:
```
[3] Similarity Score: 0.4123
    Article: About Cancer
    Section: General Information
    Text: "Cancer affects millions of people worldwide..."
```

This is too generic - might be in top results but not ideal.

## Next Steps

After verifying ingestion works:

1. **Test more queries**: Try edge cases and specific medical terms
2. **Test metadata filtering**: Verify you can narrow by cancer type
3. **Check search quality**: Ensure top results are relevant
4. **Proceed to Phase 2**: Build the full RAG system with LLM integration

## Scripts Reference

| Script | Purpose | Interactive |
|--------|---------|-------------|
| `verify_ingestion.py` | Automated checks | No |
| `test_query.py` | Full testing suite | Yes |
| `test_vector_db.py` | Database functionality | No |
| `ingest_all_articles.py` | Re-run ingestion | No |

## Quick Commands Cheat Sheet

```bash
# Verify ingestion worked
python scripts/verify_ingestion.py

# Interactive testing
python scripts/test_query.py

# Check database count
python -c "from src.storage.vector_db import VectorDatabase; print(f'{VectorDatabase().count():,} chunks')"

# View sample chunk
python -c "from src.storage.vector_db import VectorDatabase; print(VectorDatabase().peek(1)[0].text[:200])"

# Test single query
python -c "from src.embeddings.embedding_generator import EmbeddingGenerator; from src.storage.vector_db import VectorDatabase; db = VectorDatabase(); gen = EmbeddingGenerator(); results = db.search(gen.embed_text('breast cancer symptoms'), n_results=1); print(f'{results[0].similarity_score:.4f}: {results[0].chunk.article_title}')"
```

---

**Last Updated**: 2025-11-07
**Related**: `CHECKPOINT_1.6_COMPLETE.md`, `README.md`
