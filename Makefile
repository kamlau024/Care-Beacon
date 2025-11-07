# Care-Beacon Development Makefile
.PHONY: help setup docker-up docker-down docker-logs docker-clean test lint format

help:  ## Show this help message
	@echo "Care-Beacon Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Environment Setup
setup:  ## Run initial setup (create conda env and install dependencies)
	./setup.sh

env-activate:  ## Show command to activate conda environment
	@echo "Run: conda activate care-beacon"

# Docker Infrastructure
docker-up:  ## Start Docker infrastructure (Redis)
	docker-compose up -d
	@echo "✅ Infrastructure started!"
	@echo "Redis: localhost:6379"
	@echo "Redis Commander (debug UI): http://localhost:8081"

docker-up-debug:  ## Start Docker infrastructure with debug tools (Redis Commander)
	docker-compose --profile debug up -d
	@echo "✅ Infrastructure started with debug tools!"
	@echo "Redis: localhost:6379"
	@echo "Redis Commander UI: http://localhost:8081"

docker-down:  ## Stop Docker infrastructure
	docker-compose down
	@echo "✅ Infrastructure stopped"

docker-logs:  ## View Docker logs
	docker-compose logs -f

docker-status:  ## Check Docker container status
	docker-compose ps

docker-clean:  ## Stop and remove all containers, volumes, and networks
	docker-compose down -v
	@echo "✅ All containers, volumes, and networks removed"

docker-restart:  ## Restart Docker infrastructure
	docker-compose restart

# Testing
test:  ## Run all tests
	pytest -v

test-cov:  ## Run tests with coverage report
	pytest --cov=src --cov-report=html --cov-report=term
	@echo "Coverage report: htmlcov/index.html"

test-config:  ## Run configuration tests only
	pytest tests/test_config.py -v

test-parser:  ## Run parser tests only (when available)
	pytest tests/test_parser.py -v

# Code Quality
lint:  ## Run code linting
	flake8 src/ tests/
	mypy src/

format:  ## Format code with black
	black src/ tests/

format-check:  ## Check code formatting without making changes
	black --check src/ tests/

# Data Ingestion (Phase 1)
ingest:  ## Run article ingestion pipeline (coming soon)
	@echo "Not implemented yet - Checkpoint 1.6"
	# python scripts/ingest_all_articles.py

# API Server (Phase 2)
api-dev:  ## Start API server in development mode (coming soon)
	@echo "Not implemented yet - Phase 2"
	# uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

api-prod:  ## Start API server in production mode (coming soon)
	@echo "Not implemented yet - Phase 2"
	# uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Utilities
clean-cache:  ## Clear Python cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

clean-logs:  ## Clear log files
	rm -rf logs/*.log
	@echo "✅ Log files cleared"

clean-all: clean-cache clean-logs docker-clean  ## Clean everything
	@echo "✅ All cleaned"

# Development Workflow
dev-start: docker-up  ## Start development environment
	@echo ""
	@echo "Development environment ready!"
	@echo "Next steps:"
	@echo "  1. conda activate care-beacon"
	@echo "  2. Start coding!"

dev-stop: docker-down  ## Stop development environment
	@echo "✅ Development environment stopped"

# Quick checks
check: test lint  ## Run tests and linting
	@echo "✅ All checks passed!"
