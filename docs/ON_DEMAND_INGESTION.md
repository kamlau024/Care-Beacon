# On-Demand Ingestion

This guide explains how to trigger article ingestion on Render.com without redeploying your application.

## Overview

The Care-Beacon API now includes an admin endpoint (`/api/v1/admin/ingest`) that allows you to trigger article ingestion on-demand. This is useful when:

- You've added new articles to the repository
- You've migrated articles from one location to another
- You need to rebuild the vector database
- The database wasn't properly ingested during deployment

## Benefits

✅ **No redeployment needed** - Trigger ingestion via API call
✅ **Faster than build-time ingestion** - No need to rebuild Docker images
✅ **On-demand control** - Run ingestion only when needed
✅ **Separates concerns** - Code deployment and data ingestion are independent
✅ **Progress tracking** - See real-time logs in Render dashboard

## Methods

### Method 1: Using the Helper Script (Recommended)

The easiest way to trigger ingestion:

```bash
./scripts/trigger_render_ingestion.sh https://your-api.onrender.com
```

The script will:
1. Prompt for confirmation
2. Trigger the ingestion endpoint
3. Wait for completion (5-10 minutes)
4. Display results and statistics

**Example output:**
```
╔════════════════════════════════════════════════════════════╗
║         Trigger Render Ingestion                           ║
╚════════════════════════════════════════════════════════════╝

API URL: https://care-beacon-api.onrender.com
Endpoint: https://care-beacon-api.onrender.com/api/v1/admin/ingest

⚠️  This will re-ingest all articles and may take 5-10 minutes
⚠️  Cost: ~$0.02 for embeddings

Continue? (yes/no): yes

Triggering ingestion...

HTTP Status: 200

✅ Ingestion completed successfully!

{
  "message": "Ingestion completed successfully",
  "status": "success",
  "elapsed_seconds": 185.3,
  "stats": {
    "articles_processed": "1629",
    "chunks_created": "20062",
    "cost": "$0.016976"
  },
  "timestamp": "2025-11-12T19:45:30.123456"
}
```

### Method 2: Using cURL Directly

```bash
# Basic ingestion (clears existing database automatically)
curl -X POST "https://your-api.onrender.com/api/v1/admin/ingest" \
  -H "Content-Type: application/json" \
  --max-time 1000

# With force parameter (explicit clear)
curl -X POST "https://your-api.onrender.com/api/v1/admin/ingest?force=true" \
  -H "Content-Type: application/json" \
  --max-time 1000
```

**Note:** Use `--max-time 1000` to allow the request to complete (ingestion takes 5-10 minutes).

### Method 3: Using the Swagger UI

1. Navigate to your API docs: `https://your-api.onrender.com/docs`
2. Scroll to the "Administration" section
3. Click on `POST /api/v1/admin/ingest`
4. Click "Try it out"
5. Set `force` parameter (optional)
6. Click "Execute"
7. Wait for response (5-10 minutes)

### Method 4: Using Python

```python
import requests
import time

api_url = "https://your-api.onrender.com"
endpoint = f"{api_url}/api/v1/admin/ingest"

print("Triggering ingestion...")
start_time = time.time()

response = requests.post(endpoint, timeout=1000)

elapsed = time.time() - start_time

if response.status_code == 200:
    result = response.json()
    print(f"✅ Success! Completed in {elapsed:.1f}s")
    print(f"Articles: {result['stats'].get('articles_processed')}")
    print(f"Chunks: {result['stats'].get('chunks_created')}")
    print(f"Cost: {result['stats'].get('cost')}")
else:
    print(f"❌ Failed: {response.text}")
```

## When to Use

### After Adding New Articles

If you've added new markdown articles to `scraped_data/`:

1. Commit and push the new articles
2. Wait for Render deployment to complete
3. Trigger ingestion via the API endpoint

### After Migration

If you've migrated articles (e.g., from old to new structure):

1. Run migration script locally: `python scripts/migrate_old_articles.py --yes`
2. Commit and push migrated files
3. Wait for Render deployment
4. Trigger ingestion to rebuild the database

### Database Corruption or Issues

If queries are returning unexpected results:

1. Check Render logs for errors
2. Trigger re-ingestion to rebuild the database
3. Verify results with a test query

## Monitoring Progress

### Watch Render Logs

While ingestion is running:

1. Go to Render Dashboard → `care-beacon-api` service
2. Click on "Logs" tab
3. Watch for progress messages:
   ```
   Batch 1/33 (50 articles)
   [1/4] Parsing 50 articles...
   ✅ Parsed 50 articles
   [2/4] Chunking articles...
   ✅ Created 1931 chunks
   ...
   ```

### Check API Response

The endpoint returns:
- `status`: "success" or "error"
- `elapsed_seconds`: Time taken
- `stats`: Articles processed, chunks created, cost
- `stdout`: Last 2000 characters of output logs

## Cost

| Component | Cost per Ingestion |
|-----------|-------------------|
| Embeddings (1,629 articles) | ~$0.017 |
| Render compute time | Included in plan |
| **Total** | **~$0.02** |

## Limitations

### Request Timeout

- Maximum request time: **15 minutes**
- Typical ingestion time: **5-10 minutes**
- If timeout occurs, check Render logs to see if ingestion completed

### Concurrent Requests

- Only one ingestion can run at a time
- If ingestion is already running, subsequent requests will wait
- Check Render logs for "already in progress" messages

### Memory Constraints

The ingestion script is optimized for Render's free tier (512MB RAM):
- Processes articles in batches of 50
- Generates embeddings in batches of 100
- Should not exceed memory limits

## Troubleshooting

### Error: "Ingestion script not found"

**Cause:** The ingestion script isn't in the expected location.

**Solution:**
```bash
# Check if script exists
ls -la scripts/ingest_all_articles_low_memory.py

# If missing, ensure it's committed and deployed
git add scripts/ingest_all_articles_low_memory.py
git commit -m "Add ingestion script"
git push
```

### Error: "Ingestion timed out after 15 minutes"

**Cause:** Ingestion took longer than the 15-minute timeout.

**Solution:**
1. Check Render logs - ingestion may have completed successfully
2. Verify database has chunks: `GET /api/v1/stats`
3. If incomplete, trigger again - it will continue from where it left off

### Error: "No articles found"

**Cause:** Article files aren't in the expected locations.

**Solution:**
```bash
# Check article directories exist
ls -la scraped_data/bc-cancer/articles/
ls -la scraped_data/canadian-cancer-society/articles/

# Ensure they're committed and deployed
git status scraped_data/
```

### Ingestion succeeds but queries return wrong results

**Cause:** Stale cache or database still has old data.

**Solution:**
1. Clear cache: `POST /api/v1/cache/clear`
2. Trigger ingestion again with force: `?force=true`
3. Verify with validation: `./scripts/validate_ingestion.sh stats`

## Security Considerations

⚠️ **Important:** This endpoint should be protected in production!

Currently, the endpoint is **open to anyone**. For production use:

### Option 1: Add API Key Authentication

```python
@app.post("/api/v1/admin/ingest")
async def trigger_ingestion(
    force: bool = False,
    api_key: str = Header(None, alias="X-API-Key")
):
    """Trigger ingestion with API key protection."""
    if api_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    # ... rest of implementation
```

### Option 2: Use Render's IP Whitelist

1. Go to Render Dashboard → Settings
2. Add your IP to the allowed list
3. Only requests from your IP can access the endpoint

### Option 3: Disable After Use

Remove or comment out the endpoint after initial ingestion:
```python
# @app.post("/api/v1/admin/ingest", tags=["Administration"])
# async def trigger_ingestion(force: bool = False):
#     """Temporarily disabled for security"""
#     raise HTTPException(status_code=404)
```

## Best Practices

1. **Always check Render logs** during ingestion to ensure it completes successfully
2. **Verify results** after ingestion with a test query or validation script
3. **Monitor costs** in your OpenAI dashboard (embeddings should be ~$0.02)
4. **Clear cache** after re-ingestion to ensure fresh results
5. **Document changes** when adding new articles or migrating data

## Alternative: Manual Render Jobs

Render also supports running one-off jobs. To run ingestion as a job:

1. Go to Render Dashboard → Create New Job
2. Use existing `care-beacon-api` repository
3. Set command: `python scripts/ingest_all_articles_low_memory.py`
4. Click "Run Job"

**Pros:** Doesn't block web service, can run longer
**Cons:** More setup, separate from API, harder to trigger programmatically
