#!/bin/bash
# Manual reingestion script for production
# Run this via Render Shell: bash scripts/reingest_production.sh

set -e  # Exit on error

echo "🔄 Starting manual reingestion..."
echo "⚠️  This will delete the existing vector database and rebuild it"
echo ""

# Confirm before proceeding
read -p "Are you sure you want to continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Reingestion cancelled"
    exit 0
fi

# Delete existing database
echo "🗑️  Removing existing database..."
rm -rf data/vector_db/*

# Create directory
mkdir -p data/vector_db

# Check for articles
echo "📄 Checking for source articles..."
ARTICLES_FOUND=false

if [ -d "scraped_data/bc-cancer/articles" ] && [ "$(find scraped_data/bc-cancer/articles -name '*.md' -type f | head -1)" ]; then
    ARTICLES_FOUND=true
    BC_COUNT=$(find scraped_data/bc-cancer/articles -name '*.md' -type f | wc -l)
    echo "  ✅ BC Cancer: $BC_COUNT articles"
fi

if [ -d "scraped_data/canadian-cancer-society/articles" ] && [ "$(find scraped_data/canadian-cancer-society/articles -name '*.md' -type f | head -1)" ]; then
    ARTICLES_FOUND=true
    CCS_COUNT=$(find scraped_data/canadian-cancer-society/articles -name '*.md' -type f | wc -l)
    echo "  ✅ Canadian Cancer Society: $CCS_COUNT articles"
fi

if [ "$ARTICLES_FOUND" = "false" ]; then
    echo "❌ No source articles found!"
    echo "⚠️  Make sure scraped_data/ is in your deployment"
    exit 1
fi

# Run ingestion
echo ""
echo "🚀 Running ingestion script..."
echo "⏱️  This will take several minutes..."
python scripts/ingest_all_articles.py

echo ""
echo "✅ Reingestion complete!"
echo "🔍 Test the API to verify both sources are available"
