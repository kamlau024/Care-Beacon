# Environment Troubleshooting Guide

## Python Version Requirement

**IMPORTANT**: This project uses **Python 3.10.19** consistently.

### Why Python 3.10.19?

- ✅ Stable and well-supported (LTS until October 2026)
- ✅ Compatible with all our dependencies
- ✅ Avoids database schema incompatibility issues between versions
- ✅ Ensures consistent behavior across development and testing

### Verify Your Python Version

```bash
# Activate the care-beacon environment
conda activate care-beacon

# Check Python version (should show 3.10.19)
python --version

# Check Python executable location
which python
# Expected: /opt/anaconda3/envs/care-beacon/bin/python
```

### If You Have the Wrong Version

If you see a different Python version (e.g., 3.13.5 from base anaconda):

```bash
# 1. Deactivate any active environments
conda deactivate

# 2. Remove the care-beacon environment
conda env remove -n care-beacon

# 3. Recreate with Python 3.10.19
conda create -n care-beacon python=3.10.19 -y

# 4. Activate the environment
conda activate care-beacon

# 5. Verify version
python --version
# Should show: Python 3.10.19

# 6. Install dependencies
python -m pip install -r requirements.txt
```

### Common Issue: Multiple Python Versions

**Problem**: You have Python 3.13.5 (base) and Python 3.10.19 (care-beacon), and they create incompatible databases.

**Symptoms**:
- `sqlite3.OperationalError: no such column: collections.topic`
- Database created with one version can't be read by another
- Tests pass with one Python but fail with another

**Solution**:
1. Always use the care-beacon environment: `conda activate care-beacon`
2. If switching environments, delete and recreate the database:
   ```bash
   rm -rf data/vector_db
   ```
3. Run all commands with the care-beacon Python:
   ```bash
   # Explicit path (always works)
   /opt/anaconda3/envs/care-beacon/bin/python scripts/test_vector_db.py

   # Or ensure environment is activated first
   conda activate care-beacon
   python scripts/test_vector_db.py
   ```

## Problem: pip installs to wrong location

### Symptoms
When you run `pip install package`, you see:
```
Requirement already satisfied: package in /opt/homebrew/lib/python3.11/site-packages
```

But you're in a conda environment with Python at:
```
/opt/anaconda3/envs/care-beacon/bin/python
```

### Root Cause

You have multiple Python installations on your system:
1. **Homebrew Python**: `/opt/homebrew/bin/python3` (installed via `brew install python`)
2. **Conda Base**: `/opt/anaconda3/bin/python`
3. **Conda Environment**: `/opt/anaconda3/envs/care-beacon/bin/python`

The issue occurs when your shell's `PATH` has Homebrew's bin directory before conda's, or when `pip` isn't properly aliased when activating the conda environment.

### Diagnosis Commands

Run these to see what's happening:

```bash
# Activate your environment
conda activate care-beacon

# Check Python location (should show conda env)
which python
# Expected: /opt/anaconda3/envs/care-beacon/bin/python

# Check pip location (should also show conda env)
which pip
# Expected: /opt/anaconda3/envs/care-beacon/bin/pip
# Problem: Shows /opt/homebrew/bin/pip or /opt/anaconda3/bin/pip

# Check your PATH
echo $PATH
# Look for the order of directories

# Verify what pip python is using
pip --version
# Should show: pip X.X.X from /opt/anaconda3/envs/care-beacon/lib/pythonX.X/site-packages

# Check what python -m pip uses
python -m pip --version
# Should show: pip X.X.X from /opt/anaconda3/envs/care-beacon/lib/pythonX.X/site-packages
```

### Solution 1: Always use `python -m pip` (Recommended)

This guarantees you're using the pip that belongs to the active Python:

```bash
# Instead of:
pip install package

# Use:
python -m pip install package
```

**Why this works:** `python -m pip` runs pip as a Python module using the currently active Python interpreter, guaranteeing consistency.

### Solution 2: Fix conda activation (Permanent Fix)

#### Step 1: Reinitialize conda

```bash
# For bash
conda init bash
source ~/.bashrc

# For zsh (if using zsh)
conda init zsh
source ~/.zshrc
```

#### Step 2: Check conda configuration

```bash
conda config --show
```

Look for `auto_activate_base`. If it's true, conda might be interfering.

#### Step 3: Update your shell configuration

Add this to your `~/.bashrc` or `~/.zshrc`:

```bash
# >>> conda initialize >>>
# This should already exist from conda init
# Make sure it's at the TOP of your file, before Homebrew paths

# If you have Homebrew, make sure conda comes BEFORE it
# export PATH="/opt/homebrew/bin:$PATH"  # <-- This line should come AFTER conda init
```

#### Step 4: Verify pip is in the environment

```bash
conda activate care-beacon

# List all pip commands in PATH
type -a pip

# Should show conda env pip first:
# pip is /opt/anaconda3/envs/care-beacon/bin/pip
# pip is /opt/homebrew/bin/pip  (this is okay as second)
```

### Solution 3: Create alias (Quick Fix)

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Ensure pip always uses the right Python
alias pip='python -m pip'
```

Then:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

### Solution 4: Reinstall pip in conda environment

If pip is missing from your conda environment:

```bash
conda activate care-beacon
conda install pip
```

### Prevention: Best Practices

1. **Always use `python -m pip`** when installing packages in conda environments
2. **Don't mix conda and system Python** for the same project
3. **Use conda to install packages first**, fall back to pip only if needed:
   ```bash
   conda install package  # Try this first
   python -m pip install package  # If not available in conda
   ```

4. **Create environment-specific requirements**:
   ```bash
   # Export current environment
   pip freeze > requirements.txt

   # Or use conda
   conda env export > environment.yml
   ```

## Updated Installation Instructions

### For New Users

When setting up the project, use these commands:

```bash
# 1. Create conda environment with Python 3.10.19
conda create -n care-beacon python=3.10.19 -y

# 2. Activate environment
conda activate care-beacon

# 3. Verify Python version (MUST be 3.10.19)
python --version
# Expected: Python 3.10.19

# 4. Verify Python location
which python
# Must show: /opt/anaconda3/envs/care-beacon/bin/python

# 5. Install pip if needed
conda install pip -y

# 6. Install requirements using python -m pip
python -m pip install -r requirements.txt

# 7. Verify installation
python -c "import frontmatter; print('Success!')"

# 8. Run tests
python scripts/test_parser.py
```

### For Existing Environments

If you're having issues with an existing environment:

```bash
# 1. Deactivate and remove
conda deactivate
conda env remove -n care-beacon

# 2. Recreate with Python 3.10.19
conda create -n care-beacon python=3.10.19 -y
conda activate care-beacon

# 3. Verify Python version
python --version
# Expected: Python 3.10.19

# 4. Install dependencies
python -m pip install -r requirements.txt

# 5. Clean any old databases (to avoid version conflicts)
rm -rf data/vector_db

# 6. Test
python scripts/test_parser.py
```

## Quick Diagnostic Script

Save this as `check_env.sh`:

```bash
#!/bin/bash
echo "Python location:"
which python

echo ""
echo "Pip location:"
which pip

echo ""
echo "Python version:"
python --version

echo ""
echo "Pip version:"
pip --version

echo ""
echo "Python -m pip version:"
python -m pip --version

echo ""
echo "All pip locations in PATH:"
type -a pip

echo ""
echo "Conda environment:"
conda env list | grep "*"
```

Run it:
```bash
chmod +x check_env.sh
./check_env.sh
```

## Summary

**Problem:** Multiple Python installations (Homebrew + Conda) cause `pip` to install to the wrong location.

**Quick Fix:** Always use `python -m pip install` instead of `pip install`

**Permanent Fix:**
1. Run `conda init bash` (or zsh)
2. Ensure conda initialization is at the top of your shell config
3. Add `alias pip='python -m pip'` to your shell config

---

**Last Updated**: 2025-11-07
