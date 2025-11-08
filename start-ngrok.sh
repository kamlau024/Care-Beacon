#!/bin/bash
# Start ngrok tunnels for Care Beacon
# This script starts both API and web tunnels and displays the URLs

echo "🚀 Starting ngrok tunnels for Care Beacon..."
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok is not installed!"
    echo "Install it from: https://ngrok.com/download"
    exit 1
fi

# Check if ngrok.yml exists
if [ ! -f "ngrok.yml" ]; then
    echo "❌ ngrok.yml not found!"
    echo "Please run this script from the Care-Beacon directory"
    exit 1
fi

# Start ngrok with both tunnels
echo "Starting tunnels..."
ngrok start --all --config ngrok.yml &

# Wait a bit for ngrok to start
sleep 3

echo ""
echo "✅ ngrok tunnels started!"
echo ""
echo "📊 View the ngrok dashboard at: http://localhost:4040"
echo ""
echo "⚠️  NEXT STEPS:"
echo "1. Go to http://localhost:4040 to see your tunnel URLs"
echo "2. Copy the API tunnel URL (port 8000)"
echo "3. Update web-client/.env.local with: NEXT_PUBLIC_API_URL=<api-url>"
echo "4. Restart your web dev server: cd web-client && npm run dev"
echo "5. Use the web tunnel URL (port 3000) to access from your phone"
echo ""
echo "Press Ctrl+C to stop the tunnels when done"
echo ""

# Keep the script running (ngrok is in background)
wait
