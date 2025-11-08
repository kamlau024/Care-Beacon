# 🚀 Quick Fix: Access from Phone via ngrok

## ✅ What I Fixed

1. **Updated CORS** - API now accepts requests from any origin (including ngrok)
2. **Restarted API** - Docker container restarted with new config
3. **Created guides** - See `NGROK_SETUP.md` for full details

## 🎯 Quick Steps to Access from Phone

### Step 1: Start ngrok for API (New Terminal)

```bash
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### Step 2: Update Web Client Environment

Edit `web-client/.env.local`:

```bash
# Comment out localhost and add your ngrok URL:
# NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
```

**Important**: Use the URL from Step 1!

### Step 3: Restart Web Dev Server

```bash
# In web-client directory
# Press Ctrl+C to stop current server
npm run dev
```

### Step 4: Start ngrok for Web Client (New Terminal)

```bash
cd web-client
ngrok http 3000
```

Copy the HTTPS URL (e.g., `https://xyz789.ngrok.io`)

### Step 5: Open on Your Phone

Open your phone's browser and go to the URL from Step 4:
```
https://xyz789.ngrok.io
```

## ✅ Verify It Works

The System Health card should now show:
- ✓ Overall Status: HEALTHY (green checkmark)
- ✓ Vector Database: Connected
- ✓ Redis Cache: Connected
- ✓ LLM Client: Ready

## 🔄 To Switch Back to Local

Edit `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
# NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
```

Then restart: `npm run dev`

## 📱 Current Terminal Setup

You should have:
1. **Terminal 1**: Docker (`docker-compose up -d`)
2. **Terminal 2**: ngrok for API (`ngrok http 8000`)
3. **Terminal 3**: Web dev server (`npm run dev`)
4. **Terminal 4**: ngrok for web (`ngrok http 3000`)

---

**Need more details?** See `NGROK_SETUP.md` for troubleshooting and advanced setup.
