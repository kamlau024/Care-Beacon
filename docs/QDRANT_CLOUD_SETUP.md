# Migrating to Qdrant Cloud for Production

This guide explains how to migrate from ChromaDB (local) to Qdrant Cloud (cloud-hosted) for production deployments on memory-constrained environments like Render.com free tier.

## Why Qdrant Cloud?

**Problem with ChromaDB on Render Free Tier (512MB RAM):**
- ChromaDB stores the HNSW index and data locally
- During queries, it loads portions of the index into memory
- With a 1.3GB database, memory usage can exceed 400-500MB
- This causes out-of-memory errors on Render's 512MB free tier

**Qdrant Cloud Solution:**
- Vector database runs as a separate cloud service
- Your API service only makes HTTP requests (minimal memory footprint)
- Free tier: 1GB storage, unlimited API calls
- Better scalability and performance
- Can keep LLM re-ranking enabled (improves accuracy)

## Architecture

### Before (ChromaDB Local):
```
[Render API - 512MB RAM]
  ├─ FastAPI app (~50MB)
  ├─ ChromaDB + HNSW index (~300-400MB) ❌ Causes OOM
  ├─ Query processing (~100MB)
  └─ Re-ranking (~50MB)
  Total: ~500-600MB = Exceeds limit!
```

### After (Qdrant Cloud):
```
[Render API - 512MB RAM]          [Qdrant Cloud - 1GB Free]
  ├─ FastAPI app (~50MB)     ──►  Vector Database
  ├─ Query processing (~100MB)    (Separate service)
  └─ Re-ranking (~50MB)
  Total: ~200MB ✅              No RAM impact on API!
```

---

## Step 1: Sign Up for Qdrant Cloud

1. Go to [Qdrant Cloud](https://cloud.qdrant.io)
2. Click "Get Started" or "Sign Up"
3. Create an account (free, no credit card required)
4. Verify your email

## Step 2: Create a Cluster

1. Log into Qdrant Cloud dashboard
2. Click "+ Create Cluster"
3. Configure your cluster:
   - **Name**: `care-beacon-production`
   - **Tier**: **Free** (1GB storage)
   - **Region**: Choose closest to your Render.com region (usually `us-east`)
4. Click "Create"
5. Wait 1-2 minutes for cluster to provision

## Step 3: Get Your Credentials

After cluster is created:

1. Click on your cluster name
2. Find **Cluster URL**:
   - Example: `https://abc123-example.qdrant.io`
   - Copy this URL
3. Click "API Keys" tab
4. Click "+ Create API Key"
5. Give it a name (e.g., "care-beacon-production")
6. Copy the API key (you won't see it again!)

## Step 4: Install Qdrant Client

The Qdrant client should already be in `requirements.txt`. If not:

```bash
pip install qdrant-client==1.7.0
```

## Step 5: Configure Environment Variables

### For Local Testing:

Edit `.env` file:

```bash
# Vector Database Configuration
VECTOR_DB_PROVIDER=qdrant

# Qdrant Cloud Configuration
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-api-key-here
```

### For Render.com Production:

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your `care-beacon-api` service
3. Go to "Environment" tab
4. Add these environment variables:

| Key | Value |
|-----|-------|
| `VECTOR_DB_PROVIDER` | `qdrant` |
| `QDRANT_URL` | `https://your-cluster.qdrant.io` |
| `QDRANT_API_KEY` | `your-api-key-here` |

5. Click "Save Changes"

## Step 6: Migrate Your Data

Run the migration script to transfer data from ChromaDB to Qdrant:

```bash
# Make sure your local ChromaDB database is at data/vector_db/
# And Qdrant credentials are in .env

python scripts/migrate_chromadb_to_qdrant.py
```

**Expected Output:**
```
======================================================================
ChromaDB to Qdrant Migration
======================================================================

📦 Connecting to ChromaDB...
📊 Fetching data from ChromaDB...
   Found 50,245 chunks to migrate

🚀 Connecting to Qdrant Cloud...
   URL: https://your-cluster.qdrant.io
   ✓ Connected

📝 Creating Qdrant collection...
   Vector size: 1536
   ✓ Created collection: care-beacon-medical

⬆️  Uploading data to Qdrant...
   ✓ Uploaded 50,245/50,245 chunks

✅ Verifying migration...
   Qdrant collection size: 50,245 points
   ✓ Migration successful!

======================================================================
Migration Complete!
======================================================================
```

## Step 7: Test Qdrant Locally

Before deploying to production, test that Qdrant works:

```bash
# Start your API locally with Qdrant configuration
python scripts/start_api.py
```

Then test a query:

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the symptoms of breast cancer?"}'
```

You should see results with citations!

## Step 8: Deploy to Render

Once you've confirmed Qdrant works locally:

1. **Commit changes**:
   ```bash
   git add .
   git commit -m "Migrate to Qdrant Cloud for production deployment"
   git push origin main
   ```

2. **Render auto-deploys**:
   - Render detects the push and starts deployment
   - Wait 2-3 minutes for build to complete
   - Check logs for any errors

3. **Verify production**:
   - Go to your Render app URL
   - Try a query on the Search page
   - Check that results are returned successfully

---

## Troubleshooting

### Error: "QDRANT_URL not configured"

**Solution:**
- Make sure you added `QDRANT_URL` and `QDRANT_API_KEY` to Render environment variables
- Make sure `VECTOR_DB_PROVIDER=qdrant` is set
- Redeploy if you just added the variables

### Error: "Failed to connect to Qdrant"

**Solution:**
- Verify your Qdrant cluster is running (check Qdrant Cloud dashboard)
- Check that the URL is correct and ends with `.qdrant.io`
- Verify API key is correct (regenerate if needed)
- Ensure no firewall/network issues

### Error: "Collection not found"

**Solution:**
- Run the migration script again: `python scripts/migrate_chromadb_to_qdrant.py`
- Check Qdrant Cloud dashboard to see if collection exists
- Collection name should be `care-beacon-medical`

### Slow Query Performance

**Causes:**
- Network latency between Render and Qdrant
- Free tier has rate limits

**Solutions:**
- Choose Qdrant region closest to your Render region
- Enable caching (already enabled in config)
- Consider upgrading to Qdrant paid tier if needed

### Migration Failed

**If migration stops midway:**
1. Check error message
2. Fix the issue (usually authentication or network)
3. The migration script will overwrite the collection, so just run it again

---

## Switching Back to ChromaDB (Local Development)

To switch back to ChromaDB for local development:

1. Edit `.env`:
   ```bash
   VECTOR_DB_PROVIDER=chromadb
   ```

2. Or in `config/config.yaml`:
   ```yaml
   vector_db:
     provider: "chromadb"
   ```

3. Restart your API

---

## Cost Summary

### Free Tier (What You're Using):
| Service | Free Tier | Usage | Cost |
|---------|-----------|-------|------|
| Qdrant Cloud | 1GB storage | ~1.3GB compressed | $0 |
| Qdrant API Calls | Unlimited | ~86K queries/day | $0 |
| Render Free Tier | 512MB RAM | API only (no DB) | $0 |
| **Total** | | | **$0/month** ✅ |

### If You Outgrow Free Tier:
| Upgrade | Cost | Benefit |
|---------|------|---------|
| Qdrant Standard | $25/mo | 4GB storage, better performance |
| Render Starter | $7/mo | 2GB RAM (if you ever need it) |

---

## Benefits Summary

✅ **No more out-of-memory errors** on Render free tier
✅ **Keep LLM re-ranking enabled** (better accuracy)
✅ **Better scalability** (database scales independently)
✅ **Production-ready architecture**
✅ **Free tier sufficient** for ~1.3GB database
✅ **Faster deployment** (no database download needed)
✅ **Better performance** than local ChromaDB on 512MB

---

## Next Steps

After successful migration:

1. ✅ Monitor query performance in production
2. ✅ Check Qdrant Cloud dashboard for usage metrics
3. ✅ Set up alerting if needed
4. ✅ Consider upgrading if you exceed free tier limits
5. ✅ Update your documentation to reflect Qdrant setup

**Congratulations!** 🎉 You've successfully migrated to Qdrant Cloud!
