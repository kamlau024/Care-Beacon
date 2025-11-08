# Docker Architecture - Component Distribution

## Where Everything Runs

### Container 1: `care-beacon-api`

This **single container** includes ALL of the following:

```
┌─────────────────────────────────────────────────────────────────┐
│          care-beacon-api Container (Port 8000)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Web Server                                                      │
│  └─ FastAPI (uvicorn)                  /api/v1/ask             │
│     └─ Port 8000                                                │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Core RAG System (Python Libraries - Same Process)        │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  Answer Generator (src/generation/answer_generator.py)    │ │
│  │  ├─ Coordinates entire RAG pipeline                       │ │
│  │  ├─ Calls retrieval engine                                │ │
│  │  ├─ Calls LLM client                                      │ │
│  │  └─ Calls cache layer                                     │ │
│  │                                                            │ │
│  │  Retrieval Engine (src/retrieval/retrieval_engine.py)     │ │
│  │  ├─ Vector search logic                                   │ │
│  │  ├─ Query processing                                      │ │
│  │  └─ Metadata filtering                                    │ │
│  │                                                            │ │
│  │  LLM Client (src/generation/llm_client.py)                │ │
│  │  ├─ OpenAI API calls                                      │ │
│  │  ├─ Retry logic                                           │ │
│  │  └─ Cost tracking                                         │ │
│  │                                                            │ │
│  │  Cache Layer (src/caching/redis_cache.py)                 │ │
│  │  ├─ Redis client                                          │ │
│  │  ├─ Cache key generation                                  │ │
│  │  └─ Connects to: redis:6379                              │ │
│  │                                                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Storage Layer (File-Based - NOT a Separate Service!)     │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  ChromaDB (src/storage/vector_db.py)                      │ │
│  │  ├─ Python library (chromadb==0.4.22)                     │ │
│  │  ├─ Runs IN-PROCESS (same Python process)                │ │
│  │  ├─ Uses SQLite + vector files                            │ │
│  │  ├─ Data location: /app/data/vector_db/                  │ │
│  │  │   ├─ chroma.sqlite3                                    │ │
│  │  │   └─ vector index files                                │ │
│  │  └─ Mounted from host: ./data/vector_db/                 │ │
│  │                                                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Data Ingestion Pipeline (Conditional)                     │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  Parser (src/parsing/parser.py)                           │ │
│  │  Chunker (src/chunking/chunker.py)                        │ │
│  │  Embedding Generator (src/embeddings/generator.py)        │ │
│  │  Ingester (src/ingestion/ingester.py)                     │ │
│  │                                                            │ │
│  │  Note: Only runs if ingestion container is started        │ │
│  │  API container CAN run ingestion if needed                │ │
│  │                                                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  File System (Mounted Volumes)                                  │
│  ├─ /app/data/vector_db/   → ./data/vector_db/    (ChromaDB)  │
│  ├─ /app/logs/             → ./logs/               (Logs)      │
│  └─ /app/scraped_data/     → ./scraped_data/       (Articles)  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Container 2: `care-beacon-redis`

**Separate service** (Redis server):

```
┌─────────────────────────────────────────────────────────────────┐
│          care-beacon-redis Container (Port 6379)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Redis Server 7 (redis:7-alpine)                                │
│  ├─ Port: 6379                                                  │
│  ├─ Data: /data (mounted to redis_data volume)                 │
│  ├─ AOF enabled: appendonly yes                                │
│  └─ Health check: redis-cli ping                               │
│                                                                  │
│  Why separate?                                                  │
│  ✓ Needs to be shared across multiple API instances            │
│  ✓ Should persist independently of API                         │
│  ✓ Can be scaled/managed separately                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Container 3: `care-beacon-ingestion` (Optional, On-Demand)

**One-time/periodic job** (uses same image as API):

```
┌─────────────────────────────────────────────────────────────────┐
│       care-beacon-ingestion Container (Runs Once, Exits)         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Command: python scripts/ingest_data.py                         │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Data Ingestion Pipeline                                   │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  1. Parser                                                 │ │
│  │     └─ Reads: /app/scraped_data/*.md                      │ │
│  │                                                            │ │
│  │  2. Chunker                                                │ │
│  │     └─ Creates chunks (500 tokens max)                    │ │
│  │                                                            │ │
│  │  3. Embedding Generator                                    │ │
│  │     └─ Calls OpenAI API                                   │ │
│  │                                                            │ │
│  │  4. Ingester                                               │ │
│  │     └─ Stores in ChromaDB                                 │ │
│  │                                                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Writes to: /app/data/vector_db/                               │
│  (Same volume as API - data is shared!)                        │
│                                                                  │
│  Usage:                                                         │
│  docker-compose --profile ingest up ingestion                  │
│                                                                  │
│  Exits when complete.                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow in Docker

### Query Flow (Runtime)

```
User → API Container (Port 8000)
         │
         ├─→ FastAPI receives request
         │
         ├─→ Answer Generator (Python function)
         │    │
         │    ├─→ Cache Layer (Python class)
         │    │    └─→ Redis Container :6379
         │    │         └─→ Cache hit? Return cached answer
         │    │
         │    ├─→ Retrieval Engine (Python class)
         │    │    └─→ ChromaDB (Python library)
         │    │         └─→ Read: /app/data/vector_db/chroma.sqlite3
         │    │              (Mounted volume: ./data/vector_db/)
         │    │
         │    ├─→ LLM Client (Python class)
         │    │    └─→ OpenAI API (external)
         │    │
         │    └─→ Cache Layer
         │         └─→ Redis Container :6379
         │              └─→ Store result for future queries
         │
         └─→ FastAPI returns JSON response
              └─→ User
```

### Ingestion Flow (One-Time)

```
Ingestion Container (started manually)
         │
         ├─→ Parser
         │    └─→ Read: /app/scraped_data/*.md
         │         (Mounted: ./scraped_data/)
         │
         ├─→ Chunker
         │    └─→ Create chunks
         │
         ├─→ Embedding Generator
         │    └─→ OpenAI API (external)
         │         └─→ Generate 1536-dim vectors
         │
         └─→ Ingester
              └─→ Write: /app/data/vector_db/
                   (Mounted: ./data/vector_db/)

Container exits when complete.

API Container can now read the data!
```

## Why This Architecture?

### ChromaDB is NOT a Separate Service

**Reason**: ChromaDB is **file-based**, not client-server:

```python
# In API container:
import chromadb

# This DOES NOT connect to a server
client = chromadb.PersistentClient(
    path="/app/data/vector_db"  # Just a directory path!
)

# It reads/writes SQLite + vector files directly
# No network connection needed
```

**Contrast with Redis** (client-server):

```python
# In API container:
import redis

# This CONNECTS to redis container over network
client = redis.Redis(
    host="redis",  # Redis service name in docker-compose
    port=6379
)
```

### Volume Sharing Between Containers

```yaml
# docker-compose.yml
services:
  api:
    volumes:
      - ./data:/app/data  # Mounts host ./data to container /app/data

  ingestion:
    volumes:
      - ./data:/app/data  # Same mount - SHARES the data!
```

**Result**:
- Ingestion writes to `/app/data/vector_db/` in its container
- This is actually `./data/vector_db/` on host
- API reads from `/app/data/vector_db/` in its container
- This is the **same location** on host
- ✅ Data is shared via filesystem, not network

## Container Lifecycle

### Normal Operation (API Running)

```
$ docker-compose up -d

┌──────────────┐
│ care-beacon- │  Running continuously
│     api      │  Serving requests on port 8000
└──────────────┘
       │
       └─→ Connects to ↓

┌──────────────┐
│ care-beacon- │  Running continuously
│    redis     │  Cache server on port 6379
└──────────────┘
```

### Ingestion (One-Time Setup)

```
$ docker-compose --profile ingest up ingestion

┌──────────────┐
│ care-beacon- │  Starts
│  ingestion   │  Processes data
└──────────────┘  Writes to ./data/vector_db/
       │          Exits when done
       │
       └─→ Data available to API ✓
```

## Scaling Strategy

### Single Instance (Default)

```
1 API container + 1 Redis container
Good for: <10K requests/day
Cost: $50-100/month
```

### Multiple API Instances

```yaml
# Scale API to 3 instances
$ docker-compose up -d --scale api=3

┌──────────────┐
│  API #1      │  Port 8000 → 32768
└──────────────┘
       │
       ├─→ Connects to Redis (shared)
       │
┌──────────────┐
│  API #2      │  Port 8000 → 32769
└──────────────┘
       │
       ├─→ Connects to Redis (shared)
       │
┌──────────────┐
│  API #3      │  Port 8000 → 32770
└──────────────┘
       │
       └─→ Connects to Redis (shared)

┌──────────────┐
│    Redis     │  Shared across all API instances
└──────────────┘

# Need load balancer (nginx) in front
```

### Why This Works

1. **API is stateless** - no local state, can run multiple copies
2. **ChromaDB is read-only at runtime** - all instances read same files
3. **Redis is shared** - all instances use same cache
4. **Volume is read-only for API** - no write conflicts

## Key Takeaways

✅ **ONE container** (`care-beacon-api`) contains:
   - FastAPI web server
   - All RAG logic (retrieval, generation, caching)
   - ChromaDB library (file-based, no separate process)

✅ **Redis is separate** because:
   - It needs a server process
   - Must be shared across API instances
   - Requires network communication

✅ **Ingestion is separate** because:
   - It's a one-time/periodic job
   - Should not run in the API container during normal operation
   - Shares data via mounted volume

✅ **Everything in docker-compose.yml**:
   - API service (always running)
   - Redis service (always running)
   - Ingestion service (on-demand via profile)
   - Redis Commander (optional debug tool)

---

**Bottom Line**: All your RAG components run in a SINGLE container. Only Redis needs to be separate because it's a server. ChromaDB is just files on disk, shared via Docker volumes.
