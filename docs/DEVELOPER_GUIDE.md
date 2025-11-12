# Care-Beacon Developer Guide

Complete setup and development guide for the Care-Beacon Medical RAG System.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Development Workflow](#development-workflow)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.10.19 | Runtime environment |
| **Conda** | Latest | Python environment management |
| **Docker** | Latest | Containerization |
| **Docker Compose** | Latest | Multi-container orchestration |
| **Redis** | 7+ | Caching layer |
| **Node.js** | 18+ | Frontend development (optional) |

### API Keys

You'll need the following API keys:

- **OpenAI API Key** - For embeddings and LLM (required)
- **Anthropic API Key** - For Claude LLM (optional)
- **Redis Password** - For production deployments (optional)

---

## Quick Start

### Option 1: Docker (Recommended)

The fastest way to get started:

```bash
# Clone the repository
git clone https://github.com/your-org/care-beacon.git
cd care-beacon

# Copy environment file
cp .env.example .env

# Edit .env and add your API keys
nano .env

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f api

# API will be available at http://localhost:8000
```

**Access Points**:
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- Web UI: http://localhost:3000
- Redis: localhost:6379

### Option 2: Local Development

For active development:

```bash
# Clone the repository
git clone https://github.com/your-org/care-beacon.git
cd care-beacon

# Run setup script
chmod +x setup.sh
./setup.sh

# Activate environment
conda activate care-beacon

# Start Redis (in separate terminal)
redis-server

# Start API
python scripts/start_api.py

# API will be available at http://localhost:8000
```

---

## Development Setup

### 1. Environment Setup

**Create Conda Environment**:
```bash
# Create environment with specific Python version
conda create -n care-beacon python=3.10.19 -y

# Activate environment
conda activate care-beacon

# Verify Python version (MUST be 3.10.19)
python --version
# Output: Python 3.10.19
```

**Why Python 3.10.19?**
- ChromaDB database compatibility
- Specific dependency requirements
- Tested and validated configuration

### 2. Install Dependencies

```bash
# Install all dependencies
python -m pip install -r requirements.txt

# Or install specific groups
python -m pip install -r requirements-dev.txt    # Development tools
python -m pip install -r requirements-test.txt   # Testing tools
```

### 3. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env
```

**Edit `.env`** with your configuration:

```bash
# OpenAI Configuration (REQUIRED)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Anthropic Configuration (OPTIONAL - for Claude)
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=          # Leave empty for local development

# Application Configuration
LOG_LEVEL=INFO
DEBUG=False
```

### 4. Initialize Data

```bash
# Create necessary directories
mkdir -p data/vector_db data/cache

# Run data ingestion (if you have markdown articles)
python scripts/ingest_articles.py

# Or use Docker volume mounts
docker-compose up -d
```

---

## Running the Application

### Development Mode

**Start API Server**:
```bash
# Activate environment
conda activate care-beacon

# Start with hot-reload
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Or use the convenience script
python scripts/start_api.py
```

**Start Web UI** (if available):
```bash
cd web
npm install
npm run dev
```

### Production Mode (Docker)

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Service Management

```bash
# Start specific service
docker-compose up -d api

# Restart a service
docker-compose restart api

# View service status
docker-compose ps

# Execute command in container
docker exec -it care-beacon-api bash

# View real-time logs
docker-compose logs -f api

# Stop all services
docker-compose stop
```

---

## Testing

### Running Tests

**All Tests**:
```bash
# Run full test suite
pytest tests/

# With coverage report
pytest tests/ --cov=src --cov-report=term-missing

# With coverage report (HTML)
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

**Specific Test Files**:
```bash
# Test API endpoints
pytest tests/test_api.py -v

# Test retrieval engine
pytest tests/test_retrieval.py -v

# Test with keyword
pytest tests/ -k "test_ask"
```

**Test in Docker**:
```bash
# Run tests in container
docker exec care-beacon-api pytest tests/ -v

# With coverage
docker exec care-beacon-api pytest tests/ --cov=src --cov-report=term
```

### Current Test Coverage

✅ **100% Code Coverage** - 1217 statements, 0 missing lines

```
Module                              Coverage
------------------------------------------
src/api/main.py                     100%
src/api/models.py                   100%
src/caching/redis_cache.py          100%
src/config_loader.py                100%
src/embeddings/chunking.py          100%
src/embeddings/embedding_generator  100%
src/generation/answer_generator     100%
src/generation/llm_client.py        100%
src/ingestion/markdown_parser.py    100%
src/retrieval/retrieval_engine.py   100%
src/storage/vector_db.py            100%
------------------------------------------
TOTAL                               100%
```

### Writing Tests

**Test Structure**:
```python
"""tests/test_my_feature.py"""
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_component():
    """Create a mock component for testing."""
    component = Mock()
    component.method.return_value = "expected_value"
    return component

def test_feature_success(mock_component):
    """Test feature works correctly."""
    # Arrange
    input_data = {"key": "value"}

    # Act
    result = my_function(input_data, mock_component)

    # Assert
    assert result == "expected_value"
    mock_component.method.assert_called_once()

def test_feature_error_handling():
    """Test feature handles errors correctly."""
    with pytest.raises(ValueError) as exc_info:
        my_function(invalid_input)

    assert "error message" in str(exc_info.value)
```

**Run New Tests**:
```bash
# Run only new test file
pytest tests/test_my_feature.py -v

# Run and update coverage
pytest tests/test_my_feature.py --cov=src/my_module --cov-report=term-missing
```

---

## Development Workflow

### 1. Branch Strategy

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes
git add .
git commit -m "Add my feature"

# Push to remote
git push origin feature/my-feature

# Create pull request on GitHub
```

### 2. Code Style

We use **Black** for formatting and **Ruff** for linting:

```bash
# Format code
black src/ tests/

# Check formatting (without changes)
black src/ tests/ --check

# Lint code
ruff check src/ tests/

# Auto-fix linting issues
ruff check src/ tests/ --fix
```

### 3. Pre-commit Hooks

Install pre-commit hooks to automatically check code:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

**`.pre-commit-config.yaml`**:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

### 4. Commit Messages

Follow conventional commits format:

```bash
# Feature
git commit -m "feat: add source filtering to API"

# Bug fix
git commit -m "fix: resolve cache invalidation issue"

# Documentation
git commit -m "docs: update API documentation"

# Tests
git commit -m "test: add tests for retrieval engine"

# Refactor
git commit -m "refactor: modernize to Pydantic v2"
```

### 5. Pull Request Process

1. **Create branch** from `main`
2. **Make changes** with tests
3. **Run tests** locally: `pytest tests/ --cov=src`
4. **Format code**: `black src/ tests/`
5. **Create PR** with clear description
6. **Address review** comments
7. **Merge** after approval

---

## Architecture

### High-Level Overview

```
┌─────────────────┐
│   Web UI        │
│  (Next.js)      │
└────────┬────────┘
         │
         ↓
┌─────────────────┐      ┌──────────────┐
│   FastAPI       │─────→│    Redis     │
│   REST API      │←─────│    Cache     │
└────────┬────────┘      └──────────────┘
         │
         ↓
┌─────────────────┐
│  Answer Gen     │
│  (RAG Logic)    │
└────────┬────────┘
         │
    ┌────┴────┐
    ↓         ↓
┌─────────┐ ┌─────────┐
│ Chroma  │ │ OpenAI  │
│Vector DB│ │   API   │
└─────────┘ └─────────┘
```

### Component Responsibilities

| Component | Responsibility | Files |
|-----------|---------------|-------|
| **API Layer** | HTTP endpoints, request validation | `src/api/` |
| **Answer Generator** | Orchestrate RAG pipeline | `src/generation/answer_generator.py` |
| **Retrieval Engine** | Search vector database | `src/retrieval/retrieval_engine.py` |
| **LLM Client** | Generate answers with citations | `src/generation/llm_client.py` |
| **Vector DB** | Store and search embeddings | `src/storage/vector_db.py` |
| **Cache Layer** | Cache query results | `src/caching/redis_cache.py` |
| **Ingestion** | Parse and chunk articles | `src/ingestion/` |
| **Embeddings** | Generate vector embeddings | `src/embeddings/` |

### Request Flow

```
1. User submits question via API
   ↓
2. API validates request
   ↓
3. Check Redis cache
   ├─ Cache hit → Return cached result
   ↓
4. Generate query embedding (OpenAI)
   ↓
5. Search vector database (Chroma)
   ↓
6. Retrieve top-k relevant paragraphs
   ↓
7. Generate answer with LLM (OpenAI/Claude)
   ↓
8. Format response with citations
   ↓
9. Cache result in Redis
   ↓
10. Return to user
```

---

## Configuration

### Config Files

**`config/config.yaml`** - Main configuration:
```yaml
# API Configuration
api:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost:3000"
  rate_limit:
    enabled: true
    requests_per_minute: 60

# LLM Configuration
llm:
  provider: "openai"        # or "anthropic"
  model: "gpt-4o-mini"      # or "claude-3-5-sonnet-20241022"
  temperature: 0.1
  max_tokens: 2000

# Embeddings Configuration
embeddings:
  provider: "openai"
  model: "text-embedding-3-small"
  dimensions: 1536
  batch_size: 100

# Vector Database Configuration
vector_db:
  provider: "chroma"
  collection_name: "care-beacon-medical"
  distance_metric: "cosine"
  persist_directory: "data/vector_db"

# Cache Configuration
cache:
  enabled: true
  host: "localhost"
  port: 6379
  db: 0
  ttl: 86400              # 24 hours in seconds

# Retrieval Configuration
retrieval:
  top_k: 10
  min_similarity_threshold: 0.0
  rerank_results: false

# Logging Configuration
logging:
  level: "INFO"           # DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Environment Variables

Environment variables override config file values:

```bash
# Override specific settings
export LOG_LEVEL=DEBUG
export OPENAI_API_KEY=sk-...
export REDIS_HOST=redis.example.com
```

### Loading Configuration

```python
from src.config_loader import get_config

# Get configuration singleton
config = get_config()

# Access values with dot notation
api_port = config.get("api.port")              # 8000
llm_model = config.get("llm.model")            # "gpt-4o-mini"
cache_ttl = config.get("cache.ttl", 3600)      # With default value

# Get API keys
openai_key = config.get_api_key("openai")
anthropic_key = config.get_api_key("anthropic")
```

---

## Troubleshooting

### Common Issues

#### 1. Python Version Mismatch

**Problem**: `ModuleNotFoundError` or database errors
```
Error: incompatible with SQLite version 3.35.0
```

**Solution**: Ensure Python 3.10.19
```bash
python --version  # Must show 3.10.19
conda create -n care-beacon python=3.10.19 -y
conda activate care-beacon
```

#### 2. Redis Connection Error

**Problem**: API can't connect to Redis
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solution**: Start Redis server
```bash
# macOS/Linux
redis-server

# Docker
docker-compose up -d redis

# Check Redis is running
redis-cli ping  # Should return "PONG"
```

#### 3. OpenAI API Key Error

**Problem**: 401 Unauthorized from OpenAI
```
openai.error.AuthenticationError: Invalid API key
```

**Solution**: Check API key configuration
```bash
# Verify .env file has correct key
cat .env | grep OPENAI_API_KEY

# Test API key
python -c "import openai; openai.api_key='your-key'; print('Key valid')"
```

#### 4. Port Already in Use

**Problem**: Can't start API on port 8000
```
OSError: [Errno 48] Address already in use
```

**Solution**: Kill process or use different port
```bash
# Find process using port 8000
lsof -ti:8000

# Kill the process
kill $(lsof -ti:8000)

# Or use different port
uvicorn src.api.main:app --port 8001
```

#### 5. Docker Volume Permission Issues

**Problem**: Permission denied errors in Docker
```
PermissionError: [Errno 13] Permission denied: 'data/vector_db'
```

**Solution**: Fix permissions
```bash
# Fix local directory permissions
chmod -R 755 data/

# Or run container as your user
docker-compose run --user $(id -u):$(id -g) api bash
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
# In config/config.yaml
logging:
  level: "DEBUG"

# Or via environment variable
export LOG_LEVEL=DEBUG
```

View detailed logs:
```bash
# Docker logs
docker-compose logs -f api

# Local logs (if using file logging)
tail -f logs/care-beacon.log
```

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check Redis
docker exec care-beacon-redis redis-cli ping

# Check Chroma database size
docker exec care-beacon-api python -c "
from src.storage.vector_db import VectorDatabase
db = VectorDatabase()
print(f'Total chunks: {db.get_stats()[\"total_chunks\"]}')
"
```

---

## Contributing

### Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/your-username/care-beacon.git
   cd care-beacon
   ```
3. **Set up development environment** (see above)
4. **Create feature branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

### Development Guidelines

1. **Write tests** for new features
2. **Maintain 100% coverage** - All new code must be tested
3. **Follow code style** - Use Black and Ruff
4. **Update documentation** - Keep docs in sync with code
5. **Add type hints** - Use Python type annotations
6. **Write docstrings** - Document all public functions/classes

### Code Review Checklist

- [ ] Tests added and passing
- [ ] Code coverage at 100%
- [ ] Code formatted with Black
- [ ] Linting passes (Ruff)
- [ ] Documentation updated
- [ ] Type hints added
- [ ] Commit messages follow convention
- [ ] PR description is clear

### Running Quality Checks

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/ --fix

# Run tests
pytest tests/ --cov=src --cov-report=term-missing

# Type checking (optional)
mypy src/

# All checks
make check  # If Makefile exists
```

---

## Additional Resources

- **API Documentation**: [docs/API.md](./API.md)
- **Architecture**: [docs/ARCHITECTURE.md](./ARCHITECTURE.md)
- **Project Plan**: [Claude.md](../Claude.md)
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Contact & Support

- **Issues**: [GitHub Issues](https://github.com/your-org/care-beacon/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/care-beacon/discussions)
- **Email**: dev@care-beacon.example.com

---

**Last Updated**: 2024-01-15
**Version**: 2.0.0
