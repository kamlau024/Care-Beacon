# Docker Quick Start Guide

## ✅ Your System is Running!

Both containers are now healthy and operational:
- ✅ `care-beacon-api` - FastAPI + RAG system (Port 8000)
- ✅ `care-beacon-redis` - Cache server (Port 6379)

## 🚀 Quick Commands

### Check Status
```bash
docker-compose ps

# Expected output:
# NAME                STATUS              PORTS
# care-beacon-api     Up (healthy)        0.0.0.0:8000->8000/tcp
# care-beacon-redis   Up (healthy)        0.0.0.0:6379->6379/tcp
```

### View Logs
```bash
# View all logs
docker-compose logs -f

# View API logs only
docker-compose logs -f api

# View last 50 lines
docker-compose logs --tail=50 api
```

### Test the API

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Ask a Question:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are symptoms of breast cancer?"}'
```

**Interactive Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Restart Services
```bash
# Restart everything
docker-compose restart

# Restart just API
docker-compose restart api

# Rebuild and restart (after code changes)
docker-compose build api
docker-compose up -d
```

### Stop Services
```bash
# Stop (preserves data)
docker-compose stop

# Stop and remove containers (preserves volumes/data)
docker-compose down

# ⚠️ DANGER: Remove everything including data
docker-compose down -v
```

## 🔧 What Was Fixed

**Issue:** API container kept restarting

**Cause:** Missing `import os` in `src/caching/redis_cache.py`

**Fix Applied:**
```python
# Added to src/caching/redis_cache.py
import os  # ← This was missing
```

The code used `os.getenv()` to read Docker environment variables (`REDIS_HOST`, `REDIS_PORT`) but the `os` module wasn't imported.

## 📊 System Architecture

```
┌────────────────────────────────┐
│   care-beacon-api Container    │
│   - FastAPI (Port 8000)        │
│   - Answer Generator           │
│   - Retrieval Engine           │
│   - LLM Client                 │
│   - ChromaDB (file-based)      │
│   - Redis Client               │
└───────────┬────────────────────┘
            │ Connects to
            ▼
┌────────────────────────────────┐
│  care-beacon-redis Container   │
│  - Redis Server (Port 6379)    │
│  - Cache Layer                 │
└────────────────────────────────┘
```

## 📁 Data Persistence

Data is stored in Docker volumes and mapped to your host:

```
./data/vector_db/     → ChromaDB vector database (4,064 chunks)
./logs/               → Application logs
./scraped_data/       → Source articles
redis_data (volume)   → Redis cache data
```

**This means:**
- Your vector database persists across container restarts
- You don't need to re-run ingestion each time
- Cache survives restarts

## 🧪 Verify Everything Works

Run these tests to confirm the system is healthy:

```bash
# 1. Health check (should show all services healthy)
curl http://localhost:8000/health

# 2. Ask a question
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How is cancer diagnosed?"}'

# 3. Check statistics
curl http://localhost:8000/api/v1/stats

# 4. Check Docker logs (should show no errors)
docker-compose logs api --tail=20
```

## 🔍 Troubleshooting

### Container Keeps Restarting

```bash
# Check logs for errors
docker-compose logs api

# Common issues:
# - Missing OPENAI_API_KEY in .env
# - Port 8000 already in use
# - Redis not healthy
```

### "No context found" Errors

```bash
# Check if ChromaDB has data
docker-compose exec api ls -la data/vector_db/

# If empty, run ingestion:
docker-compose --profile ingest up ingestion
```

### Redis Connection Errors

```bash
# Check Redis status
docker-compose ps redis

# Should show "Up (healthy)"

# Test connection
docker-compose exec api redis-cli -h redis ping
# Should return: PONG
```

### Performance Issues

```bash
# Check cache hit rate (should be >40%)
curl http://localhost:8000/api/v1/stats | jq '.cache.hit_rate'

# Check container resource usage
docker stats
```

## 📈 Monitoring

### Real-time Logs
```bash
# Follow logs in real-time
docker-compose logs -f

# With timestamps
docker-compose logs -f --timestamps
```

### Resource Usage
```bash
# Monitor CPU/memory usage
docker stats

# Check disk usage
docker system df
```

### Cache Performance
```bash
# Get detailed stats
curl http://localhost:8000/api/v1/stats | jq '{
  total_queries: .cache.total_queries,
  cache_hits: .cache.cache_hits,
  hit_rate: .cache.hit_rate,
  cost_saved: .total_cost_saved
}'
```

## 🛠️ Development Workflow

### Making Code Changes

```bash
# 1. Edit your code
nano src/api/main.py

# 2. Rebuild the container
docker-compose build api

# 3. Restart
docker-compose up -d

# Or combine steps 2-3:
docker-compose up -d --build api
```

### Running Tests Inside Container

```bash
# Run all tests
docker-compose exec api pytest tests/ -v

# Run specific test file
docker-compose exec api pytest tests/test_api.py -v

# With coverage
docker-compose exec api pytest tests/ --cov=src
```

### Accessing Container Shell

```bash
# Open bash shell in API container
docker-compose exec api bash

# Inside container you can:
ls -la                              # List files
python scripts/test_answer_generator.py  # Run scripts
redis-cli -h redis ping             # Test Redis
cat logs/care-beacon.log            # View logs
```

## 🔐 Security Notes

**For Production:**
1. Don't use `.env` file - use secrets management
2. Enable HTTPS (reverse proxy with nginx)
3. Add authentication to API endpoints
4. Set resource limits in docker-compose.yml
5. Use private Docker registry
6. Regular security updates

**Current Setup (Development):**
- ⚠️ API accessible without authentication
- ⚠️ HTTP only (no HTTPS)
- ⚠️ Debug mode available
- ✅ Redis password not required (localhost only)

## 💰 Cost Monitoring

```bash
# Check current costs
curl http://localhost:8000/api/v1/stats | jq '{
  total_cost: .total_cost,
  cost_saved: .total_cost_saved,
  reduction: .cost_reduction_percent
}'

# Expected costs:
# - First query: ~$0.0002
# - Cached query: ~$0.0000
# - Average (50% cache): ~$0.0001
```

## 🎯 Next Steps

Your system is now running! You can:

1. **Test with real questions** via Swagger UI: http://localhost:8000/docs
2. **Monitor performance** with `/api/v1/stats`
3. **Scale up** by running multiple API instances
4. **Deploy to production** (see DOCKER_DEPLOYMENT.md)
5. **Build a frontend** to interact with the API

## 📚 Additional Resources

- Full Docker guide: `DOCKER_DEPLOYMENT.md`
- Architecture details: `DOCKER_ARCHITECTURE.md`
- System overview: `ARCHITECTURE.md`
- API documentation: `CHECKPOINT_2.4_COMPLETE.md`

---

**Status**: ✅ Fully Operational
**Last Updated**: 2025-01-15
**Tested**: Docker 20.10+, Docker Compose 2.0+
