# Testing Guide - How to Verify Ingested Content

This guide covers verifying and querying the medical articles that have been ingested into Qdrant Cloud. It predates the Vercel migration and the switch away from ChromaDB; several of the standalone scripts it originally pointed at (`scripts/verify_ingestion.py`, `scripts/test_query.py` at the repo root) import a `VectorDatabase` class from `src.storage.vector_db` that **no longer exists** — that module is now a factory function, `create_vector_database()`, returning a `QdrantVectorDatabase` (`api/src/storage/qdrant_db.py`). Those root-level scripts have not been updated for either the Qdrant migration or the `api/` reorg and should be treated as unmaintained rather than run as-is.

The concepts below (similarity score interpretation, what "good ingestion" looks like) still apply; the code samples have been updated to match the actual current API.

## Quick Verification

There is no dedicated verification script that's known to work against the current codebase. The most reliable check is the API itself:

```bash
# Against the live deployment
curl https://care-beacon-health.vercel.app/api/v1/vector-db/stats

# Or locally, via `vercel dev`
curl http://localhost:3000/api/v1/vector-db/stats
```

This exercises `create_vector_database()` → `QdrantVectorDatabase.get_stats()` and reports collection size and source breakdown, which is a reasonable proxy for "did ingestion work."

`/api/health` performs a real Qdrant collection read and will return 503 if the cluster is unreachable — useful to check first if `vector-db/stats` fails.

## Command Line Quick Tests

These use the actual current classes, run from `api/` with the conda environment active:

### Check Collection Count

```bash
cd api
/opt/anaconda3/envs/care-beacon/bin/python -c "
from src.storage.vector_db import create_vector_database

db = create_vector_database()
print(f'Total chunks: {db.count():,}')
"
```

### Run a Single Query

```bash
cd api
/opt/anaconda3/envs/care-beacon/bin/python -c "
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import create_vector_database

generator = EmbeddingGenerator()
db = create_vector_database()

query = 'What are symptoms of breast cancer?'
embedding = generator.embed_text(query)
results = db.search(embedding, n_results=3)

for result in results:
    print(f'{result.similarity_score:.4f}: {result.chunk.article_title}')
"
```

### View Sample Chunks

```bash
cd api
/opt/anaconda3/envs/care-beacon/bin/python -c "
from src.storage.vector_db import create_vector_database

db = create_vector_database()
samples = db.peek(limit=3)

for i, chunk in enumerate(samples, 1):
    print(f'{i}. {chunk.article_title} - {chunk.section}')
    print(f'   {chunk.text[:100]}...')
    print()
"
```

### Test Metadata Filtering

```python
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import create_vector_database

generator = EmbeddingGenerator()
db = create_vector_database()

query = "What are treatment options?"
embedding = generator.embed_text(query)

results_all = db.search(embedding, n_results=5)
print(f"Without filter: {len(results_all)} results")

results_filtered = db.search(
    embedding,
    n_results=5,
    where={"cancer_type": "Breast Cancer"},
)
print(f"With filter (Breast Cancer): {len(results_filtered)} results")
```

## Common Issues

### Issue: "Database is empty" / `vector-db/stats` shows zero chunks

**Cause**: Ingestion hasn't been run against this Qdrant Cloud collection, or the collection was cleared.

**Solution**: Ingestion is local-only — there is no API endpoint for it anymore (the old on-demand ingestion endpoint was removed because it required spawning a subprocess, which serverless can't do).

```bash
make ingest   # runs `cd api && python scripts/ingest.py`
```

### Issue: "No results found" / low similarity scores

**Possible causes**:
1. Query is too specific or uses uncommon terms
2. The collection doesn't have articles on that topic
3. Embeddings weren't generated correctly during ingestion

**Troubleshooting**: check `GET /api/v1/vector-db/stats` for collection size, and re-run `make ingest` if it looks empty or stale.

### Issue: Telemetry warnings mentioning ChromaDB

If you see anything referencing ChromaDB telemetry, it's leftover noise from a dependency, not from this codebase — ChromaDB has been fully removed. Nothing here should be importing it; if something is, that's worth investigating as a real bug (report it, don't ignore it).

## Interpreting Similarity Scores

- **0.8+**: Excellent - nearly perfect match
- **0.6-0.8**: Very good - highly relevant
- **0.4-0.6**: Good - relevant content
- **0.2-0.4**: Fair - somewhat related
- **< 0.2**: Poor - not very relevant

These bands are a rule of thumb carried over from before the migration; they haven't been re-validated against the current embedding/retrieval configuration (`api/config/config.yaml` sets `min_similarity_threshold: 0.6` for re-ranked results, for reference).

## Scripts Reference

| Script | Location | Status |
|--------|----------|--------|
| `ingest.py` | `api/scripts/` | Current — the only supported way to (re)populate Qdrant Cloud, via `make ingest` |
| `verify_ingestion.py`, `test_query.py` | `scripts/` (repo root) | Stale — import a `VectorDatabase` class that no longer exists; do not rely on these without updating them first |

---

**Last Updated**: 2026-08-05
