# Care-Beacon Medical RAG System

A production Retrieval-Augmented Generation (RAG) system for answering patient questions about cancer using medical articles from BC Cancer, Canadian Cancer Society, and Cleveland Clinic. Provides accurate, cited answers with paragraph-level references.

## Project Status

**Current Version**: 3.0.0 - **Live in Production** (Vercel)

### Architecture

- **Phase 1: Foundation** - Complete
  - Markdown parser with YAML frontmatter
  - Document chunking and embeddings
  - Data models and storage layer

- **Phase 2: Core RAG System** - Complete
  - Vector database integration (Qdrant Cloud)
  - Retrieval engine with semantic search
  - LLM integration (OpenAI GPT-4o-mini)
  - Answer generation with citations
  - Redis caching layer (Upstash, via Vercel Marketplace)

- **Phase 3: Production Deployment** - Complete
  - Deployed on Vercel as two Services (`api` + `web`) behind one route table
  - FastAPI REST API with OpenAPI docs
  - Source filtering (BC Cancer / Canadian Cancer Society / Cleveland Clinic)
  - Rate limiting via Vercel WAF, error handling
  - Modern FastAPI lifespan pattern, Pydantic v2 compliant

### Quality Metrics

| Metric | Status |
|--------|--------|
| **Test Suite** | 239 passing, 6 pre-existing failures (see `api/tests/`) |
| **API Documentation** | Comprehensive with examples |
| **Performance** | Real-time monitoring, < 2s average response time |

The 6 failing tests predate this deployment migration and are tracked separately;
none touch the RAG pipeline's production behavior. Run `make test` for the current
state on your machine.

## Documentation

Comprehensive documentation is available:

- **[API Documentation](docs/API.md)** - Complete REST API reference with examples
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - Setup, testing, and development workflow
- **[Usage Examples](docs/USAGE_EXAMPLES.md)** - Tutorials and integration patterns
- **[Performance Optimization](docs/PERFORMANCE_OPTIMIZATION.md)** - Monitoring, benchmarking, and optimization guide
- **[Architecture](docs/ARCHITECTURE.md)** - System design and component overview
- **[Interactive API Docs](https://care-beacon-health.vercel.app/api/docs)** - Swagger UI
- **[Project Plan](Claude.md)** - Original requirements and design decisions

## Features

- **Intelligent Question Answering** - AI-powered responses with paragraph-level citations
- **Multi-Source Support** - BC Cancer, Canadian Cancer Society, and Cleveland Clinic content
- **Source Filtering** - Filter by cancer type or information source
- **Smart Caching** - Redis (Upstash) caching to reduce repeated LLM/embedding costs
- **Vector Search** - Semantic similarity using OpenAI embeddings and Qdrant Cloud
- **Citation Transparency** - Every claim linked to original source paragraph
- **Performance Monitoring** - Real-time metrics, benchmarking, and profiling tools
- **REST API** - Modern FastAPI with OpenAPI documentation
- **Vercel Native** - Two Services (`api` + `web`) behind one route table, one domain

## Project Structure

```
care-beacon/
├── api/                      # FastAPI service (Vercel Service: api)
│   ├── src/
│   │   ├── ingestion/       # Article parsing and ingestion
│   │   ├── embeddings/      # Embedding generation and chunking
│   │   ├── storage/         # Vector DB (Qdrant) and cache (Redis)
│   │   ├── retrieval/       # Search and retrieval
│   │   ├── generation/      # LLM integration and prompts
│   │   ├── caching/         # Query result caching
│   │   └── api/             # REST API endpoints (FastAPI app)
│   ├── tests/                # Test suite
│   ├── scripts/              # Ingestion entrypoint (local only)
│   ├── config/                # config.yaml, prompts.yaml
│   └── requirements.txt       # Runtime deps only (8 packages)
├── web-client/                # Next.js frontend (Vercel Service: web)
├── scraped_data/               # Source markdown articles (never bundled into api/)
├── evaluation/                 # Test questions and evaluation
├── docs/                       # Documentation
├── vercel.json                  # Service routing table
└── .vercelignore                 # Filesystem upload exclusions (load-bearing, see Deployment)
```

## Installation

### Prerequisites

- **Python 3.10.19** (via Conda) - for local API development and tests; Vercel itself runs the `api` service on Python 3.12
- Node.js - for `web-client` (Next.js 16)
- [Vercel CLI](https://vercel.com/docs/cli) - for `vercel dev` and deployments
- OpenAI API key (embeddings + LLM)
- Qdrant Cloud instance (vector database)

### Step 1: Clone and Set Up the Python Environment

```bash
cd /Users/kamlau/Projects/Care-Beacon

conda create -n care-beacon python=3.10.19 -y
conda activate care-beacon
python -m pip install -r api/requirements.txt -r api/requirements-dev.txt
```

### Step 2: Configure Environment Variables

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY, ADMIN_API_KEY
```

`REDIS_URL` is injected automatically by the Upstash Redis Marketplace integration
when running on Vercel; for local work, pull it with `vercel env pull`.

### Step 3: Verify Installation

```bash
make test
```

See [Deployment](#deployment) below for how the app runs in production, and
`docs/DEVELOPER_GUIDE.md` for a full local development walkthrough.

## Quick Start

### Production

The app is live at **https://care-beacon-health.vercel.app**.

```bash
# Check health
curl https://care-beacon-health.vercel.app/api/health

# Ask a question
curl -X POST "https://care-beacon-health.vercel.app/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the symptoms of breast cancer?"}'
```

### Local Development

```bash
# Set up environment (see Installation above), then:
vercel dev
```

`vercel dev` runs both Services (`api` and `web`) behind the same route table used
in production, so `/api/*` and everything else resolve exactly as they do live.

## Usage Examples

### Python Client

```python
import requests

# Ask a question
response = requests.post(
    "https://care-beacon-health.vercel.app/api/v1/ask",
    json={
        "question": "What are the symptoms of breast cancer?",
        "cancer_type": "Breast Cancer",
        "source": "BC Cancer"
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Sources: {len(result['sources'])}")
print(f"Cost: ${result['metadata']['cost']:.6f}")
```

### cURL

```bash
# Basic question
curl -X POST "https://care-beacon-health.vercel.app/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is chemotherapy?",
    "max_results": 5
  }'

# With filters
curl -X POST "https://care-beacon-health.vercel.app/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are treatment options?",
    "cancer_type": "Lung Cancer",
    "source": "BC Cancer"
  }'

# Get statistics
curl "https://care-beacon-health.vercel.app/api/v1/stats"
```

For more examples, see [Usage Examples](docs/USAGE_EXAMPLES.md).

## Testing

```bash
export PY=/opt/anaconda3/envs/care-beacon/bin/python

# Run all tests
cd api && $PY -m pytest tests/ -q --continue-on-collection-errors

# Run a specific test file
cd api && $PY -m pytest tests/test_api.py -v

# Run with coverage
cd api && $PY -m pytest tests/ --cov=src --cov-report=term-missing
```

A bare `pytest` may resolve to a different interpreter (e.g. an Anaconda base
environment) and fail; use the `care-beacon` conda env's Python explicitly, or
`make test`, which does this for you.

**Current state**: 239 passed, 6 pre-existing failures unrelated to the Vercel
migration. There is no coverage or pass-rate guarantee implied here — check
`api/tests/` and CI output for the current numbers.

## Deployment

One Vercel project (`care-beacon-health`), two Services, one domain:

| Service | Root | Framework | Public paths |
|---------|------|-----------|--------------|
| `web`   | `web-client/` | Next.js 16 | everything not under `/api/` |
| `api`   | `api/`        | FastAPI, Python 3.12 | `/api/*` |

Routing is defined in `vercel.json`. The `/api/(.*)` rewrite must stay ahead of the
`/(.*)` catch-all, because rewrites are evaluated in order and routing into a service
is final.

**Environment variables:** `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`,
`ADMIN_API_KEY`, `VECTOR_DB_PROVIDER=qdrant`. `REDIS_URL` is injected automatically
by the Upstash Redis Marketplace integration.

**Local development:** `vercel dev` runs both services behind the same route table as
production. `make test` runs the Python suite.

**Ingestion is local-only:** `make ingest`. It reads `scraped_data/` — which lives
outside `api/` and is never bundled into the function — and upserts into Qdrant Cloud.

**Rate limiting** is enforced by the Vercel WAF, not application code: a custom rule
(`ask-rate-limit`) allows 60 requests per 60 seconds per IP on `/api/v1/ask` and
returns 429 past that, configured via `vercel firewall rules`.

**The upload, not just the deploy, is filesystem-based:** `vercel deploy` uploads
from disk, not from git, so `.gitignore` has no effect on it. `.vercelignore` keeps
`scraped_data/` (25,000+ files) and other local-only content out of the upload —
without it, the upload exceeds Vercel's 15,000-file limit. Do not delete it.

**Admin route** is protected by Vercel Deployment Protection (dashboard-configured,
not in code), so the browser never needs to hold the admin key.

## Configuration

Main configuration is in `api/config/config.yaml`. Key settings:

- **Embeddings**: Model, batch size, dimensions
- **Vector DB**: Qdrant collection name, distance metric
- **Retrieval**: Top-k results, similarity threshold
- **LLM**: Model selection, temperature, max tokens
- **Cache**: Redis settings, TTL
- **Costs**: API cost tracking

## Keepalive

Qdrant Cloud reclaims idle free-tier clusters after roughly a week of inactivity.
A Vercel cron job issues a daily GET to `/api/health`, which performs a real Qdrant
collection read — so a 200 proves the cluster answered, not merely that the function
booted.

It is configured in `vercel.json` and needs no secrets, no repository variables and
no external service:

```json
"crons": [{ "path": "/api/health", "schedule": "0 9 * * *" }]
```

**Three things to know:**

1. **The schedule is UTC**, always. `0 9 * * *` is 09:00 UTC.
2. **Hobby runs cron once per day, with up to 59 minutes of jitter.** That is ample
   here — Qdrant's idle threshold is about a week, so a daily ping has six days of
   margin. Per-minute scheduling would require Pro.
3. **Cron requests are identifiable**: Vercel sends them with the user agent
   `vercel-cron/1.0` and an `x-vercel-cron-schedule` header.

Check runs under Project → Cron Jobs in the Vercel dashboard, or with
`vercel crons ls`.

A GitHub Actions workflow was used for this originally. It was replaced because
this repository is private, so Actions runs consume the account's minutes quota —
and when that quota is exhausted, jobs sit queued forever with no runner assigned
and no error. A keepalive whose own failure mode is silent is worse than none.


## Data Source

- **Sources**: BC Cancer (bccancer.bc.ca), Canadian Cancer Society, Cleveland Clinic
- **Topics**: Various cancer types (breast, lung, digestive, etc.)
- **Format**: Markdown with YAML frontmatter
- **Location**: `scraped_data/`

## Development

### Daily Development Workflow

```bash
# 1. Activate conda environment
conda activate care-beacon

# 2. Run both services locally
vercel dev

# 3. Run tests or develop
make test
```

### Makefile Commands

```bash
make test               # Run all tests
make test-cov           # Run tests with coverage
make lint                # Run linting (flake8 + mypy)
make format             # Format code with Black
make check               # Run tests + linting
make dev                 # Run both services via vercel dev
make ingest               # Run article ingestion (local only)
make clean-cache        # Clear Python cache
make clean-logs          # Clear log files
make help                 # Show all commands
```

### Code Formatting

```bash
cd api
black src/ tests/
flake8 src/ tests/
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

## License

[Add your license here]

## Contact

[Add your contact information here]

---

**Last Updated**: 2026-08-05
**Version**: 3.0.0 (Live in production on Vercel)
