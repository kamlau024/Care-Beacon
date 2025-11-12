#!/bin/bash
# Render.com build script for Care-Beacon API

set -e  # Exit on error

echo "🔨 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Dependencies installed"

# Check if we should force reingest (set FORCE_REINGEST=true in Render environment variables)
FORCE_REINGEST=${FORCE_REINGEST:-false}

# IMPORTANT: On Render, the persistent disk is NOT mounted during the build phase.
# It's only mounted when the container starts. Therefore, we should NOT run ingestion
# during build unless explicitly forced, as it will rebuild the database every deployment.
#
# To rebuild the vector database:
# 1. Set FORCE_REINGEST=true in Render environment variables
# 2. Trigger a new deployment
# 3. Set FORCE_REINGEST back to false after successful ingestion

if [ "$FORCE_REINGEST" = "true" ]; then
    echo "🔄 FORCE_REINGEST is set - will reingest all data"
    echo "⚠️  This will take several minutes and cost ~$1-2 in API calls."

    # Check if source articles exist
    ARTICLES_FOUND=false
    if [ -d "scraped_data/bc-cancer/articles" ] && [ "$(find scraped_data/bc-cancer/articles -name '*.md' -type f | head -1)" ]; then
        ARTICLES_FOUND=true
        echo "📄 BC Cancer articles found"
    fi
    if [ -d "scraped_data/canadian-cancer-society/articles" ] && [ "$(find scraped_data/canadian-cancer-society/articles -name '*.md' -type f | head -1)" ]; then
        ARTICLES_FOUND=true
        echo "📄 Canadian Cancer Society articles found"
    fi

    if [ "$ARTICLES_FOUND" = "true" ]; then
        echo "📄 Running ingestion..."
        echo "⚠️  This will take several minutes."

        # Create data directory if it doesn't exist
        mkdir -p data/vector_db

        # Delete existing database to ensure clean rebuild
        echo "🗑️  Removing existing database..."
        rm -rf data/vector_db/*

        # Run memory-efficient ingestion script (optimized for 512MB free tier)
        python scripts/ingest_all_articles_low_memory.py

        echo "✅ Vector database initialized with multi-source data"
    else
        echo "❌ FORCE_REINGEST is set but no source articles found!"
        echo "⚠️  Checked: scraped_data/bc-cancer/articles and scraped_data/canadian-cancer-society/articles"
        echo "⚠️  Cannot proceed with ingestion."
        exit 1
    fi
else
    echo "ℹ️  Skipping vector database ingestion during build"
    echo "ℹ️  The persistent disk will be used (mounted at /opt/render/project/src/data at runtime)"
    echo "ℹ️  To rebuild the database, set FORCE_REINGEST=true in Render environment variables"

    # Create empty directory structure to prevent errors during build
    mkdir -p data/vector_db
fi

echo "🚀 Build complete!"
