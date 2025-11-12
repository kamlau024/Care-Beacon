#!/bin/bash
#
# Start Care-Beacon MCP Server (HTTP/SSE) for local testing
#

set -e

echo "========================================================================"
echo "Care-Beacon MCP Server (HTTP/SSE Transport)"
echo "========================================================================"
echo ""

# Configuration
export CARE_BEACON_API_URL="${CARE_BEACON_API_URL:-http://localhost:8000}"
export PORT="${PORT:-8001}"
export MCP_API_KEY="${MCP_API_KEY:-}"  # Empty for development mode

echo "📋 Configuration:"
echo "  API URL: $CARE_BEACON_API_URL"
echo "  Port: $PORT"
if [ -z "$MCP_API_KEY" ]; then
    echo "  Auth: Disabled (development mode)"
else
    echo "  Auth: Enabled (API key required)"
fi
echo ""

# Check if main API is running
echo "🔍 Checking if Care-Beacon API is accessible..."
if curl -s -f "$CARE_BEACON_API_URL/health" > /dev/null 2>&1; then
    echo "✅ API is accessible at $CARE_BEACON_API_URL"
else
    echo "⚠️  Warning: API may not be running at $CARE_BEACON_API_URL"
    echo "   Start the API first: python scripts/start_api.py"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "========================================================================"
echo "🚀 Starting MCP Server..."
echo "========================================================================"
echo ""
echo "SSE Endpoint: http://localhost:$PORT/sse"
echo "Health Check: http://localhost:$PORT/health"
echo "API Docs: http://localhost:$PORT/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the server
python mcp/sse/mcp_server.py
