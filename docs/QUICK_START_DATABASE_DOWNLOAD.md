# Quick Start: Database Download for Demo

This guide will help you quickly deploy your Care-Beacon app to Render with a pre-built database, bypassing memory-intensive ingestion.

## ⚡ Quick Overview

Instead of ingesting data on Render's 512MB free tier (which runs out of memory), you'll:
1. Create a manifest of your local database
2. Upload files to cloud storage (free)
3. Configure Render to download from cloud
4. Use the Admin UI button to trigger the download

**Total Time**: ~15-20 minutes
**Cost**: $0 (using free tiers)

---

## Step 1: Prepare Your Local Database

### 1.1 Run Ingestion (Includes Manifest Creation)

```bash
cd /Users/kamlau/Projects/Care-Beacon

# Option 1: Standard ingestion (recommended for local machines with 4GB+ RAM)
python scripts/ingest_all_articles.py

# Option 2: Low-memory ingestion (for constrained environments)
python scripts/ingest_all_articles_low_memory.py
```

This will:
1. Ingest all articles from `scraped_data/`
2. Create embeddings and store in ChromaDB
3. **Automatically create `vector_db_manifest.json`** inside `data/vector_db/`

**Why inside vector_db?** The manifest describes this specific database, so it stays with the database during backups and uploads.

**Expected Output (end of ingestion):**
```
======================================================================
Creating Vector Database Manifest
======================================================================

📊 Database Files:
   Total files: 6
   Total size: 989,372,442 bytes (943.4 MB)

✅ Manifest created: data/vector_db/vector_db_manifest.json
   Size: 412 bytes

📤 Ready for Cloud Upload:
   Upload entire folder: data/vector_db/ → <cloud-url>/vector_db/
   Includes manifest: vector_db_manifest.json
```

---

## Step 2: Upload to Cloud Storage (Choose One)

### Option A: Google Cloud Storage (Recommended - Free 5GB)

**Setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Cloud Storage API
4. Create a bucket:
   - Name: `care-beacon-vectordb` (or your choice)
   - Location: `us` (or nearest region)
   - Storage class: `Standard`
   - Access control: `Uniform`
   - Public access: **Allowed** (make public)

**Upload Files:**

```bash
# Install gsutil (Google Cloud CLI)
# Visit: https://cloud.google.com/storage/docs/gsutil_install

# Upload entire vector_db directory (includes manifest inside)
gsutil -m cp -r data/vector_db gs://care-beacon-vectordb/
```

**Make Public:**
```bash
# Make all files public
gsutil -m acl ch -u AllUsers:R gs://care-beacon-vectordb/vector_db/**
```

**Your Base URL:**
```
https://storage.googleapis.com/care-beacon-vectordb/
```

**Note:** The base URL should point to the bucket root. The manifest will be fetched from `{base_url}/vector_db/vector_db_manifest.json`

### Option B: AWS S3 (Free Tier - 5GB)

**Setup:**
1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com/)
2. Create bucket:
   - Name: `care-beacon-vectordb`
   - Region: `us-east-1` (or preferred)
   - Block Public Access: **OFF**
3. Add bucket policy (make public):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicRead",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::care-beacon-vectordb/*"
  }]
}
```

**Upload Files:**

```bash
# Install AWS CLI
# Visit: https://aws.amazon.com/cli/

# Configure credentials
aws configure

# Upload entire vector_db directory (includes manifest inside)
aws s3 cp data/vector_db s3://care-beacon-vectordb/vector_db --recursive
```

**Your Base URL:**
```
https://care-beacon-vectordb.s3.amazonaws.com/
```

**Note:** The base URL should point to the bucket root. The manifest will be fetched from `{base_url}/vector_db/vector_db_manifest.json`

### Option C: Netlify (Free - Easy)

**Setup:**
1. Go to [Netlify](https://netlify.com)
2. Drag and drop your `data` folder to deploy
3. Get the URL (e.g., `https://care-beacon-db.netlify.app/`)

**Note:** Netlify has a 100MB file size limit, so you may need to split large files.

### Option D: Google Drive (Free - 15GB)

**Setup:**
1. Go to [Google Drive](https://drive.google.com)
2. Create a folder: `Care-Beacon-VectorDB`
3. Upload the entire `vector_db` folder from `data/vector_db/`:
   - Drag and drop the `vector_db` folder into your Drive folder
   - Or click "New" → "Folder upload" and select `data/vector_db`

**Make Files Public:**

For each file in the uploaded `vector_db` folder:
1. Right-click on the `vector_db` folder
2. Select "Share" → "Share"
3. Under "General access", click "Change"
4. Select "Anyone with the link"
5. Set permission to "Viewer"
6. Click "Done"

**Important**: You need to make the entire folder and all its contents public.

**Get Public URLs:**

Google Drive doesn't provide direct HTTP access like cloud storage buckets, so you'll need to use a different approach:

**Option D.1: Using Google Drive API (Recommended)**

This requires setting up a Google Cloud project with Drive API enabled:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable Google Drive API
4. Create service account credentials
5. Share your Drive folder with the service account email
6. Use the service account to download files

**Note:** This approach is more complex and requires code changes to the download functionality.

**Option D.2: Using rclone (Alternative)**

Install rclone to sync files:

```bash
# Install rclone
brew install rclone  # macOS
# or download from https://rclone.org/

# Configure Google Drive
rclone config

# Upload files
rclone copy data/vector_db gdrive:Care-Beacon-VectorDB/vector_db -P

# Make public (requires additional setup)
```

**Option D.3: Using Third-Party Services (Easiest for Testing)**

Use a service like `DriveToWeb` or similar that converts Google Drive links to direct URLs:

1. Upload `vector_db` folder to Google Drive
2. Make folder public (as described above)
3. Use a third-party service to get direct download links
4. Create a manifest with these direct URLs

**Limitations:**
- ⚠️ Google Drive has daily download bandwidth limits
- ⚠️ Files larger than 100MB trigger virus scan warnings
- ⚠️ Not ideal for production use
- ⚠️ Slower download speeds compared to proper cloud storage
- ⚠️ Requires manual URL generation for each file

**Recommendation:** Google Drive is **not recommended** for this use case. Use Google Cloud Storage (Option A) instead, which:
- Provides direct HTTP URLs
- Has proper bandwidth for downloads
- Is designed for this type of file hosting
- Has the same 5GB free tier
- Is much simpler to set up

**If you must use Google Drive:**

The easiest approach is to:
1. Create a shared folder on Google Drive
2. Get the folder ID from the sharing link
3. Use Google Drive API with a service account
4. Modify the download code to use Drive API instead of HTTP downloads

This requires code changes and is beyond the scope of this quick start guide.

---

## Step 3: Configure Render Environment

### 3.1 Add Environment Variable

No environment variable needed! You'll enter the URL directly in the Admin UI.

If you prefer to set a default URL via environment variable:
1. Go to your Render dashboard: https://dashboard.render.com
2. Select your `care-beacon-api` service
3. Go to "Environment" tab
4. Add new environment variable:
   - **Key:** `VECTOR_DB_REMOTE_URL`
   - **Value:** Your base URL from Step 2
     - Example: `https://storage.googleapis.com/care-beacon-vectordb/`
     - **Important:** Must end with `/`
5. Click "Save Changes"

But the **recommended approach** is to just paste the URL in the Admin UI.

### 3.2 Verify Environment Variable

Render will automatically trigger a redeploy. Wait for it to complete (~2-3 minutes).

---

## Step 4: Trigger Database Download

### 4.1 Open Admin UI

1. Go to your deployed app: `https://your-app.onrender.com`
2. Click "Admin" tab in the navigation

### 4.2 Use Download Button

You'll see a new "Database Download" card with:
- **Status badge**: Shows current state (Ready/Downloading/Success/Error)
- **Download button**: Purple button labeled "Download"
- **Progress bar**: Real-time download progress

### 4.3 Start Download

1. Click the **"Download"** button
2. Confirm the dialog:
   ```
   This will download the pre-built vector database from cloud storage.

   The existing database will be backed up automatically.

   Download size: ~1.3GB (31 files)
   Estimated time: 2-5 minutes

   Continue?
   ```
3. Click **OK**

### 4.4 Monitor Progress

You'll see real-time updates:
```
Downloading in progress...        0:32

[Progress Bar] 45%

45%                               15/31 files

Downloading 16/31: f21de15f-fa31-4260-b3e4-37035237023e/data_level0.bin
```

### 4.5 Success!

Once complete:
```
✅ Database downloaded successfully!

Files Downloaded: 31
Time: 3:45

The database is now ready to use. You can start querying immediately.
```

---

## Step 5: Test Your Database

### 5.1 Check Vector DB Stats

Still on the Admin page, look at the "Vector Database" card:
- **Total Documents**: Should show your article count
- **Total Chunks**: Should match your local database
- **Sources**: BC Cancer, Canadian Cancer Society

### 5.2 Try a Query

1. Go to "Search" tab
2. Enter a test question: "What are the symptoms of breast cancer?"
3. Click "Ask"
4. You should get results with citations!

---

## Troubleshooting

### Error: "VECTOR_DB_REMOTE_URL not configured"

**Solution:**
- Make sure you added the environment variable in Render
- Check that the URL ends with `/`
- Redeploy if needed

### Error: "Failed to fetch manifest"

**Solution:**
- Verify your cloud storage URL is accessible
- Test in browser: `https://your-url/vector_db_manifest.json`
- Check that files are public
- Ensure manifest file was uploaded

### Error: "Failed to download {filename}"

**Solution:**
- Check that all files in manifest exist in cloud storage
- Verify folder structure matches:
  ```
  https://your-url/vector_db/chroma.sqlite3
  https://your-url/vector_db/[uuid-folder]/data_level0.bin
  ```
- Check file permissions (must be public)

### Download is very slow

**Causes:**
- Cloud storage region far from Render server
- Render free tier bandwidth limits
- Large file sizes

**Solutions:**
- Use a cloud provider in the same region as your Render service
- Be patient - 1.3GB takes 2-5 minutes even on good connections
- Consider upgrading Render tier for faster network

### "Download failed - restored backup"

**What happened:**
- Download encountered an error
- Your existing database was automatically restored
- Safe to try again

**Actions:**
1. Check error message for specific issue
2. Fix the problem (usually URL or permissions)
3. Click "Download" again

---

## Updating the Database

When you add new articles locally:

### Option 1: Re-upload Everything

```bash
# 1. Run local ingestion (creates manifest automatically)
python scripts/ingest_all_articles.py
# or
python scripts/ingest_all_articles_low_memory.py

# 2. Re-upload to cloud storage
# (Use same commands from Step 2)

# 3. In Render Admin UI, click "Download" again
```

### Option 2: Incremental Upload (Advanced)

Only upload changed files:

```bash
# For Google Cloud Storage
gsutil rsync -r data/vector_db gs://care-beacon-vectordb/data/vector_db

# For AWS S3
aws s3 sync data/vector_db s3://care-beacon-vectordb/data/vector_db
```

---

## Cost Summary

### Free Tier (What You're Using)

| Service | Free Tier | Usage | Cost |
|---------|-----------|-------|------|
| Google Cloud Storage | 5GB | 1.3GB | $0 |
| AWS S3 | 5GB + 20K requests | 1.3GB | $0 |
| Render Free Tier | 512MB RAM | API only | $0 |
| **Total** | | | **$0/month** |

### If You Need More Performance

| Upgrade | Cost | Benefit |
|---------|------|---------|
| Render Starter | $7/mo | 512MB → 2GB RAM, faster network |
| Google Cloud Storage | $0.026/GB | Beyond 5GB |
| AWS S3 | $0.023/GB | Beyond 5GB |

---

## Next Steps

✅ **You're all set for your demo!**

Your Care-Beacon app is now running with a full vector database, and you can:
- Search for cancer information
- View statistics
- Show real-time query performance
- Demonstrate the RAG pipeline

### For Production

When ready to move beyond the demo:
1. Add authentication to Admin endpoints
2. Set up CI/CD for automatic database updates
3. Consider paid tiers for better performance
4. Implement proper error monitoring
5. Add usage analytics

---

## Summary of What You Built

```
┌─────────────────────┐
│  Local Development  │
│   (Your Machine)    │
└─────────┬───────────┘
          │
          │ 1. Create manifest
          │ 2. Upload files
          ↓
┌─────────────────────┐
│  Cloud Storage      │
│  (GCS/S3/Netlify)   │
│                     │
│  - manifest.json    │
│  - vector_db/...    │
└─────────┬───────────┘
          │
          │ 3. Configure URL
          │ 4. Download via UI
          ↓
┌─────────────────────┐
│  Render.com         │
│  (Production API)   │
│                     │
│  - Downloaded DB    │
│  - Ready to query!  │
└─────────────────────┘
```

## Additional FAQs

### Q: Where should the manifest file be located?

**A:** The manifest should be **inside the `data/vector_db/` folder** (`data/vector_db/vector_db_manifest.json`).

**Why?** The manifest describes that specific vector database, so it should stay with the database during backups and uploads. When the database folder is backed up (renamed to `vector_db_backup_TIMESTAMP`), the manifest moves with it.

### Q: Where should I upload the manifest in cloud storage?

**A:** Upload the entire `vector_db` folder, which includes the manifest inside:
- ✅ Correct: `https://your-bucket.com/vector_db/vector_db_manifest.json`
- ✅ Correct: `https://your-bucket.com/vector_db/chroma.sqlite3`
- ✅ Correct: `https://your-bucket.com/vector_db/[uuid]/data_level0.bin`
- ❌ Wrong: `https://your-bucket.com/vector_db_manifest.json` (manifest outside vector_db)

### Q: What's the correct base URL format?

**A:** The base URL should point to your bucket root and end with `/`:
- ✅ Correct: `https://storage.googleapis.com/my-bucket/`
- ❌ Wrong: `https://storage.googleapis.com/my-bucket/data/`
- ❌ Wrong: `https://storage.googleapis.com/my-bucket` (missing trailing slash)

---

**Congratulations!** 🎉 You've deployed a full RAG system without dealing with memory constraints!
