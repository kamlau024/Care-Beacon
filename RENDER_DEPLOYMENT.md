# 🚀 Deploying Care-Beacon to Render.com

This guide walks you through deploying the complete Care-Beacon stack to Render.com.

## 📋 Prerequisites

1. A Render.com account (free tier works!)
2. Your GitHub repository: `https://github.com/kamlau024/Care-Beacon.git`
3. An OpenAI API key

## 🏗️ Architecture Overview

Your deployment will consist of 3 services:

1. **Redis** - Managed Redis for caching (free tier)
2. **FastAPI API** - Backend service with persistent disk for vector DB (free tier)
3. **Next.js Web** - Frontend application (free tier)

## 🎯 Deployment Steps

### Option A: One-Click Blueprint Deployment (Recommended)

#### 1. Push Configuration Files to GitHub

Make sure you've committed and pushed the new files:

```bash
git add render.yaml runtime.txt scripts/render_build.sh
git commit -m "Add Render.com deployment configuration"
git push origin main
```

#### 2. Deploy via Render Blueprint

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New"** → **"Blueprint"**
3. Connect your GitHub repository: `https://github.com/kamlau024/Care-Beacon`
4. Render will automatically detect `render.yaml`
5. Review the services that will be created:
   - `care-beacon-redis` (Redis)
   - `care-beacon-api` (Web Service - Python)
   - `care-beacon-web` (Web Service - Node.js)
6. Click **"Apply"**

#### 3. Configure Environment Variables

After the blueprint is applied, you need to set your OpenAI API key:

1. Go to **care-beacon-api** service
2. Navigate to **Environment** tab
3. Find `OPENAI_API_KEY` and click **"Edit"**
4. Paste your OpenAI API key
5. Click **"Save Changes"**
6. The service will automatically redeploy

---

### Option B: Manual Step-by-Step Deployment

If you prefer manual control, follow these steps:

#### Step 1: Create Redis Instance

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New"** → **"Redis"**
3. Configure:
   - **Name**: `care-beacon-redis`
   - **Plan**: Free
4. Click **"Create Redis"**
5. Wait for it to become available

#### Step 2: Deploy FastAPI Backend

1. Click **"New"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `care-beacon-api`
   - **Runtime**: Python 3
   - **Build Command**: `chmod +x scripts/render_build.sh && ./scripts/render_build.sh`
   - **Start Command**: `python scripts/start_api.py`
   - **Plan**: Free

4. **Add Environment Variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `REDIS_URL`: Select **"Add from service"** → Choose `care-beacon-redis`
   - `ANONYMIZED_TELEMETRY`: `False`

5. **Add Persistent Disk**:
   - Click **"Add Disk"**
   - **Name**: `vector-db-data`
   - **Mount Path**: `/opt/render/project/src/data`
   - **Size**: 1 GB (free tier)

6. Click **"Create Web Service"**

**Note**: First deployment will take 10-15 minutes as it ingests vector database data.

#### Step 3: Deploy Next.js Frontend

1. Click **"New"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `care-beacon-web`
   - **Runtime**: Node
   - **Root Directory**: `web-client`
   - **Build Command**: `npm install && npm run build`
   - **Start Command**: `npm start`
   - **Plan**: Free

4. **Add Environment Variables**:
   - `NEXT_PUBLIC_API_URL`: The URL of your `care-beacon-api` service
     - Example: `https://care-beacon-api.onrender.com`
   - Get this URL from the care-beacon-api service page (top right corner)

5. Click **"Create Web Service"**

---

## ✅ Verify Deployment

### 1. Check API Health

Visit your API's health endpoint:
```
https://care-beacon-api.onrender.com/health
```

You should see:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "services": {
    "vector_db": true,
    "redis_cache": true,
    "llm_client": true
  }
}
```

### 2. Check API Documentation

Visit the interactive API docs:
```
https://care-beacon-api.onrender.com/docs
```

### 3. Check Web Application

Visit your web application:
```
https://care-beacon-web.onrender.com
```

Test:
- ✅ System Health card shows all services healthy
- ✅ Search functionality works
- ✅ Statistics tab displays data
- ✅ Admin functions work (clear cache, reset stats)

---

## 🔧 Configuration Details

### Redis Connection

The API automatically connects to Redis using the `REDIS_URL` environment variable provided by Render.

### Vector Database

- Stored on persistent disk at `/opt/render/project/src/data`
- Automatically initialized on first deployment
- Persists across deployments and restarts

### CORS Configuration

The API is configured to allow all origins (`*`) for development. Update `config/config.yaml` if you need to restrict this in production.

---

## 📊 Monitoring & Logs

### View Logs

1. Go to your service in Render Dashboard
2. Click **"Logs"** tab
3. View real-time logs

### Check Metrics

1. Go to your service in Render Dashboard
2. Click **"Metrics"** tab
3. View CPU, memory, and request metrics

---

## 🆓 Free Tier Limits

Render's free tier includes:

- **Web Services**: 750 hours/month (spins down after 15 min of inactivity)
- **Redis**: 25 MB storage, 20 connections
- **Persistent Disks**: 1 GB

**Important Notes**:
- Free tier services spin down after 15 minutes of inactivity
- First request after spin-down will take 30-60 seconds (cold start)
- Consider upgrading to paid tier for production use

---

## 🔄 Updating Your Deployment

### Update Code

1. Push changes to GitHub:
   ```bash
   git add .
   git commit -m "Your update message"
   git push origin main
   ```

2. Render will automatically deploy (if auto-deploy is enabled)
3. Or manually deploy from Render Dashboard:
   - Go to your service
   - Click **"Manual Deploy"** → **"Deploy latest commit"**

### Update Environment Variables

1. Go to your service in Render Dashboard
2. Click **"Environment"** tab
3. Update variables
4. Service will automatically redeploy

---

## 🔄 Reingesting Vector Database (After Adding New Data)

When you add new scraped articles or want to rebuild the vector database with updated data:

### Verify Current Database Contents

First, check what sources are currently in your production database:

```bash
# Check source distribution
curl -X POST https://care-beacon-api.onrender.com/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the symptoms of breast cancer?", "min_similarity": 0.5}' \
  | python3 -c "import sys, json; data = json.load(sys.stdin); from collections import Counter; print('Sources:', Counter([s['source'] for s in data.get('sources', [])]))"
```

**Expected output** (with multi-source data):
```
Sources: Counter({'Canadian Cancer Society': 15, 'BC Cancer': 10})
```

If you only see one source (e.g., all "BC Cancer"), you need to reingest.

### Method 1: Manual Reingestion via Shell (Recommended)

1. Go to **Render Dashboard** → `care-beacon-api` service
2. Click **"Shell"** tab (in the service menu)
3. Wait for shell to connect
4. Run the reingestion script:
   ```bash
   bash scripts/reingest_production.sh
   ```
5. Type `yes` when prompted
6. Wait for completion (5-10 minutes)
7. The script will:
   - Delete the existing vector database
   - Check for articles in both sources
   - Run the ingestion pipeline
   - Report completion

**Expected output:**
```
🔄 Starting manual reingestion...
⚠️  This will delete the existing vector database and rebuild it
Are you sure you want to continue? (yes/no): yes
🗑️  Removing existing database...
📄 Checking for source articles...
  ✅ BC Cancer: 11 articles
  ✅ Canadian Cancer Society: 1535 articles

🚀 Running ingestion script...
⏱️  This will take several minutes...
[Ingestion progress logs...]
✅ Reingestion complete!
```

### Method 2: Force Reingest via Environment Variable

1. Go to **Render Dashboard** → `care-beacon-api` service
2. Click **"Environment"** tab
3. Add new environment variable:
   - **Key**: `FORCE_REINGEST`
   - **Value**: `true`
4. Click **"Save Changes"**
5. Render will automatically trigger a new deployment
6. Build script will detect `FORCE_REINGEST=true` and rebuild the database
7. **After deployment completes**, remove the variable or set to `false`:
   - Otherwise, every deployment will reingest (slow and costly!)

### Method 3: Delete Disk and Redeploy

If shell access isn't working:

1. Go to **Render Dashboard** → `care-beacon-api` service
2. Click **"Disks"** tab
3. Delete the `vector-db-data` disk
4. Recreate the disk:
   - **Name**: `vector-db-data`
   - **Mount Path**: `/opt/render/project/src/data`
   - **Size**: 1 GB
5. Trigger a manual deploy
6. The build script will detect missing database and run ingestion

### Verify Reingestion Success

After reingestion, verify both sources are available:

```bash
# Check with a test query
curl -X POST https://care-beacon-api.onrender.com/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the symptoms of breast cancer?", "source": "Canadian Cancer Society"}' \
  | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Sources returned: {len(data[\"sources\"])}'); print('All from CCS:', all(s['source'] == 'Canadian Cancer Society' for s in data['sources']))"
```

**Expected output:**
```
Sources returned: 5
All from CCS: True
```

### Important Notes

- **Reingestion takes 5-10 minutes** for ~1,500 articles
- **Cost**: ~$0.02 in OpenAI embedding costs (one-time)
- **Downtime**: API remains running during reingestion if using Method 1 (Shell)
- **scraped_data/** must be in your repository for auto-ingestion to work
- The build script now supports multi-source structure:
  - `scraped_data/bc-cancer/articles/`
  - `scraped_data/canadian-cancer-society/articles/`

---

## 🐛 Troubleshooting

### API Service Won't Start

**Check logs for:**
- Missing environment variables (especially `OPENAI_API_KEY`)
- Redis connection issues
- Vector database initialization errors

**Solution:**
1. Verify all environment variables are set
2. Check Redis service is running
3. Check build logs for ingestion script errors

### Web Client Can't Connect to API

**Check:**
- `NEXT_PUBLIC_API_URL` is set correctly
- API service is running and healthy
- CORS is properly configured

**Solution:**
1. Update `NEXT_PUBLIC_API_URL` to match your API URL
2. Redeploy web client
3. Clear browser cache and hard refresh

### Vector Database Is Empty or Missing Sources

**Check:**
- Only seeing one source (e.g., all "BC Cancer" but no "Canadian Cancer Society")
- Getting "No context found" for all queries
- New articles not showing up in search results

**Solution:**
See the **"Reingesting Vector Database"** section above for detailed instructions on rebuilding the database with all sources. Use Method 1 (Shell) for the quickest solution.

### Redis Connection Errors

**Check:**
- Redis service is running
- `REDIS_URL` environment variable is correctly linked

**Solution:**
1. Verify Redis service status
2. Re-link Redis URL in API service environment variables
3. Redeploy API service

---

## 🎉 Success!

Your Care-Beacon stack is now live on Render.com!

**Access your application:**
- Web App: `https://care-beacon-web.onrender.com`
- API: `https://care-beacon-api.onrender.com`
- API Docs: `https://care-beacon-api.onrender.com/docs`

---

## 📝 Next Steps

1. **Custom Domain** (optional): Add a custom domain in Render settings
2. **Upgrade to Paid Tier**: For production use with no spin-down
3. **Add Authentication**: Implement user authentication for the admin panel
4. **Monitoring**: Set up Render's notification alerts for service health
5. **Backups**: Regularly backup your vector database disk

---

## 💡 Cost Optimization Tips

1. Use Render's **suspend feature** when not actively using the app
2. Monitor your **free tier hours** in the Render dashboard
3. Consider **background workers** for heavy ingestion tasks
4. Optimize your **vector database** to stay within disk limits

---

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [Render Free Tier Limits](https://render.com/docs/free)
- [Render Persistent Disks](https://render.com/docs/disks)
- [Render Environment Variables](https://render.com/docs/environment-variables)

---

**Need help?** Check the Render Community Forum or Care-Beacon GitHub Issues.
