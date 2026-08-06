# Care-Beacon Development Makefile
#
# Layout: two Vercel Services, `api/` (FastAPI, Python) and `web-client/`
# (Next.js). Local dev runs both behind the same route table via `vercel dev`.

PY := /opt/anaconda3/envs/care-beacon/bin/python

.PHONY: help setup env-activate test test-cov lint format dev ingest clean-cache clean-logs clean-all check

help:  ## Show this help message
	@echo "Care-Beacon Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Environment Setup
setup:  ## Run initial setup (create conda env and install dependencies)
	./setup.sh

env-activate:  ## Show command to activate conda environment
	@echo "Run: conda activate care-beacon"

# Testing
test:  ## Run all tests
	cd api && $(PY) -m pytest tests/ -v

test-cov:  ## Run tests with coverage report
	cd api && $(PY) -m pytest tests/ --cov=src --cov-report=html --cov-report=term

# Code Quality
lint:  ## Run code linting
	cd api && flake8 src/ tests/ && mypy src/

format:  ## Format code with black
	cd api && black src/ tests/

format-check:  ## Check code formatting without making changes
	cd api && black --check src/ tests/

# Local Development
dev:  ## Run both services locally via the Vercel route table
	vercel dev

# Data Ingestion (local only)
ingest:  ## Run article ingestion (local only)
	cd api && $(PY) scripts/ingest.py

# Utilities
clean-cache:  ## Clear Python cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

clean-logs:  ## Clear log files
	rm -rf logs/*.log
	@echo "Log files cleared"

clean-all: clean-cache clean-logs  ## Clean everything
	@echo "All cleaned"

# Quick checks
check: test lint  ## Run tests and linting
	@echo "All checks passed!"
