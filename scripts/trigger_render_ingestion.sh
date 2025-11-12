#!/bin/bash
# Trigger ingestion on Render.com via API endpoint
#
# Usage:
#   ./scripts/trigger_render_ingestion.sh https://your-api.onrender.com

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if API URL is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: API URL is required${NC}"
    echo ""
    echo "Usage: $0 <API_URL>"
    echo ""
    echo "Example:"
    echo "  $0 https://care-beacon-api.onrender.com"
    exit 1
fi

API_URL="$1"
ENDPOINT="${API_URL}/api/v1/admin/ingest"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Trigger Render Ingestion                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}API URL:${NC} $API_URL"
echo -e "${YELLOW}Endpoint:${NC} $ENDPOINT"
echo ""
echo -e "${YELLOW}⚠️  This will re-ingest all articles and may take 5-10 minutes${NC}"
echo -e "${YELLOW}⚠️  Cost: ~\$0.02 for embeddings${NC}"
echo ""
read -p "Continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
    echo -e "${RED}Cancelled${NC}"
    exit 0
fi

echo -e "${GREEN}Triggering ingestion...${NC}"
echo ""

# Trigger ingestion (with extended timeout for long-running operation)
response=$(curl -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -w "\n%{http_code}" \
    --max-time 1000 \
    --silent \
    --show-error)

# Extract HTTP status code and body
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

echo ""
echo "HTTP Status: $http_code"
echo ""

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✅ Ingestion completed successfully!${NC}"
    echo ""
    echo "$body" | jq '.'
else
    echo -e "${RED}❌ Ingestion failed${NC}"
    echo ""
    echo "$body" | jq '.' || echo "$body"
    exit 1
fi
