# Performance Optimization Guide

This document provides a comprehensive guide to the performance monitoring and optimization capabilities of Care-Beacon.

**Important caveat before reading further**: the `/api/v1/performance*` endpoints described in the next section **do not exist in the current API** (`api/src/api/main.py`). The only monitoring endpoints that actually exist today are `GET /api/health` (a real Qdrant collection read, 503 if unreachable) and `GET /api/v1/stats` (LLM usage, cache performance, retrieval cost — see `api/src/api/main.py`). The root-level `scripts/benchmark_performance.py` and `scripts/profile_rag_pipeline.py` referenced below also call a plain `/health` path and the nonexistent `/api/v1/performance*` endpoints — they predate the current API surface and would need updating before they'd work again. This section is left in place because the underlying performance concepts (percentiles, cache hit rate, cost tracking) are still useful, but treat the specific endpoints, scripts, and self-hosted infrastructure (dedicated Redis/ChromaDB boxes) described here as historical, not current.

## Table of Contents

1. [Performance Monitoring System](#performance-monitoring-system)
2. [Benchmarking Tools](#benchmarking-tools)
3. [Profiling Tools](#profiling-tools)
4. [Performance Metrics](#performance-metrics)
5. [Optimization Strategies](#optimization-strategies)
6. [Best Practices](#best-practices)

---

## Performance Monitoring System

Care-Beacon includes a built-in performance monitoring system that automatically tracks all API requests and provides detailed metrics.

### Features

- **Automatic Request Tracking**: Every API request is automatically logged with timing information
- **Real-time Metrics**: Access performance metrics via dedicated API endpoints
- **Percentile Calculations**: P50, P90, P95, and P99 response times
- **Endpoint-Specific Metrics**: Track performance for individual endpoints
- **Cache Analytics**: Monitor cache hit rates and effectiveness
- **Cost Tracking**: Track LLM API costs per request and in aggregate

### Performance Endpoints

#### GET /api/v1/performance

Get comprehensive performance metrics including response times, throughput, and cache statistics.

**Example Response:**
```json
{
  "summary": {
    "uptime_seconds": 3600,
    "total_requests": 1250,
    "total_errors": 5,
    "error_rate": 0.004,
    "requests_per_second": 0.347,
    "average_response_time_ms": 1850,
    "total_tokens_used": 625000,
    "total_cost_usd": 12.50,
    "average_cost_per_request": 0.01,
    "cache": {
      "hits": 375,
      "misses": 875,
      "hit_rate": 0.30,
      "total_queries": 1250
    }
  },
  "percentiles": {
    "p50": 1600,
    "p90": 2800,
    "p95": 3200,
    "p99": 4500
  }
}
```

#### GET /api/v1/performance/endpoints

Get metrics broken down by individual endpoint.

**Example Response:**
```json
{
  "endpoints": {
    "/api/v1/ask": {
      "request_count": 1000,
      "average_duration_ms": 2100,
      "min_duration_ms": 800,
      "max_duration_ms": 5000,
      "errors": 3,
      "error_rate": 0.003,
      "cache_hit_rate": 0.35
    },
    "/health": {
      "request_count": 250,
      "average_duration_ms": 5,
      "min_duration_ms": 2,
      "max_duration_ms": 15,
      "errors": 0,
      "error_rate": 0.0,
      "cache_hit_rate": 0.0
    }
  }
}
```

#### GET /api/v1/performance/recent?limit=10

Get metrics for the most recent requests.

**Example Response:**
```json
{
  "requests": [
    {
      "endpoint": "/api/v1/ask",
      "method": "POST",
      "status_code": 200,
      "duration_ms": 1850,
      "cached": false,
      "tokens_used": 500,
      "cost": 0.0125,
      "timestamp": "2025-11-11T10:30:45.123456"
    }
  ],
  "count": 10
}
```

#### POST /api/v1/performance/reset

Reset all performance metrics (useful before benchmarking).

---

## Benchmarking Tools

The `benchmark_performance.py` script provides comprehensive API benchmarking capabilities.

### Basic Usage

```bash
# Run benchmark with default settings (10 questions, 1 iteration)
python scripts/benchmark_performance.py

# Run with custom settings
python scripts/benchmark_performance.py --iterations 3 --questions 10

# Reset metrics before benchmarking
python scripts/benchmark_performance.py --reset --iterations 5

# Use custom API URL
python scripts/benchmark_performance.py --url http://production-api:8000
```

### Command-Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | `http://localhost:8000` | API base URL |
| `--iterations` | `1` | Number of times to repeat question list |
| `--questions` | `10` | Number of questions to use (max: 10) |
| `--output` | `benchmark_results.json` | Output JSON file |
| `--reset` | `False` | Reset performance metrics before benchmarking |

### Example Output

```
BENCHMARK RESULTS
============================================================

Requests:
  Total:      30
  Successful: 30
  Failed:     0

Throughput:
  Requests/sec: 1.25
  Total time:   24.00s

Response Times:
  Mean:   1850ms
  Median: 1600ms
  Min:    850ms
  Max:    4200ms
  StdDev: 450ms
  P95:    3200ms
  P99:    3800ms

Cache Performance:
  Hits:     9
  Misses:   21
  Hit Rate: 30.0%

Costs:
  Total:   $0.375000
  Average: $0.012500

============================================================
```

### Interpreting Results

**Response Times:**
- **Mean/Median**: Average response time. Target: < 2000ms
- **P95/P99**: 95th/99th percentile response times. Shows worst-case performance
- **Standard Deviation**: Response time consistency. Lower is better

**Cache Performance:**
- **Hit Rate**: Percentage of requests served from cache
  - < 20%: Cache is cold or questions are too varied
  - 20-40%: Normal performance with varied questions
  - > 40%: Excellent cache utilization

**Throughput:**
- **Requests/sec**: Number of requests processed per second
- For sequential benchmark, this primarily measures response time
- Target: > 0.5 rps (< 2000ms average response time)

---

## Profiling Tools

The `profile_rag_pipeline.py` script provides detailed profiling of RAG pipeline components.

### Basic Usage

```bash
# Profile full RAG pipeline
python scripts/profile_rag_pipeline.py --mode full --iterations 5

# Profile cache operations
python scripts/profile_rag_pipeline.py --mode cache

# Profile vector search
python scripts/profile_rag_pipeline.py --mode search

# Profile everything
python scripts/profile_rag_pipeline.py --mode all
```

### Profiling Modes

#### 1. Full Pipeline Profiling (`--mode full`)

Profiles the entire RAG pipeline including:
- Cache check time
- Vector database retrieval time
- LLM generation time
- Total end-to-end time

**Example Output:**
```
PROFILING RESULTS
============================================================

Question: What are the symptoms of breast cancer?
Iterations: 5

Cache Check:
  Mean:   2.50ms
  Median: 2.20ms
  Count:  2

Retrieval:
  Mean:   350ms
  Median: 340ms
  Count:  3

Generation:
  Mean:   1450ms
  Median: 1420ms
  Count:  3

Total (Cached):
  Mean:   3ms
  Median: 2ms
  Count:  2

Total (Uncached):
  Mean:   1850ms
  Median: 1820ms
  Count:  3

Time Breakdown (Uncached):
  Retrieval:  18.9% (350ms)
  Generation: 78.4% (1450ms)
  Other:      2.7%

============================================================
```

**Interpretation:**
- **Cache Check**: Very fast (< 5ms is excellent)
- **Retrieval**: Vector search time (< 500ms is good)
- **Generation**: LLM API call time (1000-2000ms is typical for GPT-4o-mini)
- **Time Breakdown**: Shows which component is the bottleneck

#### 2. Cache Profiling (`--mode cache`)

Profiles Redis cache read/write operations.

**Example Output:**
```
Cache Operations (100 iterations):

Write Performance:
  Mean:   0.850ms
  Median: 0.800ms
  Min:    0.500ms
  Max:    3.200ms
  P95:    1.500ms

Read Performance:
  Mean:   0.650ms
  Median: 0.600ms
  Min:    0.400ms
  Max:    2.800ms
  P95:    1.200ms
```

**Targets:**
- Write: < 2ms mean
- Read: < 1ms mean
- If slower, check Redis connection and network latency

#### 3. Vector Search Profiling (`--mode search`)

Profiles vector similarity search against the configured database — that's Qdrant Cloud now, not ChromaDB (this script predates the Qdrant migration, so double-check it actually targets `create_vector_database()` rather than an old ChromaDB import before trusting numbers from it).

**Example Output** (illustrative only — not re-measured against Qdrant Cloud):
```
Vector Search (50 iterations):
Query: 'What are the symptoms of breast cancer?'
Results per query: 5

Search Performance:
  Mean:   350ms
  Median: 340ms
  Min:    280ms
  Max:    520ms
  P95:    450ms
  P99:    490ms
```

**Targets:**
- Mean: < 500ms for < 10K documents
- P95: < 800ms
- If slower, consider:
  - Reducing `top_k` parameter
  - Choosing a Qdrant Cloud region closer to where the `api` Vercel function runs
  - Upgrading past the Qdrant free tier if you're hitting its limits

---

## Performance Metrics

### Key Performance Indicators (KPIs)

#### Response Time
- **Target**: < 2000ms average
- **Excellent**: < 1500ms
- **Acceptable**: 1500-2500ms
- **Poor**: > 2500ms

#### Throughput
- **Target**: > 0.5 requests/second (sequential)
- **With Caching**: > 1.0 requests/second
- **Production Goal**: Handle 1 request/second sustained

#### Cache Hit Rate
- **Target**: > 30% for production traffic
- **Excellent**: > 50%
- **Cost Impact**: Each 10% increase in hit rate saves ~10% on LLM costs

#### Error Rate
- **Target**: < 1%
- **Acceptable**: < 2%
- **Critical**: > 5%

#### Cost per Request
- **GPT-4o-mini**: $0.01-0.02 typical
- **With 40% cache**: $0.006-0.012
- **Monthly at 1 req/sec**: $1,500-2,500 (uncached), $900-1,500 (with cache)

---

## Optimization Strategies

### 1. Caching Optimization

**Current State:**
- Redis-based semantic caching
- 24-hour TTL
- Cache key includes question + filters + similarity threshold

**Optimizations:**
- **Increase Cache Hit Rate**:
  - Normalize questions (lowercase, trim whitespace)
  - Use semantic similarity for cache lookups (fuzzy matching)
  - Increase cache TTL for stable content

- **Reduce Cache Overhead**:
  - Pre-warm cache with common questions
  - Implement cache prefetching for predictable patterns

**Expected Impact:** 30-50% cost reduction, 90% faster cached responses

### 2. Vector Search Optimization

**Current Bottleneck:** Vector search takes ~18-25% of total time

**Optimizations:**
- **Reduce Search Space**:
  - Use metadata filters (cancer type, source) to narrow search
  - Reduce `top_k` from 5 to 3 if acceptable

- **Qdrant Cloud is a managed service** — there's no local disk/RAM to provision for it (that was a ChromaDB-era concern). The levers that remain are picking a Qdrant Cloud region close to where the `api` Vercel function runs, and the collection's own indexing configuration on the Qdrant Cloud side.

**Expected Impact:** 20-30% reduction in search time

### 3. LLM Generation Optimization

**Current Bottleneck:** LLM generation takes ~75-80% of total time

**Optimizations:**
- **Reduce Token Usage**:
  - Shorter prompts (currently ~2000 tokens)
  - Fewer retrieved contexts (reduce from 5 to 3-4)
  - More concise system prompts

- **Model Selection**:
  - GPT-4o-mini: Good balance (current choice)
  - Claude Haiku: Faster, similar quality
  - Consider streaming responses for better perceived performance

**Expected Impact:** 10-20% cost reduction, slight speed improvement

### 4. Parallel Processing

**Future Optimization:**
- Process multiple questions concurrently
- Batch embeddings generation
- Parallel vector searches

**Expected Impact:** 3-5x throughput improvement for batch workloads

---

## Best Practices

### 1. Performance Monitoring

**Regular Monitoring** (using the endpoint that actually exists — `/api/v1/performance` does not):
```bash
curl https://care-beacon-health.vercel.app/api/v1/stats | jq .

# Cache hit rate
curl https://care-beacon-health.vercel.app/api/v1/stats | jq '.cache.hit_rate'

# LLM cost so far
curl https://care-beacon-health.vercel.app/api/v1/stats | jq '.total_cost'
```

There is no built-in P50/P90/P95/P99 latency tracking in the current API — `/api/v1/stats` reports cost, token usage, and cache performance, not response-time percentiles. If you need latency percentiles, you'd need to add that instrumentation (or rely on Vercel's own function-invocation metrics).

**Set Up Alerts:**
- Alert if cache hit rate drops sharply
- Alert if `/api/health` starts returning 503 (the daily keepalive workflow already does a minimal version of this)
- Alert if cost per request/day exceeds budget

### 2. Load Testing

`scripts/benchmark_performance.py` and `scripts/profile_rag_pipeline.py` exist at the repo root but call stale paths (`/health` instead of `/api/health`, and the nonexistent `/api/v1/performance*`). Treat any numbers from them as unverified until they're updated to match the current API surface. There is no `scripts/compare_benchmarks.py` in this repository.

### 3. Cache Management

**Clear Cache When Content Updates:**
```bash
# After running `make ingest`. Requires the ADMIN_API_KEY header now --
# this endpoint didn't used to need authentication.
curl -X POST https://care-beacon-health.vercel.app/api/v1/cache/clear \
  -H "X-API-Key: $ADMIN_API_KEY"
```

There is no `scripts/warm_cache.py` in this repository — cache warming would have to hit `POST /api/v1/ask` directly for each question you want pre-cached.

### 4. Resource Allocation

There is no server to size — the `api` Service is a Vercel serverless function, Qdrant Cloud and Upstash Redis are both managed. The only capacity planning that applies:
- Qdrant Cloud free tier: 1GB storage (upgrade if you outgrow it)
- OpenAI API rate limits, independent of hosting
- Vercel function limits (timeout, memory) — see Vercel's own documentation for current values, not repeated here since this repo doesn't pin a specific `functions` config in `vercel.json`

---

## Performance Testing Checklist

Before deploying to production, complete this checklist:

- [ ] Run full benchmark with 50+ iterations
- [ ] Verify P95 response time < 3000ms
- [ ] Verify cache hit rate > 20% after warmup
- [ ] Verify error rate < 1%
- [ ] Profile pipeline to identify bottlenecks
- [ ] Test with production-like query patterns
- [ ] Monitor costs for 24 hours
- [ ] Set up performance monitoring alerts
- [ ] Document baseline performance metrics
- [ ] Create runbook for performance issues

---

## Troubleshooting

### Slow Response Times

**Symptoms:** P95 > 3000ms, average > 2500ms

**Diagnosis:**
```bash
# Profile pipeline to find bottleneck
python scripts/profile_rag_pipeline.py --mode full --iterations 10
```

**Solutions:**
- If retrieval is slow (> 500ms): Optimize vector search or reduce top_k
- If generation is slow (> 2000ms): Check LLM API latency, consider model change
- If cache is slow (> 5ms): Check Redis connection and latency

### Low Cache Hit Rate

**Symptoms:** Cache hit rate lower than expected

**Diagnosis:**
```bash
curl https://care-beacon-health.vercel.app/api/v1/stats | jq '.cache'
```

There's no `/api/v1/performance/recent` endpoint to inspect individual recent requests — `/api/v1/stats` only reports aggregates.

**Solutions:**
- Questions too varied: consider semantic cache matching (not currently implemented)
- TTL too short: increase `cache.ttl_seconds` in `api/config/config.yaml`

### High Costs

**Diagnosis:**
```bash
curl https://care-beacon-health.vercel.app/api/v1/stats | jq '.llm'
```

**Solutions:**
- Improve cache hit rate (biggest impact)
- Reduce tokens per request (shorter prompts, fewer contexts — see `api/config/prompts.yaml` / `prompts_active.yaml`)
- Consider a cheaper model (`gpt-4o-mini` is already the budget choice; see `api/config/config.yaml`)
- Rate limiting is already in place — the Vercel WAF rule caps `/api/v1/ask` at 60 requests/60s per IP

---

## Next Steps

1. **Implement Recommendations**: Apply optimization strategies from this guide
2. **Continuous Monitoring**: Set up automated performance monitoring
3. **Iterative Improvement**: Profile → Optimize → Benchmark → Repeat
4. **Cost Tracking**: Monitor costs daily and adjust as needed

For questions or issues, see the main [Developer Guide](DEVELOPER_GUIDE.md) or [API Documentation](API.md).
