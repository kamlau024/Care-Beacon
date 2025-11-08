#!/bin/bash
# Start TWO separate ngrok instances for Care Beacon
# Each gets its own unique URL on free plan

echo "🚀 Starting dual ngrok tunnels for Care Beacon..."
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok is not installed!"
    echo "Install it from: https://ngrok.com/download"
    exit 1
fi

# Kill any existing ngrok processes
pkill -f ngrok 2>/dev/null
sleep 1

echo "📡 Starting API tunnel (port 8000)..."
NGROK_WEB_ADDR=localhost:4040 ngrok http 8000 --log=stdout > /tmp/ngrok-api.log 2>&1 &
API_PID=$!

sleep 2

echo "🌐 Starting Web tunnel (port 3000)..."
NGROK_WEB_ADDR=localhost:4041 ngrok http 3000 --log=stdout > /tmp/ngrok-web.log 2>&1 &
WEB_PID=$!

sleep 3

echo ""
echo "✅ Both ngrok tunnels started!"
echo ""
echo "📊 TUNNEL INFORMATION:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get API URL from ngrok API (first tunnel)
API_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | head -1 | cut -d'"' -f4)

# Get Web URL from ngrok API (second tunnel)
WEB_URL=$(curl -s http://localhost:4041/api/tunnels | grep -o '"public_url":"https://[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$API_URL" ]; then
    echo "⚠️  Could not detect API URL automatically"
    echo "   View tunnel URLs at: http://localhost:4040"
else
    echo ""
    echo "🔌 API Tunnel (port 8000):"
    echo "   $API_URL"
    echo "   Dashboard: http://localhost:4040"
fi

if [ -z "$WEB_URL" ]; then
    echo ""
    echo "⚠️  Could not detect Web URL automatically"
    echo "   View tunnel URLs at: http://localhost:4041"
else
    echo ""
    echo "🌐 Web Tunnel (port 3000):"
    echo "   $WEB_URL"
    echo "   Dashboard: http://localhost:4041"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  NEXT STEPS:"
echo ""
echo "1. Copy the API URL from above"
echo ""
echo "2. Edit web-client/.env.local and set:"
if [ ! -z "$API_URL" ]; then
    echo "   NEXT_PUBLIC_API_URL=$API_URL"
else
    echo "   NEXT_PUBLIC_API_URL=<your-api-url>"
fi
echo ""
echo "3. Restart your web dev server:"
echo "   cd web-client && npm run dev"
echo ""
echo "4. Access from your phone using the Web URL:"
if [ ! -z "$WEB_URL" ]; then
    echo "   $WEB_URL"
else
    echo "   <your-web-url>"
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Tips:"
echo "   • API Dashboard: http://localhost:4040"
echo "   • Web Dashboard: http://localhost:4041"
echo "   • Press Ctrl+C to stop both tunnels"
echo "   • URLs will change when you restart ngrok (free plan)"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping ngrok tunnels..."
    kill $API_PID 2>/dev/null
    kill $WEB_PID 2>/dev/null
    pkill -f ngrok 2>/dev/null
    echo "✅ Tunnels stopped"
    exit 0
}

# Trap Ctrl+C
trap cleanup INT TERM

# Keep script running
echo "Running... (Press Ctrl+C to stop)"
echo ""
wait
