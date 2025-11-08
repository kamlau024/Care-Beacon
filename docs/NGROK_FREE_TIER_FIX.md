# ngrok Free Tier - Dual Tunnel Fix

## 🐛 The Problem You Encountered

When using `start-ngrok.sh` with the config file, both ports mapped to the **same URL**:

```
https://boughless-lawrence-shimmeringly.ngrok-free.dev -> localhost:8000
https://boughless-lawrence-shimmeringly.ngrok-free.dev -> localhost:3000
```

This doesn't work because ngrok can't route to different ports using the same URL.

## ✅ The Solution

Use **TWO separate ngrok instances** instead of the config file. Each instance gets its own unique URL.

### Use the New Script

```bash
./start-ngrok-dual.sh
```

This runs:
- ngrok instance #1 → port 8000 (API) → gets URL like `https://abc123.ngrok-free.dev`
- ngrok instance #2 → port 3000 (web) → gets URL like `https://xyz789.ngrok-free.dev`

Each has its own dashboard:
- API: http://localhost:4040
- Web: http://localhost:4041

## 🚀 Quick Start

### 1. Stop the old ngrok

```bash
# Press Ctrl+C in the terminal running ngrok
# Or kill all ngrok processes:
pkill -f ngrok
```

### 2. Start the new dual setup

```bash
./start-ngrok-dual.sh
```

The script will automatically:
- Start both tunnels
- Show you both URLs
- Give you the exact command to update .env.local

### 3. Copy the API URL

The script shows something like:
```
🔌 API Tunnel (port 8000):
   https://abc123.ngrok-free.dev
```

### 4. Update .env.local

```bash
# Edit web-client/.env.local
NEXT_PUBLIC_API_URL=https://abc123.ngrok-free.dev
```

### 5. Restart web dev server

```bash
cd web-client
npm run dev
```

### 6. Access from phone

Use the Web URL shown:
```
🌐 Web Tunnel (port 3000):
   https://xyz789.ngrok-free.dev
```

## 📊 Dashboard URLs

- **API Dashboard:** http://localhost:4040
- **Web Dashboard:** http://localhost:4041

Each dashboard shows its own tunnel info and request logs.

## 🔄 Comparison

### Old Method (doesn't work on free tier)
```bash
./start-ngrok.sh  # Uses config file
# ❌ Both ports → same URL
```

### New Method (works perfectly)
```bash
./start-ngrok-dual.sh  # Separate instances
# ✅ Each port → unique URL
```

## 💡 Why This Happens

ngrok's **free tier** has limitations when using config files with multiple tunnels:
- Single tunnel: ✅ Works perfectly
- Multiple tunnels via config: ⚠️ May share same URL
- Multiple separate instances: ✅ Each gets unique URL

**Paid tier** ($8-10/month) supports proper multi-tunnel configs with custom subdomains.

## 🛠️ Manual Alternative

If you prefer manual control:

**Terminal 1:**
```bash
ngrok http 8000
```

**Terminal 2:**
```bash
ngrok http 3000
```

Same result - each gets its own URL!

## 📋 Quick Reference

| Task | Command |
|------|---------|
| Start both tunnels | `./start-ngrok-dual.sh` |
| Stop tunnels | `Ctrl+C` or `pkill -f ngrok` |
| View API dashboard | http://localhost:4040 |
| View Web dashboard | http://localhost:4041 |
| Update API URL | Edit `web-client/.env.local` |
| Restart web server | `cd web-client && npm run dev` |

## ✅ Verification

After setup, test:

1. **API:** curl https://your-api-url.ngrok-free.dev/health
2. **Web:** Open https://your-web-url.ngrok-free.dev on phone
3. **Health Check:** Should show all services connected ✅

---

**Status:** ✅ Fixed with dual instance script
**New Script:** `start-ngrok-dual.sh`
**Updated:** 2025-11-08
