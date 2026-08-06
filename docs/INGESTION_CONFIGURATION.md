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

```bash
make ingest   # runs `cd api && python scripts/ingest.py`, picking up the config/env vars above
```

There is no Admin UI or API endpoint to trigger ingestion remotely — that capability was deleted because it required spawning a subprocess, which isn't possible on Vercel's serverless functions.

## Monitoring Memory Usage

The ingestion scripts display memory usage throughout the process:

```
[1/4] Parsing 10 articles...
  ✅ Parsed 10 articles
  💾 Memory: 245.3 MB

[2/4] Chunking articles...
  ✅ Created 324 chunks
  💾 Memory: 267.8 MB

[3/4] Generating embeddings...
  ✅ Generated 324 embeddings
  💾 Memory: 312.4 MB

[4/4] Storing in database...
  ✅ Stored 324 chunks
  💾 Memory: 285.2 MB
```

### Signs You Need to Reduce Batch Sizes

If you see any of these while running `make ingest` locally:
- Memory usage climbing higher than you're comfortable with (`api/scripts/ingest.py` prints memory usage via `psutil` as it runs)
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
