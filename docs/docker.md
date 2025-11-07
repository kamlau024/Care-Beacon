# Docker Infrastructure Guide

This guide covers how to use Docker Compose to manage the Care-Beacon infrastructure locally.

## Overview

The Docker Compose setup provides:

- **Redis**: Caching layer for query results
- **Redis Commander**: Web UI for debugging Redis (optional)
- **Extensible**: Easy to add more services as needed

## Prerequisites

- Docker Desktop installed and running
- Docker Compose (included with Docker Desktop)

## Quick Start

### Start Infrastructure

```bash
# Start Redis (recommended for development)
make docker-up

# OR use docker-compose directly
docker-compose up -d
```

### Start with Debug Tools

```bash
# Start Redis + Redis Commander web UI
make docker-up-debug

# Then visit: http://localhost:8081
```

### Stop Infrastructure

```bash
# Stop services (keeps data)
make docker-down

# Stop and remove all data
make docker-clean
```

## Services

### Redis (Port 6379)

**Purpose**: Cache query results to reduce LLM API costs

**Connection**:
- Host: `localhost`
- Port: `6379`
- No password (development only)

**Data Persistence**:
- Volume: `redis_data`
- Append-only file (AOF) enabled for durability
- Data persists between restarts

**Health Check**:
```bash
docker-compose ps
# Should show "healthy" status
```

### Redis Commander (Port 8081) - Debug Profile

**Purpose**: Web UI to inspect cached data

**Access**: http://localhost:8081

**Usage**:
- View all cached keys
- Inspect key values
- Delete cache entries
- Monitor cache statistics

**Start Only When Needed**:
```bash
# Regular start (no Redis Commander)
docker-compose up -d

# Start with Redis Commander
docker-compose --profile debug up -d
```

## Makefile Commands

```bash
# Infrastructure
make docker-up          # Start Redis
make docker-up-debug    # Start Redis + Redis Commander
make docker-down        # Stop all services
make docker-restart     # Restart all services
make docker-logs        # View logs
make docker-status      # Check container status
make docker-clean       # Remove everything including volumes

# Development workflow
make dev-start          # Start infrastructure
make dev-stop           # Stop infrastructure
```

## Configuration

The application automatically connects to Docker Redis if `config/config.yaml` has:

```yaml
cache:
  enabled: true
  provider: "redis"
  host: "localhost"
  port: 6379
```

This is already configured by default!

## Troubleshooting

### Redis not connecting

```bash
# Check if Redis is running
docker-compose ps

# Check Redis logs
docker-compose logs redis

# Test connection
redis-cli ping
# Should return: PONG
```

### Port already in use

If port 6379 is already in use, change it in `docker-compose.yml`:

```yaml
redis:
  ports:
    - "6380:6379"  # Use port 6380 on host
```

Then update `config/config.yaml` or `.env`:
```bash
REDIS_PORT=6380
```

### Clear cache data

```bash
# Remove all cached data
docker-compose down -v

# Restart fresh
docker-compose up -d
```

## Data Persistence

### Volumes

- `redis_data`: Stores Redis data
- Located in Docker's volume directory
- Persists across container restarts

### Backup Redis Data

```bash
# Save Redis snapshot
docker-compose exec redis redis-cli BGSAVE

# Export data
docker-compose exec redis redis-cli --rdb /data/dump.rdb

# Copy from container
docker cp care-beacon-redis:/data/dump.rdb ./backup/
```

### Restore Redis Data

```bash
# Stop Redis
docker-compose down

# Copy backup to volume
docker cp ./backup/dump.rdb care-beacon-redis:/data/

# Start Redis
docker-compose up -d
```

## Future Services

The docker-compose.yml is designed to be extensible. Potential future additions:

### PostgreSQL with pgvector

Uncomment the postgres service in `docker-compose.yml` to experiment with PostgreSQL as an alternative to Chroma:

```bash
docker-compose up -d postgres
```

### Monitoring (Prometheus + Grafana)

Add monitoring stack for production:
- Prometheus for metrics collection
- Grafana for dashboards
- Track API latency, costs, cache hit rates

### API Service

In Phase 2, you could add the FastAPI service to Docker Compose:

```yaml
api:
  build: .
  ports:
    - "8000:8000"
  depends_on:
    - redis
  environment:
    - REDIS_HOST=redis
```

## Production Considerations

For production deployment:

1. **Add authentication**: Use Redis password
2. **External Redis**: Consider managed Redis (AWS ElastiCache, Redis Cloud)
3. **Monitoring**: Add health checks and alerting
4. **Backups**: Automated backup strategy
5. **Scaling**: Redis Cluster for high availability

## Development Workflow

Typical development session:

```bash
# 1. Start infrastructure
make docker-up

# 2. Activate conda environment
conda activate care-beacon

# 3. Run tests
make test

# 4. Develop and test your code
python scripts/your_script.py

# 5. View Redis cache (if needed)
# Open http://localhost:8081 after:
docker-compose --profile debug up -d

# 6. Stop when done
make docker-down
```

## Resources

- Docker Compose Docs: https://docs.docker.com/compose/
- Redis Documentation: https://redis.io/documentation
- Redis Commander: https://github.com/joeferner/redis-commander

---

**Last Updated**: 2025-11-07
