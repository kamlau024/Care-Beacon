# Ingestion Batch Size Configuration

This document explains how to configure batch sizes for data ingestion to optimize for different memory environments.

## Overview

The ingestion process supports configurable batch sizes to adapt to different hosting environments:

- **Article Batch Size**: Number of articles to process in one batch
- **Chunk Batch Size**: Number of chunks to add to the vector database in one batch

## Configuration Methods

### Method 1: Config File (config/config.yaml)

Edit the `config/config.yaml` file:

```yaml
# Ingestion Configuration (for bulk data loading)
ingestion:
  article_batch_size: 10  # Number of articles to process per batch
  chunk_batch_size: 50    # Number of chunks to add to vector DB per batch
```

**Default values:**
- Article batch size: `10` (optimized for low-memory environments)
- Chunk batch size: `50` (optimized for low-memory environments)

### Method 2: Environment Variables (Recommended for Production)

Set environment variables to override config file values:

```bash
export INGESTION_ARTICLE_BATCH_SIZE=10
export INGESTION_CHUNK_BATCH_SIZE=50
```

Or add to your `.env` file:

```bash
# Optional: Ingestion Batch Sizes (for low-memory environments)
INGESTION_ARTICLE_BATCH_SIZE=10
INGESTION_CHUNK_BATCH_SIZE=50
```

## Recommended Settings by Environment

### Render.com Free Tier (512MB RAM)

**Ultra-low memory settings:**
```bash
INGESTION_ARTICLE_BATCH_SIZE=5
INGESTION_CHUNK_BATCH_SIZE=25
```

**Standard low-memory settings:**
```bash
INGESTION_ARTICLE_BATCH_SIZE=10
INGESTION_CHUNK_BATCH_SIZE=50
```

### Render.com Paid Tiers (2GB+ RAM)

```bash
INGESTION_ARTICLE_BATCH_SIZE=50
INGESTION_CHUNK_BATCH_SIZE=100
```

### Local Development (8GB+ RAM)

```bash
INGESTION_ARTICLE_BATCH_SIZE=100
INGESTION_CHUNK_BATCH_SIZE=200
```

### High-Memory Production (16GB+ RAM)

No limits needed - you can omit these environment variables or set high values:
```bash
INGESTION_ARTICLE_BATCH_SIZE=500
INGESTION_CHUNK_BATCH_SIZE=500
```

## Usage with Render.com

### Step 1: Set Environment Variables in Render Dashboard

1. Go to your service in Render dashboard
2. Navigate to "Environment" tab
3. Add environment variables:
   - Key: `INGESTION_ARTICLE_BATCH_SIZE`, Value: `5`
   - Key: `INGESTION_CHUNK_BATCH_SIZE`, Value: `25`
4. Save changes

### Step 2: Trigger Ingestion

Use the Admin UI to trigger ingestion with the new batch sizes:
- Navigate to `/admin` in your deployed app
- Click "Ingest Data"
- The ingestion will use the configured batch sizes

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

If you see any of these during ingestion:
- Memory usage exceeding 450MB on Render free tier
- Out of Memory (OOM) errors
- Process killed unexpectedly
- Ingestion hanging or becoming very slow

**Solution:** Reduce both batch sizes by 50%

## Testing Configuration

Verify your configuration is working:

```bash
# Default config values
python -c "from src.config_loader import get_config; c = get_config(); print(f'Article: {c.get(\"ingestion.article_batch_size\")}, Chunk: {c.get(\"ingestion.chunk_batch_size\")}')"

# With environment variables
INGESTION_ARTICLE_BATCH_SIZE=5 INGESTION_CHUNK_BATCH_SIZE=25 python -c "from src.config_loader import get_config; c = get_config(); print(f'Article: {c.get(\"ingestion.article_batch_size\")}, Chunk: {c.get(\"ingestion.chunk_batch_size\")}')"
```

## Impact on Performance

### Smaller Batch Sizes
- ✅ Lower memory usage
- ✅ Less likely to run out of memory
- ❌ Slower ingestion (more batches)
- ❌ More API calls to embedding service

### Larger Batch Sizes
- ✅ Faster ingestion (fewer batches)
- ✅ Fewer API calls to embedding service
- ❌ Higher memory usage
- ❌ Risk of OOM on small instances

## Related Files

- `/config/config.yaml` - Default configuration
- `/src/config_loader.py` - Configuration loading logic
- `/scripts/ingest_all_articles_low_memory.py` - Low-memory ingestion script
- `/scripts/ingest_all_articles.py` - Standard ingestion script
- `/.env.example` - Environment variable template

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
1. Restart the application after setting environment variables
2. Check variable names are exactly: `INGESTION_ARTICLE_BATCH_SIZE` and `INGESTION_CHUNK_BATCH_SIZE`
3. Verify values are integers (numbers only, no quotes in Render dashboard)

### Q: Which script uses these settings?

**A:** Both ingestion scripts use these settings:
- `/scripts/ingest_all_articles.py` - Standard script
- `/scripts/ingest_all_articles_low_memory.py` - Memory-optimized script (used by Admin UI)
