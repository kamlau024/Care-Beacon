#!/bin/bash
# Fix conda environment and install all dependencies properly

echo "================================================"
echo "Fixing care-beacon conda environment"
echo "================================================"
echo ""

# Initialize conda for bash
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [ -f "/opt/anaconda3/etc/profile.d/conda.sh" ]; then
    source "/opt/anaconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
else
    echo "❌ Could not find conda installation"
    echo "Please run: conda init bash"
    exit 1
fi

# Activate environment
echo "Activating care-beacon environment..."
conda activate care-beacon

# Verify which Python we're using
echo ""
echo "Checking Python location..."
which python
python --version
echo ""

# Reinstall all requirements
echo "Installing all dependencies from requirements.txt..."
pip install --force-reinstall python-frontmatter
pip install -r requirements.txt

echo ""
echo "================================================"
echo "Verifying installation..."
echo "================================================"
python -c "import frontmatter; print('✅ frontmatter imported successfully!')"

echo ""
echo "================================================"
echo "Running parser test..."
echo "================================================"
python scripts/test_parser.py

echo ""
echo "✅ Done!"
