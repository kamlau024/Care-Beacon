# 📱 Mobile Access Guide - Use Care Beacon from Anywhere

This guide shows you how to access Care Beacon from your phone when you're **not on your home network**.

## 🎯 Your Use Case

You want to:
- Access the web app from your phone
- Use it when you're away from home (different network)
- Have both the web client and API accessible

## ✅ Solution: Multiple ngrok Tunnels

Yes, you can expose **both** `localhost:3000` (web) and `localhost:8000` (API) via ngrok!

---

## 🚀 Quick Start (Easiest Method)

I've created a helper script that sets up both tunnels for you.

### Step 1: Start Your Services

Make sure Docker and the web dev server are running:

```bash
# Terminal 1 - Docker (if not already running)
docker-compose up -d

# Terminal 2 - Web dev server (from web-client directory)
cd web-client
npm run dev
```

### Step 2: Start ngrok Tunnels

```bash
# From the Care-Beacon root directory
./start-ngrok.sh
```

This starts **both** tunnels at once!

### Step 3: Get Your URLs

Open the ngrok dashboard in your browser:
```
http://localhost:4040
```

You'll see two tunnels:
```
API (port 8000):  https://abc123.ngrok.io
Web (port 3000):  https://xyz789.ngrok.io
```

### Step 4: Update Web Client Configuration

Edit `web-client/.env.local`:
```bash
NEXT_PUBLIC_API_URL=https://abc123.ngrok.io  # Use YOUR API URL
```

### Step 5: Restart Web Dev Server

```bash
# In the web-client terminal (Ctrl+C to stop)
npm run dev
```

### Step 6: Access from Your Phone

Open your phone's browser:
```
https://xyz789.ngrok.io  # Use YOUR web URL
```

Done! 🎉

---

## 🛠️ Alternative Methods

### Method A: Manual Two-Tunnel Setup

If you prefer manual control:

**Terminal 1:**
```bash
ngrok http 8000
```

**Terminal 2:**
```bash
ngrok http 3000
```

Each terminal shows its own tunnel URL.

### Method B: Using Config File

Start both at once with the config file:

```bash
ngrok start --all --config ngrok.yml
```

View dashboard at http://localhost:4040

---

## 💰 ngrok Plans Comparison

### Free Plan (What You Probably Have)
- ✅ Multiple tunnels (run separately or with config)
- ✅ Random URLs (e.g., `abc123.ngrok.io`)
- ✅ Up to 2-hour sessions
- ❌ URLs change on restart
- ❌ No custom domains

**Best for:** Testing, development, occasional use

### Paid Plan ($8-10/month)
- ✅ Custom subdomains (e.g., `carebeacon-api.ngrok.io`)
- ✅ Longer sessions
- ✅ URLs stay the same
- ✅ More simultaneous tunnels

**Best for:** Regular use, professional development

---

## 📋 Complete Workflow

Here's the full workflow when you want to use the app from your phone:

### One-Time Setup:

1. Install ngrok: https://ngrok.com/download
2. Files already created for you:
   - `ngrok.yml` - Configuration
   - `start-ngrok.sh` - Helper script

### Every Time You Want to Use:

1. **Start services:**
   ```bash
   docker-compose up -d
   cd web-client && npm run dev
   ```

2. **Start ngrok:**
   ```bash
   ./start-ngrok.sh
   ```

3. **Get URLs from dashboard:**
   ```
   http://localhost:4040
   ```

4. **Update .env.local:**
   ```bash
   # In web-client/.env.local
   NEXT_PUBLIC_API_URL=https://your-api-url.ngrok.io
   ```

5. **Restart web server:**
   ```bash
   cd web-client
   npm run dev  # Restart to load new env
   ```

6. **Access from phone:**
   ```
   https://your-web-url.ngrok.io
   ```

### When Done:

1. Stop ngrok (Ctrl+C in the ngrok terminal)
2. Optional: Stop dev server and Docker
3. Optional: Revert .env.local to `http://localhost:8000`

---

## 🧪 Testing

### 1. Test API Directly

From your phone's browser:
```
https://your-api-url.ngrok.io/health
```

Should show:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  ...
}
```

### 2. Test Web App

From your phone's browser:
```
https://your-web-url.ngrok.io
```

System Health card should show:
- ✅ Overall Status: HEALTHY
- ✅ Vector Database: Connected
- ✅ Redis Cache: Connected
- ✅ LLM Client: Ready

### 3. Test Search

Type a question and verify you get results with citations.

---

## 🚨 Troubleshooting

### "Failed to check system health"

**Problem:** Web client can't reach API

**Solutions:**
1. Check .env.local has correct ngrok API URL
2. Restart web dev server after changing .env.local
3. Verify API tunnel is running: curl https://your-api-url.ngrok.io/health
4. Check ngrok dashboard (http://localhost:4040) for errors

### CORS Errors

**Solution:** Already fixed! CORS is set to allow all origins in development.

If you still see errors:
```bash
docker-compose restart api
```

### ngrok URLs Changed

**Problem:** URLs change every time you restart ngrok (free plan)

**Solutions:**
1. Update .env.local with new API URL
2. Restart web dev server
3. OR upgrade to ngrok paid plan for stable URLs

### Web App Loads but API Calls Fail

**Problem:** Old API URL in .env.local

**Solution:**
1. Open http://localhost:4040
2. Copy the current API tunnel URL
3. Update .env.local
4. **MUST restart** web dev server (Ctrl+C, then `npm run dev`)

### ngrok Session Expired (Free Plan)

**Problem:** Free sessions expire after 2 hours

**Solution:**
1. Restart ngrok
2. Get new URLs from http://localhost:4040
3. Update .env.local
4. Restart web dev server

---

## 💡 Pro Tips

### 1. Use ngrok Dashboard

Always keep http://localhost:4040 open in a browser tab to:
- See current tunnel URLs
- Monitor incoming requests
- Debug issues
- View request/response details

### 2. Save URLs in Notes

Copy both URLs to your phone's notes app:
```
API: https://abc123.ngrok.io
Web: https://xyz789.ngrok.io
```

This way you don't have to check the dashboard every time.

### 3. Create a .env.local.ngrok Backup

Save your ngrok API URL:

```bash
# .env.local.ngrok (backup file)
NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
```

Then when switching:
```bash
# For ngrok
cp web-client/.env.local.ngrok web-client/.env.local

# For localhost
cp web-client/.env.local.local web-client/.env.local
```

### 4. Use ngrok Authtoken (Optional)

Get longer sessions and more features:

```bash
# Sign up at ngrok.com, get your authtoken
ngrok config add-authtoken YOUR_TOKEN
```

### 5. Bookmark the Web URL

Add the web ngrok URL to your phone's home screen for quick access!

---

## 🔐 Security Notes

### Current Setup (Development)
- ⚠️ Anyone with the ngrok URL can access your app
- ⚠️ No authentication
- ⚠️ CORS allows all origins
- ⚠️ API calls use your OpenAI API key

### Recommendations:
1. **Don't share ngrok URLs publicly** - Keep them private
2. **Use for testing only** - Not for production
3. **Monitor usage** - Check OpenAI API usage
4. **Stop tunnels when done** - Don't leave running overnight
5. **For production** - Use proper hosting with authentication

---

## 📚 Files Created for You

All in the project root:

1. **ngrok.yml** - Configuration for both tunnels
2. **start-ngrok.sh** - Helper script to start both
3. **MOBILE_ACCESS.md** (this file) - Complete guide

In web-client:
- **NGROK_SETUP.md** - Detailed ngrok guide
- **NGROK_QUICK_FIX.md** - Quick reference
- **.env.local** - Environment configuration

---

## 🎬 Quick Reference

### Start Everything:
```bash
docker-compose up -d                  # Start API + Redis
cd web-client && npm run dev          # Start web dev server (different terminal)
./start-ngrok.sh                      # Start ngrok tunnels (different terminal)
```

### Get URLs:
```
http://localhost:4040
```

### Update Config:
```bash
# Edit web-client/.env.local
NEXT_PUBLIC_API_URL=https://your-api-url.ngrok.io
```

### Restart Web:
```bash
cd web-client
npm run dev  # Restart to load new env
```

### Access from Phone:
```
https://your-web-url.ngrok.io
```

### Stop:
```bash
Ctrl+C in ngrok terminal
```

---

## ❓ FAQ

**Q: Can I use just one ngrok tunnel?**
A: You need two - one for the API and one for the web client. They can't share a tunnel because they're on different ports.

**Q: Do the URLs change every time?**
A: On free ngrok, yes. Paid plans give you stable custom subdomains.

**Q: Can I use this in production?**
A: No, this is for development only. For production, use proper hosting (Vercel, AWS, etc.)

**Q: How much does ngrok cost?**
A: Free plan works great for testing. Paid plans start at ~$8/month for stable URLs.

**Q: Can my friends access it?**
A: Yes, if you share the ngrok URL. But they'll use your OpenAI API quota!

**Q: What if I'm on my home network?**
A: Just use http://localhost:3000 - no ngrok needed.

**Q: Can I use cloudflared or localtunnel instead?**
A: Yes! The concept is the same - expose both ports and update .env.local.

---

## 🆘 Need Help?

1. Check ngrok dashboard: http://localhost:4040
2. Verify .env.local has correct URL
3. Make sure you restarted web dev server after changing .env.local
4. Check Docker containers: `docker-compose ps` (both should be healthy)
5. Test API directly: curl https://your-api-url.ngrok.io/health

---

**Status**: ✅ Ready to Use
**Updated**: 2025-11-08
**Your Setup**: Multiple ngrok tunnels (both ports exposed)
