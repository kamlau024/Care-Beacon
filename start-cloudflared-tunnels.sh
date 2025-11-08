#!/bin/bash
# Start Cloudflare tunnels for Care Beacon (no browser warnings!)
# Cloudflare Tunnel is free and has no browser warning pages

echo "🚀 Starting Cloudflare tunnels for Care Beacon..."
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "❌ cloudflared is not installed!"
    echo ""
    echo "Install with:"
    echo "  brew install cloudflare/cloudflare/cloudflared"
    echo ""
    echo "Or download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
    exit 1
fi

# Kill existing processes
pkill -f cloudflared 2>/dev/null
sleep 1

echo "📡 Starting Cloudflare tunnel for API (port 8000)..."
cloudflared tunnel --url http://localhost:8000 > /tmp/cloudflared-api.log 2>&1 &
API_PID=$!

sleep 5

echo "🌐 Starting Cloudflare tunnel for Web (port 3000)..."
cloudflared tunnel --url http://localhost:3000 > /tmp/cloudflared-web.log 2>&1 &
WEB_PID=$!

sleep 5

echo ""
echo "✅ Both Cloudflare tunnels started!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Extract URLs from logs
API_URL=$(grep -o "https://.*\.trycloudflare\.com" /tmp/cloudflared-api.log 2>/dev/null | head -1)
WEB_URL=$(grep -o "https://.*\.trycloudflare\.com" /tmp/cloudflared-web.log 2>/dev/null | head -1)

if [ ! -z "$API_URL" ]; then
    echo "🔌 API Tunnel:"
    echo "   $API_URL"
else
    echo "⚠️  Could not detect API URL"
    echo "   Check: cat /tmp/cloudflared-api.log"
fi

echo ""

if [ ! -z "$WEB_URL" ]; then
    echo "🌐 Web Tunnel:"
    echo "   $WEB_URL"
else
    echo "⚠️  Could not detect Web URL"
    echo "   Check: cat /tmp/cloudflared-web.log"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  NEXT STEPS:"
echo ""
if [ ! -z "$API_URL" ]; then
    echo "1. Update web-client/.env.local:"
    echo "   NEXT_PUBLIC_API_URL=$API_URL"
else
    echo "1. Check API log: cat /tmp/cloudflared-api.log"
    echo "   Then update web-client/.env.local with the API URL"
fi
echo ""
echo "2. Restart web dev server:"
echo "   cd web-client && npm run dev"
echo ""
if [ ! -z "$WEB_URL" ]; then
    echo "3. Access from your phone:"
    echo "   $WEB_URL"
else
    echo "3. Check web log: cat /tmp/cloudflared-web.log"
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✨ No browser warnings! No 'Continue' pages!"
echo "   Cloudflare tunnels work instantly from any device."
echo ""
echo "💡 Tips:"
echo "   • Press Ctrl+C to stop both tunnels"
echo "   • URLs change on restart (free tier)"
echo "   • Much faster than ngrok warning pages!"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping Cloudflare tunnels..."
    kill $API_PID 2>/dev/null
    kill $WEB_PID 2>/dev/null
    pkill -f cloudflared 2>/dev/null
    echo "✅ Tunnels stopped"
    exit 0
}

trap cleanup INT TERM

echo "Running... (Press Ctrl+C to stop)"
echo ""
wait
