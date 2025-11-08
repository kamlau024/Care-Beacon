# Docker Deployment Guide

## Architecture Overview

The Care-Beacon system is containerized with the following services:

```
┌─────────────────────────────────────────────────────────────┐
│                  DOCKER ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────┐              │
│  │         care-beacon-api                  │              │
│  │  (FastAPI + All RAG Components)          │              │
│  ├──────────────────────────────────────────┤              │
│  │  • FastAPI REST API (Port 8000)          │              │
│  │  • Answer Generator (RAG coordinator)    │              │
│  │  • Retrieval Engine (vector search)      │              │
│  │  • LLM Client (OpenAI integration)       │              │
│  │  • Cache Layer (Redis client)            │              │
│  │  • ChromaDB (file-based vector DB)       │              │
│  └────────────┬─────────────────────────────┘              │
│               │                                              │
│               │ Connects to                                 │
│               ▼                                              │
│  ┌──────────────────────────────────────────┐              │
│  │       care-beacon-redis                  │              │
│  │  (Redis 7 - Cache Layer)                 │              │
│  ├──────────────────────────────────────────┤              │
│  │  • Port 6379                             │              │
│  │  • Persistent storage (redis_data)       │              │
│  │  • AOF enabled (crash recovery)          │              │
│  └──────────────────────────────────────────┘              │
│                                                              │
│  Optional Services:                                         │
│  ┌──────────────────────────────────────────┐              │
│  │    care-beacon-ingestion (on-demand)     │              │
│  │  • Runs data ingestion pipeline          │              │
│  │  • Populates ChromaDB                    │              │
│  │  • One-time or periodic execution        │              │
│  └──────────────────────────────────────────┘              │
│                                                              │
│  ┌──────────────────────────────────────────┐              │
│  │    redis-commander (debug only)          │              │
│  │  • Web UI for Redis (Port 8081)          │              │
│  │  • Enable with --profile debug           │              │
│  └──────────────────────────────────────────┘              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Architectural Points

### Why ChromaDB is NOT a Separate Service

**ChromaDB is file-based** (uses SQLite + vector files):
- ✅ Runs **inside the API container** as a Python library
- ✅ Data stored in `./data/vector_db/` (mounted volume)
- ✅ No separate server process needed
- ✅ Shared between API and ingestion via volume mount

**Contrast with Redis** (separate service):
- ❌ Redis needs a server process
- ❌ Needs to be shared across multiple API instances
- ❌ Requires network communication

### Component Distribution

| Component | Where It Runs | Type |
|-----------|--------------|------|
| FastAPI | `api` container | Web server (port 8000) |
| Answer Generator | `api` container | Python module |
| Retrieval Engine | `api` container | Python module |
| LLM Client | `api` container | Python module |
| Cache Layer | `api` container | Python module (Redis client) |
| **ChromaDB** | `api` container | **Python library (file-based)** |
| **Redis Server** | `redis` container | **Separate service** |
| Ingestion Pipeline | `ingestion` container | One-time job |

## Prerequisites

1. **Docker & Docker Compose**
   ```bash
   docker --version  # Should be 20.10+
   docker-compose --version  # Should be 1.29+ or 2.0+
   ```

2. **OpenAI API Key**
   ```bash
   export OPENAI_API_KEY='your-key-here'
   # Or create a .env file (see below)
   ```

3. **Disk Space**
   - Minimum: 2GB
   - Recommended: 5GB (for logs, caches, etc.)

## Quick Start

### 1. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# .env
OPENAI_API_KEY=sk-your-actual-openai-key-here
```

### 2. Build and Start Services

```bash
# Build the Docker image
docker-compose build

# Start API + Redis
docker-compose up -d

# View logs
docker-compose logs -f api
```

### 3. Verify Services

```bash
# Check service status
docker-compose ps

# Expected output:
# NAME                    STATUS              PORTS
# care-beacon-api         running (healthy)   0.0.0.0:8000->8000/tcp
# care-beacon-redis       running (healthy)   0.0.0.0:6379->6379/tcp

# Test API
curl http://localhost:8000/health

# Test question answering
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are symptoms of breast cancer?"}'
```

### 4. Access Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Data Ingestion

### Option 1: First Time Setup (If Vector DB is Empty)

If you haven't run the ingestion yet, or don't have the `data/vector_db/` populated:

```bash
# Run ingestion service (one-time)
docker-compose --profile ingest up ingestion

# This will:
# 1. Parse articles from scraped_data/
# 2. Generate embeddings via OpenAI
# 3. Store in ChromaDB (data/vector_db/)
# 4. Exit when complete

# Cost: ~$0.005 (one-time)
# Time: ~5-10 minutes
```

### Option 2: Using Existing Vector DB

If you already have `data/vector_db/` populated from local development:

```bash
# Just start the API - it will use existing data
docker-compose up -d

# The data/ directory is mounted as a volume,
# so your existing ChromaDB data is automatically available
```

### Re-ingesting Data (e.g., After Adding New Articles)

```bash
# Stop API temporarily
docker-compose stop api

# Run ingestion
docker-compose --profile ingest up ingestion

# Restart API
docker-compose start api
```

## Service Management

### Start Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d api

# Start with debug tools (Redis Commander)
docker-compose --profile debug up -d
# Access Redis Commander at http://localhost:8081
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f redis

# Last 100 lines
docker-compose logs --tail=100 api
```

### Stop Services

```bash
# Stop all services (preserves data)
docker-compose stop

# Stop and remove containers (preserves volumes)
docker-compose down

# Stop and remove everything INCLUDING VOLUMES (⚠️ deletes data)
docker-compose down -v
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart api
```

## Scaling

### Running Multiple API Instances

```bash
# Scale API to 3 instances
docker-compose up -d --scale api=3

# You'll need a load balancer (nginx) in front
# See PRODUCTION_DEPLOYMENT.md for details
```

## Monitoring & Debugging

### Health Checks

```bash
# Check if services are healthy
docker-compose ps

# Manual health check
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/stats
```

### Access Container Shell

```bash
# Access API container
docker-compose exec api bash

# Inside container:
ls -la data/vector_db/  # Check ChromaDB files
python scripts/test_answer_generator.py  # Run tests
redis-cli -h redis ping  # Test Redis connection
```

### View Redis Data (Debug Mode)

```bash
# Start with Redis Commander
docker-compose --profile debug up -d

# Access web UI
open http://localhost:8081

# Or use CLI
docker-compose exec redis redis-cli
# > KEYS care_beacon:*
# > GET care_beacon:answer:<hash>
```

## Volumes & Data Persistence

### Volume Mounts

```yaml
# API Service Volumes:
./data:/app/data                    # ChromaDB vector database
./logs:/app/logs                    # Application logs
./scraped_data:/app/scraped_data    # Source articles

# Redis Volume:
redis_data:/data                    # Redis persistent storage (AOF)
```

### Backing Up Data

```bash
# Backup ChromaDB
tar -czf chromadb-backup-$(date +%Y%m%d).tar.gz data/vector_db/

# Backup Redis
docker-compose exec redis redis-cli BGSAVE
docker cp care-beacon-redis:/data/dump.rdb redis-backup-$(date +%Y%m%d).rdb

# Backup both
tar -czf care-beacon-backup-$(date +%Y%m%d).tar.gz data/ logs/
```

### Restoring Data

```bash
# Restore ChromaDB
tar -xzf chromadb-backup-20250115.tar.gz

# Restore Redis
docker-compose stop redis
docker cp redis-backup-20250115.rdb care-beacon-redis:/data/dump.rdb
docker-compose start redis
```

## Environment Configuration

### Required Environment Variables

```bash
OPENAI_API_KEY=sk-...        # Required for embeddings & LLM
```

### Optional Environment Variables

```bash
# Redis Connection (defaults work for docker-compose)
REDIS_HOST=redis             # Default: localhost
REDIS_PORT=6379              # Default: 6379

# API Configuration
API_HOST=0.0.0.0             # Default: 0.0.0.0
API_PORT=8000                # Default: 8000
API_DEBUG=false              # Default: false

# Logging
LOG_LEVEL=INFO               # Default: INFO
```

### Using .env File

Create `.env` in project root:

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
API_DEBUG=false
LOG_LEVEL=INFO
```

Docker Compose automatically loads this file.

## Troubleshooting

### API Won't Start

**Problem**: `care-beacon-api` exits immediately

```bash
# Check logs
docker-compose logs api

# Common issues:
# 1. Missing OPENAI_API_KEY
docker-compose exec api env | grep OPENAI

# 2. Redis not ready
docker-compose ps redis  # Should be "healthy"

# 3. Port 8000 already in use
lsof -i :8000
```

**Solution**:
```bash
# Stop conflicting services
docker-compose down

# Set API key
export OPENAI_API_KEY='your-key'

# Rebuild and restart
docker-compose build
docker-compose up -d
```

### ChromaDB Empty / No Results

**Problem**: API returns "No context found" for all queries

```bash
# Check if vector DB has data
docker-compose exec api ls -la data/vector_db/

# Should see: chroma.sqlite3 and other files
```

**Solution**:
```bash
# Run ingestion
docker-compose --profile ingest up ingestion

# Or copy from local development
cp -r ./data/vector_db/* ./data/vector_db/
docker-compose restart api
```

### Redis Connection Errors

**Problem**: API logs show "Redis connection failed"

```bash
# Check Redis health
docker-compose ps redis

# Test connection from API container
docker-compose exec api redis-cli -h redis ping
```

**Solution**:
```bash
# Restart Redis
docker-compose restart redis

# Check Redis logs
docker-compose logs redis
```

### Out of Memory

**Problem**: Container crashes or OOM errors

```bash
# Check container stats
docker stats

# Increase Docker memory limit (Docker Desktop)
# Settings → Resources → Memory → 4GB+
```

### Slow Performance

**Problem**: API responses are slow

```bash
# Check cache hit rate
curl http://localhost:8000/api/v1/stats | jq '.cache.hit_rate'

# Should be >0.4 (40%)
# If low, cache might not be working

# Check Redis
docker-compose exec redis redis-cli INFO stats
```

## Production Deployment

For production deployment, see:
- **PRODUCTION_DEPLOYMENT.md** - Full production setup
- **ARCHITECTURE.md** - System architecture details

Key production recommendations:
1. Use managed Redis (AWS ElastiCache, etc.)
2. Add nginx as reverse proxy with HTTPS
3. Implement proper authentication
4. Set up monitoring (Prometheus, DataDog)
5. Use secrets management (not .env files)
6. Configure auto-scaling
7. Set up CI/CD pipeline

## Performance Tips

### Optimize for Production

```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
      replicas: 3  # Run 3 instances
```

### Enable Redis Persistence

Already configured with AOF (Append-Only File):
```yaml
command: redis-server --appendonly yes
```

### Reduce Cache TTL for Memory

If Redis uses too much memory:

```yaml
# config/config.yaml
cache:
  ttl_seconds: 1800  # Reduce from 3600 to 30 minutes
```

## Cost Monitoring

### Track API Costs

```bash
# Get current costs
curl http://localhost:8000/api/v1/stats | jq '{
  total_cost: .total_cost,
  cost_saved: .total_cost_saved,
  cache_hit_rate: .cache.hit_rate
}'
```

### Reset Statistics

```bash
curl -X POST http://localhost:8000/api/v1/stats/reset
```

## Development Workflow

### Local Development with Docker

```bash
# 1. Start only Redis
docker-compose up -d redis

# 2. Run API locally (for hot reload)
python scripts/start_api.py

# 3. Connect to dockerized Redis
# API will use REDIS_HOST=localhost from local .env
```

### Testing in Docker

```bash
# Run tests inside container
docker-compose exec api pytest tests/ -v

# Or with coverage
docker-compose exec api pytest tests/ --cov=src --cov-report=html
```

### Updating Code

```bash
# Rebuild after code changes
docker-compose build api

# Restart with new code
docker-compose up -d api

# Or both in one command
docker-compose up -d --build
```

## Useful Commands

```bash
# View all containers
docker-compose ps

# View resource usage
docker stats

# Clean up stopped containers
docker-compose rm

# Clean up dangling images
docker image prune

# Complete cleanup (⚠️ removes volumes)
docker-compose down -v
docker system prune -a --volumes

# Export logs to file
docker-compose logs > care-beacon-logs.txt

# Follow logs for all services
docker-compose logs -f

# Restart specific service
docker-compose restart api

# Update just one service
docker-compose up -d --no-deps --build api
```

## Security Considerations

### Secrets Management

❌ **Don't do this in production**:
```bash
# .env file in repo
OPENAI_API_KEY=sk-real-key
```

✅ **Do this instead**:
```bash
# Use secrets management
docker secret create openai_key -
# Paste key, press Ctrl+D

# Reference in compose file
secrets:
  - openai_key
```

### Network Security

```yaml
# Expose only necessary ports
services:
  api:
    ports:
      - "127.0.0.1:8000:8000"  # Only localhost can access
```

### Resource Limits

Always set resource limits in production:

```yaml
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '2.0'
```

---

**Last Updated**: 2025-01-15
**Docker Compose Version**: 2.0+
**Tested On**: macOS, Linux, Windows (WSL2)
