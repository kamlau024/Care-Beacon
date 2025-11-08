#!/bin/bash
# Start ngrok for API and localtunnel for web
# This works around ngrok's single static domain limitation

echo "🚀 Starting tunnels for Care Beacon (ngrok + localtunnel)..."
echo ""

# Kill existing processes
pkill -f ngrok 2>/dev/null
pkill -f localtunnel 2>/dev/null
sleep 1

echo "📡 Starting ngrok for API (port 8000)..."
echo "   Using your static domain: boughless-lawrence-shimmeringly.ngrok-free.dev"
ngrok http 8000 > /tmp/ngrok-api.log 2>&1 &
NGROK_PID=$!

sleep 3

echo ""
echo "🌐 Starting localtunnel for Web (port 3000)..."
npx localtunnel --port 3000 > /tmp/localtunnel.log 2>&1 &
LT_PID=$!

sleep 5

echo ""
echo "✅ Both tunnels started!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔌 API Tunnel (ngrok):"
echo "   https://boughless-lawrence-shimmeringly.ngrok-free.dev"
echo "   Dashboard: http://localhost:4040"
echo ""

# Try to get localtunnel URL from logs
sleep 2
LT_URL=$(grep -o "https://.*\.loca\.lt" /tmp/localtunnel.log 2>/dev/null | head -1)

if [ ! -z "$LT_URL" ]; then
    echo "🌐 Web Tunnel (localtunnel):"
    echo "   $LT_URL"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  NEXT STEPS:"
    echo ""
    echo "1. Update web-client/.env.local:"
    echo "   NEXT_PUBLIC_API_URL=https://boughless-lawrence-shimmeringly.ngrok-free.dev"
    echo ""
    echo "2. Restart web dev server:"
    echo "   cd web-client && npm run dev"
    echo ""
    echo "3. Access from your phone:"
    echo "   $LT_URL"
    echo ""
    echo "   ⚠️  Note: First time you open the localtunnel URL,"
    echo "   you'll see a page asking you to click 'Continue'."
    echo "   This is normal security for localtunnel."
else
    echo "⚠️  Could not auto-detect localtunnel URL"
    echo "   Check: cat /tmp/localtunnel.log"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Tips:"
echo "   • ngrok dashboard: http://localhost:4040"
echo "   • Press Ctrl+C to stop both tunnels"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping tunnels..."
    kill $NGROK_PID 2>/dev/null
    kill $LT_PID 2>/dev/null
    pkill -f ngrok 2>/dev/null
    pkill -f localtunnel 2>/dev/null
    echo "✅ Tunnels stopped"
    exit 0
}

trap cleanup INT TERM

echo "Running... (Press Ctrl+C to stop)"
echo ""
wait
