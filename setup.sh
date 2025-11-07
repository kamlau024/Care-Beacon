#!/bin/bash
# Setup script for Care-Beacon Medical RAG System

set -e  # Exit on error

echo "================================================"
echo "Care-Beacon Medical RAG System - Setup"
echo "================================================"
echo ""

# Check if conda is installed
echo "Checking for conda installation..."
if ! command -v conda &> /dev/null; then
    echo "❌ conda not found. Please install Anaconda or Miniconda:"
    echo "   https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi
echo "✅ conda is installed"

# Environment name
ENV_NAME="care-beacon"

# Check if conda environment already exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "✅ Conda environment '$ENV_NAME' already exists"
    echo ""
    read -p "Do you want to remove and recreate it? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing environment..."
        conda env remove -n $ENV_NAME -y
        echo "✅ Environment removed"
    else
        echo "Using existing environment..."
    fi
fi

# Create conda environment if it doesn't exist
if ! conda env list | grep -q "^${ENV_NAME} "; then
    echo ""
    echo "Creating conda environment '$ENV_NAME' with Python 3.10..."
    conda create -n $ENV_NAME python=3.10 -y
    echo "✅ Conda environment created"
fi

# Activate conda environment
echo ""
echo "Activating conda environment..."
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "✅ Python $python_version activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo "⚠️  Please edit .env and add your API keys!"
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo ""
echo "Creating data directories..."
mkdir -p data/vector_db
mkdir -p data/cache
mkdir -p logs
mkdir -p evaluation/results
echo "✅ Directories created"

# Check if Redis is installed
echo ""
echo "Checking Redis installation..."
if command -v redis-cli &> /dev/null; then
    echo "✅ Redis is installed"

    # Try to ping Redis
    if redis-cli ping &> /dev/null; then
        echo "✅ Redis is running"
    else
        echo "⚠️  Redis is installed but not running"
        echo "   Start Redis with: brew services start redis (Mac)"
        echo "   Or: docker run -d -p 6379:6379 redis:alpine"
    fi
else
    echo "⚠️  Redis not found"
    echo "   Install with: brew install redis (Mac)"
    echo "   Or use Docker: docker run -d -p 6379:6379 redis:alpine"
    echo "   Or disable caching in config/config.yaml"
fi

# Run tests
echo ""
echo "Running configuration tests..."
pytest tests/test_config.py -v

echo ""
echo "================================================"
echo "✅ Setup complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API keys"
echo "2. Ensure Redis is running (or disable caching)"
echo "3. Activate environment: conda activate care-beacon"
echo "4. Proceed to Checkpoint 1.2 (Markdown Parser)"
echo ""
echo "To deactivate: conda deactivate"
echo "For more information, see README.md"
echo ""
