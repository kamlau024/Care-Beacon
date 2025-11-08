# 📱 Quick Mobile Setup - 5 Minutes

## ✅ Yes, You Can Use Multiple ngrok Endpoints!

You can expose **both** localhost:3000 and localhost:8000 via ngrok simultaneously.

---

## 🚀 Super Quick Setup

### 1️⃣ Start ngrok (one command!)

```bash
./start-ngrok.sh
```

### 2️⃣ Get your URLs

Open: http://localhost:4040

You'll see:
- API URL: `https://abc123.ngrok.io` ← port 8000
- Web URL: `https://xyz789.ngrok.io` ← port 3000

### 3️⃣ Update config

Edit `web-client/.env.local`:
```bash
NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
```
☝️ Use YOUR API URL from step 2

### 4️⃣ Restart web server

```bash
cd web-client
npm run dev
```

### 5️⃣ Access from phone

Open: `https://xyz789.ngrok.io` (your web URL)

Done! 🎉

---

## 🔄 Every Time Workflow

**Start:**
```bash
./start-ngrok.sh
# Open http://localhost:4040
# Update .env.local with API URL
# Restart: cd web-client && npm run dev
```

**Use:**
```
Access web URL from your phone
```

**Stop:**
```bash
Ctrl+C in ngrok terminal
```

---

## 📋 What's Running

- ✅ Docker (API + Redis) - localhost:8000
- ✅ Next.js dev server - localhost:3000
- ✅ ngrok tunnel #1 - API (8000)
- ✅ ngrok tunnel #2 - Web (3000)

---

## 🧪 Quick Test

From your phone:

1. **API**: https://your-api-url.ngrok.io/health
   - Should return JSON with "status": "healthy"

2. **Web**: https://your-web-url.ngrok.io
   - Should load the app
   - System Health should be green ✅

3. **Search**: Type a question
   - Should get results with citations

---

## 🚨 Troubleshooting

**Problem:** "Failed to check system health"

**Fix:**
```bash
# 1. Check .env.local has correct ngrok API URL
# 2. Restart web dev server
cd web-client && npm run dev
```

**Problem:** URLs changed

**Fix:** ngrok free tier generates new URLs each time
```bash
# Get new URLs from: http://localhost:4040
# Update .env.local
# Restart web dev server
```

---

## 💡 Pro Tip

Create bookmarks:
```bash
# Save these for quick access
http://localhost:4040         # ngrok dashboard
```

---

See **MOBILE_ACCESS.md** for the complete guide!
