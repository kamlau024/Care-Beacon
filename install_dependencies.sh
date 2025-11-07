#!/bin/bash
# Install dependencies in care-beacon conda environment

echo "Installing dependencies in care-beacon environment..."
echo ""

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ conda not found. Please ensure conda is installed."
    exit 1
fi

# Activate conda environment
eval "$(conda shell.bash hook)"
conda activate care-beacon

# Check Python location
echo "Python location:"
which python
echo ""

# Install python-frontmatter
echo "Installing python-frontmatter..."
pip install python-frontmatter

echo ""
echo "✅ Installation complete!"
echo ""
echo "To verify, run:"
echo "  conda activate care-beacon"
echo "  python scripts/test_parser.py"
