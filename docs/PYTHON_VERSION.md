# Python Version Requirements

## Required Version

**This project requires Python 3.10.19**

## Why Python 3.10.19?

1. **Stability**: Python 3.10 is a mature, stable release with LTS support until October 2026
2. **Compatibility**: All our dependencies (ChromaDB, OpenAI, etc.) are tested and work well with Python 3.10
3. **Consistency**: Using a specific version ensures identical behavior across development, testing, and deployment
4. **Database Compatibility**: ChromaDB creates databases with version-specific schemas that are incompatible across Python versions

## Common Issues

### Problem: Using Wrong Python Version

**Symptoms**:
```bash
sqlite3.OperationalError: no such column: collections.topic
```

**Cause**: ChromaDB database was created with one Python version (e.g., 3.13.5) but accessed with another (e.g., 3.10.19)

**Solution**:
```bash
# 1. Delete the incompatible database
rm -rf data/vector_db

# 2. Ensure you're using Python 3.10.19
conda activate care-beacon
python --version
# Expected: Python 3.10.19

# 3. Recreate the database by running tests
python scripts/test_vector_db.py
```

### Problem: Multiple Python Installations

Many developers have multiple Python installations:
- **Homebrew Python**: `/opt/homebrew/bin/python3` (often 3.11 or 3.12)
- **System Python**: `/usr/bin/python3` (often 3.9)
- **Conda Base**: `/opt/anaconda3/bin/python` (often latest version)
- **Conda Environments**: `/opt/anaconda3/envs/*/bin/python` (environment-specific)

**Solution**: Always activate the care-beacon environment before running any commands:
```bash
conda activate care-beacon
python --version  # Verify it shows 3.10.19
```

## Installation

### New Installation

```bash
# Create environment with Python 3.10.19
conda create -n care-beacon python=3.10.19 -y

# Activate environment
conda activate care-beacon

# Verify version
python --version
# Expected: Python 3.10.19

# Install dependencies
python -m pip install -r requirements.txt
```

### Fixing Existing Installation

If you already have care-beacon but with wrong Python version:

```bash
# Remove existing environment
conda deactivate
conda env remove -n care-beacon

# Recreate with correct version
conda create -n care-beacon python=3.10.19 -y
conda activate care-beacon

# Verify version
python --version

# Reinstall dependencies
python -m pip install -r requirements.txt

# Clean old databases (important!)
rm -rf data/vector_db

# Run tests to verify
python -m pytest tests/test_vector_db.py -v
```

## Verification

### Quick Check

```bash
conda activate care-beacon
python --version
```

Expected output:
```
Python 3.10.19
```

### Full Check

Run the environment check script:

```bash
conda activate care-beacon

echo "Python version:"
python --version

echo ""
echo "Python location:"
which python

echo ""
echo "Expected location:"
echo "/opt/anaconda3/envs/care-beacon/bin/python"

echo ""
echo "Installed packages:"
python -m pip list | grep -E "chroma|openai|pytest"
```

## Development Workflow

### Always Use the Correct Environment

```bash
# Start of each session
conda activate care-beacon

# Verify you're in the right environment
python --version  # Should show 3.10.19

# Run your commands
python scripts/test_vector_db.py
python -m pytest tests/
```

### Running Tests

```bash
# Activate environment first
conda activate care-beacon

# Run tests with environment's Python
python -m pytest tests/test_vector_db.py -v

# Or use explicit path (if environment activation doesn't work)
/opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/test_vector_db.py -v
```

### Installing Packages

```bash
# Activate environment first
conda activate care-beacon

# Use python -m pip to ensure correct pip
python -m pip install package-name

# Verify installation
python -c "import package_name; print('Success!')"
```

## CI/CD and Deployment

When deploying or setting up CI/CD, ensure Python 3.10.19 is used:

### Docker (example)

```dockerfile
FROM python:3.10.19-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "src/api/main.py"]
```

### GitHub Actions (example)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10.19'
      - run: pip install -r requirements.txt
      - run: pytest
```

## FAQ

### Q: Can I use Python 3.11 or 3.12?

**A**: Not recommended. While the code may work, ChromaDB databases created with different Python versions are incompatible, leading to errors.

### Q: What if I see Python 3.13.5 when I check?

**A**: You're likely in the base anaconda environment. Run:
```bash
conda activate care-beacon
python --version  # Should now show 3.10.19
```

### Q: Why not just use the latest Python?

**A**: Latest Python versions can have:
- Breaking changes in dependencies
- Database schema incompatibilities
- Untested edge cases

Python 3.10.19 is stable, well-tested, and has LTS support until 2026.

### Q: I'm getting database errors after switching Python versions

**A**: Delete the database and recreate it:
```bash
rm -rf data/vector_db
python scripts/test_vector_db.py
```

## Summary

✅ **Use**: Python 3.10.19
✅ **Install**: `conda create -n care-beacon python=3.10.19 -y`
✅ **Verify**: `python --version` should show `Python 3.10.19`
✅ **Activate**: Always `conda activate care-beacon` before running commands
❌ **Avoid**: Using different Python versions for the same project
❌ **Avoid**: Mixing base anaconda Python with environment Python

For detailed troubleshooting, see `docs/environment_troubleshooting.md`.

---

**Last Updated**: 2025-11-07
**Maintained By**: Care-Beacon Development Team
