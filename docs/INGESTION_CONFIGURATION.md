# Ingestion Batch Size Configuration

This document explains how to configure batch sizes for data ingestion. Ingestion is **local-only**: it runs as `api/scripts/ingest.py` via `make ingest`, on whatever machine you run it from. There used to be an on-demand ingestion API endpoint that could be triggered from a deployed environment (with its own Render.com memory constraints); it was removed because spawning a subprocess is not possible on Vercel's serverless functions. Batch-size tuning below is about the memory available on your local machine, not a hosting tier.

## Overview

The ingestion process supports configurable batch sizes to control local memory usage:

- **Article Batch Size**: Number of articles to process in one batch
- **Chunk Batch Size**: Number of chunks to add to the vector database (Qdrant Cloud) in one batch

## Configuration Methods

### Method 1: Config File (`api/config/config.yaml`)

```yaml
# Ingestion Configuration (for bulk data loading)
ingestion:
  article_batch_size: 10  # Number of articles to process per batch
  chunk_batch_size: 25    # Number of chunks to add to vector DB per batch
```

These are the actual current defaults in `api/config/config.yaml` — the chunk batch size was reduced from an earlier default of 50 specifically to avoid Qdrant Cloud request timeouts, per the comment in that file.

### Method 2: Environment Variables (Recommended for Production)

Set environment variables to override config file values:

```bash
export INGESTION_ARTICLE_BATCH_SIZE=10
export INGESTION_CHUNK_BATCH_SIZE=50
```

Or add to your `.env` file at the repo root:

```bash
# Optional: Ingestion Batch Sizes (for low-memory environments)
# Reduce these values if running out of memory during data ingestion
INGESTION_ARTICLE_BATCH_SIZE=10  # Number of articles to process per batch (default: 10)
INGESTION_CHUNK_BATCH_SIZE=50    # Number of chunks to add to vector DB per batch (default: 25 in config.yaml)
```

## Recommended Settings by Local Machine

Since ingestion only ever runs locally (`make ingest`), "environment" here means the machine you run it on, not a hosting tier — there is no Render.com or Vercel memory limit to work around, because ingestion never runs on either.

### Constrained machine (a few GB RAM free)

```bash
INGESTION_ARTICLE_BATCH_SIZE=5
INGESTION_CHUNK_BATCH_SIZE=25
```

### Typical development machine (8GB+ RAM)

```bash
INGESTION_ARTICLE_BATCH_SIZE=10
INGESTION_CHUNK_BATCH_SIZE=25
```

These match the current defaults in `api/config/config.yaml`.

### Plenty of headroom (16GB+ RAM)

```bash
INGESTION_ARTICLE_BATCH_SIZE=50
INGESTION_CHUNK_BATCH_SIZE=100
```

## Running Ingestion

The app reads Qdrant through an **alias** (`vector_db.collection_name`, `care-beacon-live`), never a collection directly. A re-ingest builds a new collection next to the live one, gets checked, and then the alias is switched to it in one atomic call. Production keeps serving the old collection the whole time, and rolling back is one more alias switch.

```bash
make qdrant-aliases                                        # collections, point counts, which one the app serves
make ingest COLLECTION=care-beacon-medical-v2              # build the new collection (asks to confirm)
make ingest COLLECTION=care-beacon-medical-v2 ARGS="--quantize"   # same, with int8 quantization (~4x less RAM)
```

`api/scripts/ingest.py` refuses to write to the served alias, to the collection behind it, or to any other non-empty collection unless you pass `--reset` (rebuild from scratch) or `--resume` (continue an interrupted run). Point ids are a hash of the chunk id, so re-writing points is idempotent: if a batch fails, the script prints the `--resume --start-batch N` to continue with. `--sources` and `--limit N` allow a small trial run first.

Run `python scripts/check_chunks.py` (from `api/`) before a full run. It parses and chunks the whole corpus without embedding anything and reports lead-in-only chunks and leftover URLs.

### Switching production to the new collection

1. Check the new collection on a preview deployment (Deployment Protection applies; see `evaluation/README.md`), including the eval gate.
2. `cd api && python scripts/qdrant_alias.py point care-beacon-live care-beacon-medical-v2`. Production and previews switch immediately, because they share the alias.
3. Clear the answer cache, since cached answers were built from the old chunks: `POST /api/v1/cache/clear` with the `X-API-Key` header.
4. To roll back, point the alias at the previous collection (`point` prints the command) and clear the cache again.

### When the cluster has no room for a second collection (build locally, swap)

The free-tier cluster cannot hold two full collections: a `--quantize` build next to the live one ran out of disk ("WAL buffer size exceeds available disk space") on 2026-11-15. In that case, build the new collection in a local Qdrant and copy it up. Search is down only while the copy runs.

1. `make qdrant-local` starts Qdrant 1.16.3 in Docker on `127.0.0.1:6333` (data in `data/qdrant-local/`, gitignored).
2. Keep a rollback copy: `cd api && python scripts/qdrant_copy.py --from cloud --to local care-beacon-medical care-beacon-medical-backup --quantize`.
3. Build the new collection locally: `python scripts/ingest.py --target local --collection care-beacon-medical-v2`. A local Qdrant serves nothing, so it needs no served alias; the other checks still apply.
4. Check the local build (point counts per source, a few known questions).
5. Delete the cloud collection to free its disk. **Search and chat retrieval fail from here until step 7.**
6. `python scripts/qdrant_copy.py --from local --to cloud care-beacon-medical-v2 --quantize --float16 --workers 6`. Ids, vectors and payloads are copied as-is, so nothing is re-embedded. Measured 2026-11-16: about 640 points/s, 10 minutes for 412,473 points (one worker manages only about 100/s). Failed upserts are retried; if the copy still fails, rerun it with `--resume`.
   - `--float16` is required on the free tier. With float32 originals the cluster ran out of disk while indexing ("Not enough space available for optimization"), leaving 72K vectors unindexed and searches at about 4 s. float16 halves the originals on disk; top-20 results match float32 to within 0.002 in score.
   - The copy creates the collection with indexing off and segments capped at 150 MB, then switches indexing on at the end. The HNSW index then builds in the background. **Until it finishes, searches are brute force and slow** (about 11 s right after the upload).
7. `python scripts/qdrant_alias.py point care-beacon-live care-beacon-medical-v2`, then clear the answer cache.

To roll back, delete the new cloud collection, copy `care-beacon-medical-backup` up the same way, and point the alias at it.

There is no Admin UI or API endpoint to trigger ingestion remotely — that capability was deleted because it required spawning a subprocess, which isn't possible on Vercel's serverless functions.

## Monitoring Progress

Every 50 batches the script prints the batch number, chunks stored, elapsed time and an ETA:

```
  batch 50/1,234  chunks 1,840  elapsed 3.2 min  eta 75.8 min
```

### Signs You Need to Reduce Batch Sizes

If you see any of these while running `make ingest` locally:
- Memory usage climbing higher than you're comfortable with (watch the `python` process in Activity Monitor while `api/scripts/ingest.py` runs)
- Out of Memory (OOM) errors
- Process killed unexpectedly
- Ingestion hanging or becoming very slow

**Solution:** Reduce both batch sizes by 50%

## Testing Configuration

Verify your configuration is working (from `api/`):

```bash
# Default config values
cd api && python -c "from src.config_loader import get_config; c = get_config(); print(f'Article: {c.get(\"ingestion.article_batch_size\")}, Chunk: {c.get(\"ingestion.chunk_batch_size\")}')"

# With environment variables
cd api && INGESTION_ARTICLE_BATCH_SIZE=5 INGESTION_CHUNK_BATCH_SIZE=25 python -c "from src.config_loader import get_config; c = get_config(); print(f'Article: {c.get(\"ingestion.article_batch_size\")}, Chunk: {c.get(\"ingestion.chunk_batch_size\")}')"
```

## Impact on Performance

### Smaller Batch Sizes
- Lower memory usage, less likely to run out of memory
- Slower ingestion (more batches), more API calls to the embedding service

### Larger Batch Sizes
- Faster ingestion (fewer batches), fewer API calls to the embedding service
- Higher memory usage, more risk of OOM on a constrained machine

## Related Files

- `api/config/config.yaml` - Default configuration
- `api/src/config_loader.py` - Configuration loading logic, including the `INGESTION_ARTICLE_BATCH_SIZE`/`INGESTION_CHUNK_BATCH_SIZE` env var overrides
- `api/scripts/ingest.py` - The only ingestion entrypoint, run via `make ingest`
- `.env.example` - Environment variable template (repo root)

## Troubleshooting

### Q: Ingestion runs out of memory

**A:** Reduce batch sizes:
```bash
INGESTION_ARTICLE_BATCH_SIZE=5
INGESTION_CHUNK_BATCH_SIZE=25
```

### Q: Ingestion is too slow

**A:** If you have sufficient memory, increase batch sizes:
```bash
INGESTION_ARTICLE_BATCH_SIZE=20
INGESTION_CHUNK_BATCH_SIZE=100
```

### Q: Environment variables not working

**A:** Make sure to:
1. Set them before running `make ingest` (or export them in your shell / `.env`)
2. Check variable names are exactly: `INGESTION_ARTICLE_BATCH_SIZE` and `INGESTION_CHUNK_BATCH_SIZE`
3. Verify values are integers

### Q: Which script uses these settings?

**A:** `api/scripts/ingest.py` — the only ingestion script in this codebase. There is no separate "low-memory" variant; you control memory usage via these two settings on the one script.
