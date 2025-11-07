# Care-Beacon Medical RAG System

A Retrieval-Augmented Generation (RAG) system for answering patient questions about cancer using medical articles from BC Cancer. Provides accurate, cited answers with paragraph-level references.

## Project Status

**Current Phase**: Phase 1 - Foundation ✅ Checkpoint 1.1 Complete

**Completed**:
- ✅ Project structure setup
- ✅ Dependencies configured
- ✅ Configuration management
- ✅ Data models defined

**Next Steps**: Checkpoint 1.2 - Markdown Parser

## Features

- Parse medical articles from markdown with YAML frontmatter
- Generate embeddings using OpenAI API
- Store and search using Chroma vector database
- Answer patient questions with cited sources
- Paragraph-level citations for transparency
- Redis caching for cost optimization
- REST API for query access

## Project Structure

```
care-beacon/
├── src/                      # Source code
│   ├── ingestion/           # Article parsing and ingestion
│   ├── embeddings/          # Embedding generation and chunking
│   ├── storage/             # Vector DB and cache
│   ├── retrieval/           # Search and retrieval
│   ├── generation/          # LLM integration and prompts
│   └── api/                 # REST API endpoints
├── tests/                    # Test suite
├── scraped_data/            # Source markdown articles (94 files)
├── config/                  # Configuration files
│   ├── config.yaml         # Main configuration
│   └── prompts.yaml        # LLM prompts (coming soon)
├── data/                    # Generated data
│   ├── vector_db/          # Chroma database
│   └── cache/              # Redis cache
├── evaluation/             # Test questions and evaluation
├── notebooks/              # Jupyter notebooks for exploration
└── docs/                   # Documentation
```

## Installation

### Prerequisites

- Conda (Anaconda or Miniconda)
- Redis (for caching)
- OpenAI API key (for embeddings)
- Anthropic API key (optional, for Claude LLM)

### Step 1: Clone and Setup Environment

**Option A: Automated Setup (Recommended)**
```bash
# Navigate to project directory
cd /Users/kamlau/Projects/Care-Beacon

# Run setup script
./setup.sh
```

**Option B: Manual Setup**
```bash
# Navigate to project directory
cd /Users/kamlau/Projects/Care-Beacon

# Create conda environment
conda create -n care-beacon python=3.10 -y

# Activate conda environment
conda activate care-beacon

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure API Keys

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API keys
# OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Step 3: Start Docker Infrastructure

**Start Redis with Docker Compose (Recommended)**
```bash
# Start Redis cache
make docker-up

# Or with Docker Compose directly
docker-compose up -d

# Verify it's running
docker-compose ps
```

**Start with Debug Tools**
```bash
# Start Redis + Redis Commander web UI
make docker-up-debug

# Access Redis Commander at: http://localhost:8081
```

**Alternative: Skip caching**
- Edit `config/config.yaml` and set `cache.enabled: false`

See `docs/docker.md` for detailed Docker infrastructure guide.

### Step 4: Verify Installation

```bash
# Run configuration tests
pytest tests/test_config.py -v

# Should see all tests pass ✅
```

## Quick Start

### Phase 1: Data Ingestion (Coming Soon)

```bash
# Parse and chunk all articles
python scripts/ingest_all_articles.py

# This will:
# - Parse 94 markdown articles
# - Create ~2,000-5,000 text chunks
# - Generate embeddings ($1-2 cost)
# - Store in Chroma vector database
```

### Phase 2: Query System (Coming Soon)

```bash
# Start the API server
uvicorn src.api.main:app --reload

# Query from command line
python scripts/test_query.py "What are the symptoms of breast cancer?"

# Query via API
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the symptoms of breast cancer?"}'
```

## Configuration

Main configuration is in `config/config.yaml`. Key settings:

- **Embeddings**: Model, batch size, dimensions
- **Vector DB**: Collection name, persistence location
- **Retrieval**: Top-k results, similarity threshold
- **LLM**: Model selection, temperature, max tokens
- **Cache**: Redis settings, TTL
- **Costs**: API cost tracking

## Data Source

- **Source**: BC Cancer (bccancer.bc.ca)
- **Articles**: 94 patient education articles
- **Topics**: Various cancer types (breast, lung, digestive, etc.)
- **Format**: Markdown with YAML frontmatter
- **Location**: `scraped_data/articles/`

## Development

### Daily Development Workflow

```bash
# 1. Start Docker infrastructure
make docker-up

# 2. Activate conda environment
conda activate care-beacon

# 3. Run tests or develop
make test
# ... your development work ...

# 4. Stop infrastructure when done
make docker-down
```

### Makefile Commands

```bash
# Infrastructure
make docker-up          # Start Redis
make docker-up-debug    # Start Redis + Redis Commander UI
make docker-down        # Stop infrastructure
make docker-logs        # View logs
make docker-status      # Check status
make docker-clean       # Remove all data

# Testing
make test               # Run all tests
make test-cov          # Run tests with coverage
make test-config       # Run config tests only

# Code Quality
make format            # Format code with Black
make lint              # Run linting
make check             # Run tests + linting

# Utilities
make clean-cache       # Clear Python cache
make clean-logs        # Clear log files
make help              # Show all commands
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_config.py -v

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Formatting

```bash
# Format code with Black
black src/ tests/

# Check code style
flake8 src/ tests/

# Type checking
mypy src/
```

## Cost Estimates

Based on 1 query/second (~2.6M queries/month):

### Embeddings
- **One-time indexing**: ~$1-2 (for 10K articles)
- **Query embedding**: ~$3/month (negligible)

### LLM API (per month)
- **Claude 3.5 Sonnet**: ~$35,000/month
- **Claude 3 Haiku**: ~$3,400/month (recommended)
- **GPT-4o-mini**: ~$2,100/month

### With 40% Cache Hit Rate
- **Claude Haiku**: ~$2,000/month
- **GPT-4o-mini**: ~$1,400/month

## Documentation

- `Claude.md` - Overall project guidance and architecture
- `IMPLEMENTATION_PLAN.md` - Detailed implementation checkpoints
- `docs/api_documentation.md` - API endpoints (coming soon)
- `docs/deployment.md` - Deployment guide (coming soon)

## License

[Add your license here]

## Contact

[Add your contact information here]

---

**Last Updated**: 2025-11-07
**Version**: 0.1.0 (Phase 1 - Checkpoint 1.1)
