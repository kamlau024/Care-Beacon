#!/bin/bash
# Render.com build script for Care-Beacon API

set -e  # Exit on error

echo "🔨 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Dependencies installed"

# Check if vector database already exists
if [ ! -f "data/vector_db/chroma.sqlite3" ]; then
    echo "📦 Vector database not found."

    # Check if source articles exist
    if [ -d "scraped_data/articles" ] && [ "$(ls -A scraped_data/articles/*.md 2>/dev/null)" ]; then
        echo "📄 Source articles found. Running ingestion..."
        echo "⚠️  This will take several minutes on first deployment."

        # Create data directory if it doesn't exist
        mkdir -p data/vector_db

        # Run ingestion script
        python scripts/ingest_all_articles.py

        echo "✅ Vector database initialized"
    else
        echo "⚠️  No source articles found in scraped_data/articles/"
        echo "⚠️  Vector database will need to be manually uploaded to persistent disk"
        echo "ℹ️  To upload: Use Render dashboard > Your service > Shell > Upload data/vector_db/"
        echo "ℹ️  Or include scraped_data/ in your git repository for automatic ingestion"

        # Create empty directory to prevent errors
        mkdir -p data/vector_db

        echo "⚠️  Continuing build without vector database..."
    fi
else
    echo "✅ Vector database already exists, skipping ingestion"
fi

echo "🚀 Build complete!"
