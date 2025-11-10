#!/bin/bash
# Render.com build script for Care-Beacon API

set -e  # Exit on error

echo "🔨 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Dependencies installed"

# Check if we should force reingest (set FORCE_REINGEST=true in Render environment variables)
FORCE_REINGEST=${FORCE_REINGEST:-false}

# Check if source articles exist (check new multi-source structure)
ARTICLES_FOUND=false
if [ -d "scraped_data/bc-cancer/articles" ] && [ "$(find scraped_data/bc-cancer/articles -name '*.md' -type f | head -1)" ]; then
    ARTICLES_FOUND=true
    echo "📄 BC Cancer articles found"
fi
if [ -d "scraped_data/canadian-cancer-society/articles" ] && [ "$(find scraped_data/canadian-cancer-society/articles -name '*.md' -type f | head -1)" ]; then
    ARTICLES_FOUND=true
    echo "📄 Canadian Cancer Society articles found"
fi

# Check if vector database already exists
DB_EXISTS=false
if [ -f "data/vector_db/chroma.sqlite3" ]; then
    DB_EXISTS=true
fi

# Decide whether to run ingestion
SHOULD_INGEST=false

if [ "$FORCE_REINGEST" = "true" ]; then
    echo "🔄 FORCE_REINGEST is set - will reingest all data"
    SHOULD_INGEST=true
elif [ "$DB_EXISTS" = "false" ]; then
    echo "📦 Vector database not found - will create new database"
    SHOULD_INGEST=true
else
    echo "✅ Vector database already exists"
fi

# Run ingestion if needed
if [ "$SHOULD_INGEST" = "true" ]; then
    if [ "$ARTICLES_FOUND" = "true" ]; then
        echo "📄 Running ingestion..."
        echo "⚠️  This will take several minutes."

        # Create data directory if it doesn't exist
        mkdir -p data/vector_db

        # Delete existing database if forcing reingest
        if [ "$FORCE_REINGEST" = "true" ] && [ "$DB_EXISTS" = "true" ]; then
            echo "🗑️  Removing existing database..."
            rm -rf data/vector_db/*
        fi

        # Run ingestion script
        python scripts/ingest_all_articles.py

        echo "✅ Vector database initialized with multi-source data"
    else
        echo "⚠️  No source articles found in scraped_data/"
        echo "⚠️  Checked: scraped_data/bc-cancer/articles and scraped_data/canadian-cancer-society/articles"
        echo "ℹ️  Vector database will need to be manually populated"

        # Create empty directory to prevent errors
        mkdir -p data/vector_db

        echo "⚠️  Continuing build without vector database..."
    fi
else
    echo "ℹ️  Skipping ingestion (set FORCE_REINGEST=true to force reingest)"
fi

echo "🚀 Build complete!"
