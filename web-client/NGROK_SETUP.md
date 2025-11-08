# ngrok Setup Guide - Access from Mobile/Remote

This guide shows you how to access Care Beacon from your phone or any remote device using ngrok.

## Problem

When accessing via ngrok, you might see "Failed to check system health" because:
- The web client tries to connect to `http://localhost:8000`
- `localhost` on your phone points to the phone itself, not your computer
- You need to expose BOTH the API and web client publicly

## ✅ Solution: Two Options

### Option 1: Expose API via ngrok (Recommended)

This allows you to access the web client via ngrok and it will connect to a publicly accessible API.

#### Step 1: Start ngrok for the API

In a new terminal:

```bash
# Expose the API (port 8000)
ngrok http 8000
```

You'll see output like:
```
Forwarding   https://abc123.ngrok.io -> http://localhost:8000
```

Copy the `https://abc123.ngrok.io` URL.

#### Step 2: Update Web Client Environment

Edit `web-client/.env.local`:

```bash
# Replace with your ngrok API URL
NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
```

#### Step 3: Restart Web Client

```bash
# Stop the current dev server (Ctrl+C)
# Then restart
npm run dev
```

#### Step 4: Start ngrok for Web Client

In another terminal:

```bash
cd web-client
ngrok http 3000
```

You'll see:
```
Forwarding   https://xyz789.ngrok.io -> http://localhost:3000
```

#### Step 5: Access from Phone

Open your phone's browser and go to:
```
https://xyz789.ngrok.io
```

The app will now work correctly because it's connecting to your publicly accessible API at `https://abc123.ngrok.io`.

---

### Option 2: Use ngrok Subdomain (ngrok Pro)

If you have ngrok Pro, you can use custom subdomains:

```bash
# Terminal 1 - API
ngrok http 8000 --subdomain=carebeacon-api

# Terminal 2 - Web Client
ngrok http 3000 --subdomain=carebeacon-web
```

Then update `.env.local`:
```bash
NEXT_PUBLIC_API_URL=https://carebeacon-api.ngrok.io
```

---

## 🔧 Configuration Details

### CORS Configuration (Already Fixed)

The API's CORS has been updated to allow all origins for development:

**File**: `config/config.yaml`
```yaml
api:
  cors_origins:
    - "*"  # Allows requests from any origin
```

**Important**: For production, change this to specific domains:
```yaml
cors_origins:
  - "https://your-domain.com"
  - "https://www.your-domain.com"
```

### Environment Variables

**Development (local)**:
```bash
# web-client/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Testing with ngrok**:
```bash
# web-client/.env.local
NEXT_PUBLIC_API_URL=https://your-api-ngrok-url.ngrok.io
```

**Production**:
```bash
# web-client/.env.local
NEXT_PUBLIC_API_URL=https://api.your-domain.com
```

---

## 🧪 Testing the Setup

### 1. Test API Directly

```bash
# Test from your phone's browser
https://your-api-ngrok-url.ngrok.io/health

# Should return:
{
  "status": "healthy",
  "version": "2.0.0",
  ...
}
```

### 2. Test Web Client

```bash
# Open from your phone
https://your-web-ngrok-url.ngrok.io

# Check System Health card - should show:
✓ Overall Status: HEALTHY
✓ Vector Database: Connected
✓ Redis Cache: Connected
✓ LLM Client: Ready
```

### 3. Test Search

- Type a question: "What are symptoms of breast cancer?"
- Click Search
- Should see results with citations

---

## 📱 Quick Setup Checklist

- [ ] Start Docker containers (`docker-compose up -d`)
- [ ] Start ngrok for API (`ngrok http 8000`)
- [ ] Copy ngrok API URL
- [ ] Update `web-client/.env.local` with ngrok API URL
- [ ] Restart web dev server (`npm run dev`)
- [ ] Start ngrok for web client (`ngrok http 3000`)
- [ ] Open ngrok web URL on your phone
- [ ] Test health check (should be green)
- [ ] Test a search query

---

## 🚨 Troubleshooting

### "Failed to check system health"

**Cause**: Web client can't reach the API

**Fix**:
1. Make sure `NEXT_PUBLIC_API_URL` in `.env.local` points to your ngrok API URL
2. Restart the Next.js dev server after changing `.env.local`
3. Check ngrok API is running: `curl https://your-api-url.ngrok.io/health`

### CORS Error in Browser Console

**Cause**: API not accepting requests from ngrok domain

**Fix**: Already done! CORS is set to `"*"` in `config/config.yaml`

If you see this error, restart the API:
```bash
docker-compose restart api
```

### "This site can't be reached"

**Cause**: ngrok tunnel is not running

**Fix**: Start ngrok in a new terminal:
```bash
ngrok http 8000  # for API
ngrok http 3000  # for web
```

### ngrok Session Expired

**Cause**: Free ngrok sessions expire after 2 hours

**Fix**:
1. Restart ngrok (URLs will change)
2. Update `.env.local` with new API URL
3. Restart web dev server

### Environment Variable Not Updated

**Cause**: Next.js caches environment variables

**Fix**: Must restart the dev server:
```bash
# Stop with Ctrl+C
npm run dev  # Start again
```

---

## 💡 Tips

1. **Keep terminals organized**:
   - Terminal 1: Docker containers
   - Terminal 2: ngrok for API
   - Terminal 3: Next.js dev server
   - Terminal 4: ngrok for web client

2. **Save ngrok URLs**: Write them down as they change each restart (free tier)

3. **Use ngrok dashboard**: Go to http://localhost:4040 to see all requests

4. **Test locally first**: Make sure everything works on `localhost` before using ngrok

5. **Pro tip**: If you use ngrok often, consider the paid plan for:
   - Custom subdomains (URLs don't change)
   - Longer session duration
   - More simultaneous tunnels

---

## 🔐 Security Notes

**Development Setup** (current):
- CORS allows all origins (`*`)
- API accessible to anyone with ngrok URL
- No authentication required

**Production Setup** (recommended):
- CORS limited to specific domains
- API behind authentication
- HTTPS only
- Rate limiting per user/IP
- API keys required

---

## 📚 Additional Resources

- ngrok docs: https://ngrok.com/docs
- Next.js environment variables: https://nextjs.org/docs/basic-features/environment-variables
- CORS explained: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS

---

## Example Terminal Setup

```bash
# Terminal 1 - Start Docker
cd /Users/kamlau/Projects/Care-Beacon
docker-compose up -d

# Terminal 2 - ngrok for API
ngrok http 8000
# Copy the https URL: https://abc123.ngrok.io

# Terminal 3 - Update environment and start web
cd /Users/kamlau/Projects/Care-Beacon/web-client
# Edit .env.local: NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
npm run dev

# Terminal 4 - ngrok for web
cd /Users/kamlau/Projects/Care-Beacon/web-client
ngrok http 3000
# Copy the https URL: https://xyz789.ngrok.io

# Phone Browser
# Open: https://xyz789.ngrok.io
```

---

**Status**: ✅ CORS Fixed - Ready for ngrok Testing
**Last Updated**: 2025-11-08
