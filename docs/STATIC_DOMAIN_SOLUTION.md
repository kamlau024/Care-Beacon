# Static Domain Solution - ngrok + localtunnel

## 🔍 The Problem

Your ngrok free account has a **static domain** that can't be removed:
- `boughless-lawrence-shimmeringly.ngrok-free.dev`
- Every ngrok tunnel automatically uses this domain
- You can't run multiple ngrok tunnels with different URLs
- This prevents exposing both port 8000 and 3000 via ngrok alone

## ✅ The Solution: Mixed Tunneling

Use **different tunneling services** for each port:
- **ngrok** for API (port 8000) → Uses your static domain
- **localtunnel** for Web (port 3000) → Gets random URL

### Why This Works

- ngrok: Stable URL for your API (good for configuration)
- localtunnel: Free, unlimited, works alongside ngrok
- Each service gets its own unique URL
- Both can run simultaneously

---

## 🚀 Quick Start

### One Command Setup

```bash
./start-mixed-tunnels.sh
```

This will:
1. Start ngrok for API on port 8000
2. Start localtunnel for Web on port 3000
3. Show you both URLs
4. Give you exact configuration steps

### What You'll Get

```
🔌 API Tunnel (ngrok):
   https://boughless-lawrence-shimmeringly.ngrok-free.dev

🌐 Web Tunnel (localtunnel):
   https://random-name-123.loca.lt
```

### Configuration Steps

The script will tell you exactly what to do:

1. **Update .env.local:**
   ```bash
   NEXT_PUBLIC_API_URL=https://boughless-lawrence-shimmeringly.ngrok-free.dev
   ```

2. **Restart web server:**
   ```bash
   cd web-client && npm run dev
   ```

3. **Access from phone:**
   ```
   https://random-name-123.loca.lt
   ```

---

## 📱 First Time Using Localtunnel

When you first open the localtunnel URL on your phone, you'll see a page that says:

```
⚠️  Tunnel Password Required
Click the button below to continue to your tunnel
```

**This is normal!** Just click "Continue" and you'll see your app.

This is localtunnel's security feature - not a problem with the setup.

---

## 🔄 Manual Alternative

If you prefer to run commands manually:

**Terminal 1 - API (ngrok):**
```bash
ngrok http 8000
```
Uses: `https://boughless-lawrence-shimmeringly.ngrok-free.dev`

**Terminal 2 - Web (localtunnel):**
```bash
npx localtunnel --port 3000
```
Shows you the URL, like: `https://smooth-pandas-play.loca.lt`

Then configure as above.

---

## 🆚 Comparison: ngrok vs localtunnel

### ngrok
- ✅ Your static domain (stable)
- ✅ Fast and reliable
- ✅ Has dashboard (http://localhost:4040)
- ✅ Better for API (needs stable URL)
- ❌ Can only use one tunnel (free tier with static domain)

### localtunnel
- ✅ Unlimited free tunnels
- ✅ Random URLs (changes each session)
- ✅ No account needed
- ✅ Perfect for web client (URL can change)
- ⚠️  Shows "Continue" page on first visit
- ⚠️  Slightly slower than ngrok

---

## 💡 Pro Tips

### 1. Stable API URL

Your API URL is always the same:
```
https://boughless-lawrence-shimmeringly.ngrok-free.dev
```

So you only need to update .env.local **once**! It won't change.

### 2. Save Localtunnel URL

The web URL changes each time you restart. Save it to your phone's notes:
```
Today's web URL: https://smooth-pandas-play.loca.lt
```

### 3. Bookmark It

Add the localtunnel URL to your phone's home screen for quick access.

### 4. Alternative: Use a Custom Subdomain

Localtunnel supports custom subdomains (first-come-first-served):
```bash
npx localtunnel --port 3000 --subdomain carebeacon-web
```

If available, you'll always get: `https://carebeacon-web.loca.lt`

---

## 🚨 Troubleshooting

### "Tunnel not found" on localtunnel

**Solution:** The tunnel URL changed or expired. Check:
```bash
cat /tmp/localtunnel.log
```

Or just restart:
```bash
./start-mixed-tunnels.sh
```

### ngrok API URL Not Working

**Solution:** Make sure you're using the correct static domain:
```bash
https://boughless-lawrence-shimmeringly.ngrok-free.dev
```

Check it at: http://localhost:4040

### Web Client Can't Reach API

**Solution:**
1. Verify .env.local has correct API URL
2. Restart web dev server: `cd web-client && npm run dev`
3. Make sure both tunnels are running

---

## 🎯 Complete Workflow

### Every Time You Want to Use from Phone:

1. **Start tunnels:**
   ```bash
   ./start-mixed-tunnels.sh
   ```

2. **Note the URLs** (shown in output)

3. **If first time or API URL changed, update .env.local:**
   ```bash
   NEXT_PUBLIC_API_URL=https://boughless-lawrence-shimmeringly.ngrok-free.dev
   ```

4. **Restart web server:**
   ```bash
   cd web-client && npm run dev
   ```

5. **Access from phone:**
   - Open localtunnel URL
   - Click "Continue" (first time only)
   - Use the app!

---

## 🔐 Security Notes

- Your ngrok static domain is public (anyone can access)
- localtunnel URLs are random and harder to guess
- Both services should only be used for development/testing
- Don't share URLs publicly
- Monitor your OpenAI API usage

---

## 💰 Cost Comparison

### Current Setup (Free)
- ngrok free: Static domain for API ✅
- localtunnel: Unlimited for Web ✅
- **Total cost: $0/month**

### Paid ngrok Alternative
- ngrok Pro: $8-10/month
- Multiple static domains
- Better performance
- No "Continue" page

**For casual use, the free mixed approach works great!**

---

## 📚 Alternative Services

If localtunnel doesn't work well, try:

1. **Cloudflare Tunnel (cloudflared):**
   ```bash
   brew install cloudflare/cloudflare/cloudflared
   cloudflared tunnel --url http://localhost:3000
   ```

2. **serveo.net:**
   ```bash
   ssh -R 80:localhost:3000 serveo.net
   ```

3. **bore.pub:**
   ```bash
   bore local 3000 --to bore.pub
   ```

All are free and work alongside ngrok!

---

**Status**: ✅ Ready to Use
**Script**: `start-mixed-tunnels.sh`
**Updated**: 2025-11-08
**Your Setup**: ngrok (API) + localtunnel (Web)
