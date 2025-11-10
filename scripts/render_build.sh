#!/bin/bash
# Render.com build script for Care-Beacon API

set -e  # Exit on error

echo "🔨 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Dependencies installed"

# Check if vector database already exists
if [ ! -f "data/vector_db/chroma.sqlite3" ]; then
    echo "📦 Vector database not found. Running ingestion..."
    echo "⚠️  This will take several minutes on first deployment."

    # Create data directory if it doesn't exist
    mkdir -p data/vector_db

    # Run ingestion script
    python scripts/ingest_all_articles.py

    echo "✅ Vector database initialized"
else
    echo "✅ Vector database already exists, skipping ingestion"
fi

echo "🚀 Build complete!"
