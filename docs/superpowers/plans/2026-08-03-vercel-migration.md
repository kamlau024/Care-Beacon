# Vercel Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Care-Beacon off the Render.com free tier onto a single Vercel project, removing the subsystems and artifacts that block a serverless deployment, and keep the Qdrant free-tier cluster alive with a scheduled health request.

**Architecture:** One Vercel project containing two Services — a `web` service rooted at `web-client/` (Next.js 16) and an `api` service rooted at `api/` (FastAPI on Python 3.12) — behind one domain and one route table. Sharing an origin eliminates CORS, `NEXT_PUBLIC_API_URL`, and the Next.js proxy rewrites. Render Redis is replaced by Upstash Redis provisioned through the Vercel Marketplace, which also becomes the store for cost counters that are process-global today. A GitHub Actions cron issues a daily request to `/api/health`, which performs a real Qdrant read.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, qdrant-client, redis-py, OpenAI (embeddings + gpt-4o-mini), Next.js 16 / React 19, Vercel Services, Upstash Redis, GitHub Actions, pytest.

**Source spec:** `docs/superpowers/specs/2026-08-03-vercel-migration-design.md`

## Global Constraints

- **Python version is 3.12.** Vercel's Python runtime supports only 3.12, 3.13 and 3.14. The project currently pins 3.10.19; this move is mandatory, not optional.
- **API runtime dependencies are exactly these eight:** `fastapi`, `pydantic`, `openai`, `qdrant-client`, `redis`, `pyyaml`, `loguru`, `python-dotenv`. Nothing else may be added to `api/requirements.txt` without a corresponding import in `api/src/`.
- **All Python that the API service needs must live under `api/`.** Vercel Services builds each service from its own `root` directory. Configuration is read by relative path, so `config/` moves too.
- **`scraped_data/` (214 MB) and `data/` stay at the repository root**, outside `api/`, so they are excluded from the function bundle by construction.
- **Service rewrites are evaluated in order.** `/api/(.*)` must precede the `/(.*)` catch-all. Routing into a service is final: an unmatched path returns that service's 404, never a fallthrough.
- **A service receives the original request path.** `/api/v1/ask` arrives at FastAPI as `/api/v1/ask`. Existing route prefixes stay as they are; no `basePath` is required.
- **The RAG pipeline is not to be modified.** Chunking, the LLM re-ranker, the `min_similarity: 0.6` threshold, prompt templates and citation formatting are out of scope.
- **`render.yaml` is not deleted until Vercel is verified working** (Task 13). It is the rollback path.
- **Commit after every task.** Never commit `.env`, `scraped_data/`, or `data/`.

## Path change at Task 6

Tasks 1–5 operate on `src/`, `tests/`, `config/`, `scripts/` at the repository root.
**Task 6 moves all of them under `api/`.** Tasks 7–13 therefore use `api/src/`,
`api/tests/`, `api/config/`, `api/scripts/`. If you are reading tasks out of order,
check which side of Task 6 you are on.

## File Structure

**Final layout:**

```
/
├── vercel.json                     # Services definition + public route table
├── .python-version                 # "3.12"
├── api/                            # Python service root
│   ├── requirements.txt            # 8 runtime packages
│   ├── requirements-dev.txt        # test, lint, eval, ingestion-only packages
│   ├── config/{config,prompts}.yaml
│   ├── scripts/ingest.py           # local-only ingestion
│   ├── src/
│   │   ├── api/{main,models}.py
│   │   ├── caching/{redis_cache,models,stats_store}.py
│   │   ├── embeddings/{chunking,embedding_generator}.py
│   │   ├── generation/{answer_generator,llm_client,models}.py
│   │   ├── ingestion/markdown_parser.py
│   │   ├── retrieval/{retrieval_engine,reranker,models}.py
│   │   ├── storage/{qdrant_db,vector_db,models}.py
│   │   └── config_loader.py
│   └── tests/
├── web-client/                     # Next.js service root
├── scraped_data/                   # outside api/, never bundled
├── data/                           # outside api/, never bundled
└── .github/workflows/keepalive.yml
```

**New files:** `vercel.json`, `api/src/caching/stats_store.py`, `api/requirements-dev.txt`, `.github/workflows/keepalive.yml`.

**Deleted:** `src/graph_api/`, `mcp/`, `src/storage/bm25_index.py`, `src/api/performance.py`, `data/bm25_index.pkl`, `tests/test_performance.py`, `tests/test_hybrid_search.py`, `web-client/components/ingestion-control.tsx`, `Dockerfile*`, `docker-compose.yml`, `render.yaml`, `runtime.txt`, tunnel scripts.

---

### Task 1: Remove undeployed subsystems (graph_api and mcp)

Neither `src/graph_api/` (Neo4j GraphRAG) nor `mcp/` appears in `render.yaml` or in the `/api/v1/ask` request path. Together they are 1,069 lines and they are the sole reason the `neo4j` and `gliner` dependencies exist. Nothing under `src/` imports `graph_api` — verified.

**Files:**
- Delete: `src/graph_api/` (5 files, 408 lines)
- Delete: `mcp/` (entire directory, 661 lines of Python plus READMEs)
- Delete: `Dockerfile.graph`, `Dockerfile.mcp`, `requirements-mcp.txt`
- Delete: `scripts/ingest_graph.py`, `scripts/start_mcp_sse.sh`
- Modify: `docker-compose.yml` (remove the `mcp-sse`, `neo4j` and `graph-api` service blocks)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. This is pure subtraction. Later tasks rely only on the fact that `neo4j` and `gliner` are now unreferenced anywhere in the repository.

- [ ] **Step 1: Record the baseline so you can prove you broke nothing**

```bash
pytest -q 2>&1 | tail -5
```

Write down the pass/fail counts. Every later step compares against this number.

- [ ] **Step 2: Prove nothing outside these directories imports them**

```bash
grep -rn "graph_api\|from neo4j\|import neo4j\|from gliner\|import gliner" \
  src/ tests/ scripts/ web-client/ --include="*.py" --include="*.ts" --include="*.tsx" \
  | grep -v "^src/graph_api/"
```

Expected: no output. If anything prints, stop and report it — the deletion is not safe and this plan's assumption was wrong.

- [ ] **Step 3: Delete the files**

```bash
git rm -r src/graph_api mcp
git rm Dockerfile.graph Dockerfile.mcp requirements-mcp.txt
git rm scripts/ingest_graph.py scripts/start_mcp_sse.sh
```

- [ ] **Step 4: Remove the three dead service blocks from docker-compose.yml**

Open `docker-compose.yml` and delete the `mcp-sse:`, `neo4j:` and `graph-api:` service
blocks in their entirety, along with the `neo4j_data` and `neo4j_logs` entries in the
top-level `volumes:` section if present. Leave `api:`, `web:`, `redis:`, `ingestion:`
and `redis-commander:` untouched. (This whole file is deleted in Task 13; it is kept
consistent here so the intermediate commits stay usable.)

- [ ] **Step 5: Verify the compose file still parses**

```bash
docker compose config --quiet && echo "compose OK"
```

Expected: `compose OK`. If Docker is not installed locally, skip this step and note it.

- [ ] **Step 6: Run the full suite**

```bash
pytest -q 2>&1 | tail -5
```

Expected: identical pass/fail counts to Step 1.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove undeployed graph_api and mcp subsystems

Neither appears in render.yaml nor in the request path. Removes 1,069
lines and the sole references to the neo4j and gliner dependencies."
```

---

### Task 2: Remove hybrid search and the 272 MB BM25 index

`ENABLE_HYBRID_SEARCH=false` is already set in production because loading `data/bm25_index.pkl` exhausted Render's memory, so removing this changes no production behaviour. The 272 MB artifact cannot fit a serverless bundle.

**Files:**
- Delete: `src/storage/bm25_index.py` (207 lines)
- Delete: `data/bm25_index.pkl` (272 MB, untracked — remove from disk only)
- Delete: `tests/test_hybrid_search.py`, and the stray root-level `test_hybrid_search.py`
- Modify: `src/storage/qdrant_db.py` — remove the BM25 import, the lazy-load fields, `_load_or_build_bm25_index()`, `hybrid_search()`, and the `ENABLE_HYBRID_SEARCH` env handling
- Modify: `src/retrieval/retrieval_engine.py:98-124` — collapse the hybrid branch
- Modify: `config/config.yaml` — remove `enable_hybrid_search`, `hybrid_alpha`, `bm25_index_path`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `QdrantVectorDatabase` no longer has `enable_hybrid_search`, `hybrid_alpha`, `bm25_index`, `bm25_load_attempted`, `bm25_index_path` attributes or a `hybrid_search()` method. `RetrievalEngine.retrieve()` calls only `self.vector_db.search(query_embedding, n_results, where)`.

- [ ] **Step 1: Delete the module, its tests and the artifact**

```bash
git rm src/storage/bm25_index.py tests/test_hybrid_search.py
git rm --cached test_hybrid_search.py 2>/dev/null || true
rm -f test_hybrid_search.py data/bm25_index.pkl
```

(The root-level `test_hybrid_search.py` is an in-progress move already staged for
deletion in the working tree; this completes it.)

- [ ] **Step 2: Run the suite to see exactly what breaks**

```bash
pytest -q 2>&1 | tail -20
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.storage.bm25_index'`, raised through `src/storage/qdrant_db.py`. This is the failing state that the next steps resolve.

- [ ] **Step 3: Strip BM25 out of qdrant_db.py**

In `src/storage/qdrant_db.py`, delete the import on line 17:

```python
from src.storage.bm25_index import BM25Index
```

Then replace the block at lines 70-90 (everything from the `# Initialize BM25 index` comment through the closing `ENABLE_HYBRID_SEARCH` note) with nothing — the `__init__` should end after `self._ensure_collection_exists()`.

Delete the entire `_load_or_build_bm25_index()` method and the entire `hybrid_search()` method.

- [ ] **Step 4: Collapse the hybrid branch in the retrieval engine**

In `src/retrieval/retrieval_engine.py`, replace lines 98-124 with:

```python
        # Retrieve more results if re-ranking is enabled (retrieve 6x to ensure completeness)
        initial_n_results = query.max_results * 6 if self.reranker else query.max_results

        logger.info(
            f"🔍 Vector search: fetching {initial_n_results} results "
            f"(reranker={'enabled' if self.reranker else 'disabled'})"
        )
        results = self.vector_db.search(
            query_embedding=query_embedding,
            n_results=initial_n_results,
            where=query.filters,
        )
        logger.info(f"📊 Vector search returned {len(results)} results")
```

- [ ] **Step 5: Remove the config block**

In `config/config.yaml`, delete these three lines and the `# Hybrid Search Configuration (Vector + BM25)` comment above them:

```yaml
  enable_hybrid_search: true
  hybrid_alpha: 0.7
  bm25_index_path: "data/bm25_index.pkl"
```

- [ ] **Step 6: Confirm no references survive**

```bash
grep -rni "bm25\|hybrid_search\|hybrid_alpha" src/ tests/ config/ scripts/ || echo "clean"
```

Expected: `clean`.

- [ ] **Step 7: Run the suite**

```bash
pytest -q 2>&1 | tail -5
```

Expected: PASS. Total count is lower than Task 1's baseline by the number of tests in `test_hybrid_search.py`; no failures.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: remove BM25 hybrid search

Already disabled in production via ENABLE_HYBRID_SEARCH=false after the
272 MB pickle exhausted Render's memory. Retrieval is pure vector search,
which is what production has been running."
```

---

### Task 3: Remove the dead ChromaDB VectorDatabase class

`src/storage/vector_db.py:15-362` defines a `VectorDatabase` class whose `__init__` calls `chromadb.PersistentClient(...)` and `Settings(...)`. Neither name is imported anywhere in the file. Instantiating it raises `NameError`. Only the `create_vector_database()` factory at the bottom is reachable.

**Files:**
- Modify: `src/storage/vector_db.py` — delete lines 15-362, keeping the module docstring, imports and the factory
- Modify: `tests/test_vector_db.py` — delete the test cases that construct `VectorDatabase`

**Interfaces:**
- Consumes: nothing.
- Produces: `src/storage/vector_db.py` exports exactly one public name, `create_vector_database(provider: Optional[str] = None, **kwargs) -> QdrantVectorDatabase`. Its signature and behaviour are unchanged.

- [ ] **Step 1: Prove the class is unreachable**

```bash
grep -rn "VectorDatabase" src/ scripts/ --include="*.py" | grep -v "QdrantVectorDatabase"
```

Expected: only the `class VectorDatabase:` definition line and the factory's return type annotation string. No instantiation anywhere.

- [ ] **Step 2: Replace the file with just the factory**

Rewrite `src/storage/vector_db.py` in full as:

```python
"""Factory for the Qdrant vector database.

ChromaDB support has been removed. This module exists solely to resolve the
configured provider and construct the corresponding database instance.
"""

from typing import Optional, TYPE_CHECKING

from src.config_loader import get_config

if TYPE_CHECKING:
    from src.storage.qdrant_db import QdrantVectorDatabase


def create_vector_database(
    provider: Optional[str] = None,
    **kwargs,
) -> "QdrantVectorDatabase":
    """Create the Qdrant vector database instance.

    Args:
        provider: Database provider (must be "qdrant"). If None, reads from config.
        **kwargs: Additional arguments passed to the database constructor.

    Returns:
        QdrantVectorDatabase instance

    Raises:
        ValueError: If provider is anything other than "qdrant"
    """
    config = get_config()
    provider = provider or config.get("vector_db.provider", "qdrant")

    if provider != "qdrant":
        raise ValueError(
            f"Unsupported vector database provider: {provider!r}. Only 'qdrant' is supported. "
            "Set VECTOR_DB_PROVIDER=qdrant and configure QDRANT_URL and QDRANT_API_KEY."
        )

    from src.storage.qdrant_db import QdrantVectorDatabase

    return QdrantVectorDatabase(**kwargs)
```

- [ ] **Step 3: Run the vector_db tests to see which break**

```bash
pytest tests/test_vector_db.py -q 2>&1 | tail -20
```

Expected: FAIL — `ImportError: cannot import name 'VectorDatabase'` or `AttributeError` in the tests that construct it.

- [ ] **Step 4: Delete the tests that exercise the removed class**

In `tests/test_vector_db.py`, remove every test that imports or instantiates `VectorDatabase`. Keep every test that targets `create_vector_database` or `QdrantVectorDatabase`.

Add this test to cover the surviving error path — note it asserts on the old provider name, which is the realistic failure a stale `.env` would produce:

```python
def test_create_vector_database_rejects_non_qdrant_provider():
    """A stale VECTOR_DB_PROVIDER=chromadb must fail loudly, not silently."""
    import pytest
    from src.storage.vector_db import create_vector_database

    with pytest.raises(ValueError, match="Only 'qdrant' is supported"):
        create_vector_database(provider="chromadb")
```

- [ ] **Step 5: Run the suite**

```bash
pytest -q 2>&1 | tail -5
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete dead ChromaDB VectorDatabase class

The class referenced chromadb and Settings, neither of which is imported;
constructing it raised NameError. Removes 350 lines, leaving the factory."
```

---

### Task 4: Remove the ingestion endpoints and authenticate the admin endpoints

`/api/v1/admin/ingest` and `/api/v1/admin/ingest/stream` spawn a 15-minute `subprocess` running an ingestion script. Vercel Functions cannot do this under any configuration. Ingestion is already run locally.

Those two endpoints are also the only current users of the `require_admin_api_key` guard and the `Depends` import. Rather than leave an unused auth guard sitting in the file for six tasks, this task immediately repoints it at `/api/v1/cache/clear` and `/api/v1/stats/reset` — which have **no authentication at all** today, so anyone who finds the URL can wipe the cache.

**Files:**
- Modify: `src/api/main.py` — delete lines 666-835 (both endpoints), delete `reset_answer_generator()`, apply the guard to the two admin endpoints
- Modify: `tests/test_api.py` — add admin auth tests
- Delete: `web-client/components/ingestion-control.tsx` (318 lines)
- Modify: `web-client/lib/api.ts` — delete `triggerIngestion`
- Modify: `web-client/lib/types.ts` — delete `IngestionResponse`
- Modify: `web-client/app/page.tsx` — remove the ingestion panel from the admin page

**Interfaces:**
- Consumes: nothing.
- Produces: the `api` object exported from `web-client/lib/api.ts` no longer has a `triggerIngestion` method. `POST /api/v1/cache/clear` and `POST /api/v1/stats/reset` require an `X-API-Key` header matching the `ADMIN_API_KEY` environment variable — 403 without it, 503 when `ADMIN_API_KEY` is unset. `reset_answer_generator()` no longer exists; nothing references it after the ingest endpoints are gone.

- [ ] **Step 1: Delete both endpoint functions**

In `src/api/main.py`, delete from the `@app.post("/api/v1/admin/ingest", ...)` decorator through the end of `stream_ingestion` (the `return StreamingResponse(...)` block and its closing paren) — lines 666-835 inclusive.

- [ ] **Step 2: Delete reset_answer_generator and the orphaned json import**

`reset_answer_generator()` (`src/api/main.py:165-171`) had exactly two callers, both inside the endpoints you just deleted. Verify, then remove the function:

```bash
grep -n "reset_answer_generator" src/api/main.py tests/
```

Expected: only the `def reset_answer_generator` line. If anything else appears, stop and report it. Then delete the function.

The `json` import on line 5 was used only by the SSE generator. Delete it only if nothing else references it:

```bash
grep -n "json\." src/api/main.py
```

If there is no output, remove `import json` from line 5. If there is output, leave it.

Keep the `Depends` import and the `require_admin_api_key` function — Step 8 repoints them.

- [ ] **Step 3: Delete the frontend component and its wiring**

```bash
git rm web-client/components/ingestion-control.tsx
```

In `web-client/lib/api.ts`, delete the `triggerIngestion` method (lines 82-91) and remove `IngestionResponse` from the type import block at the top.

In `web-client/lib/types.ts`, delete the `IngestionResponse` interface.

In `web-client/app/page.tsx`, remove the `IngestionControl` import and its JSX usage on the admin page.

- [ ] **Step 4: Verify no references survive**

```bash
grep -rn "IngestionControl\|triggerIngestion\|IngestionResponse\|admin/ingest" \
  web-client/app web-client/components web-client/lib src/ || echo "clean"
```

Expected: `clean`.

- [ ] **Step 5: Typecheck the frontend**

```bash
cd web-client && npx tsc --noEmit; cd ..
```

Expected: no errors.

- [ ] **Step 6: Write the failing test for admin authentication**

Add to `tests/test_api.py`:

```python
def test_clear_cache_requires_api_key(client, mock_generator, monkeypatch):
    """An unauthenticated caller must not be able to wipe the cache."""
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    assert client.post("/api/v1/cache/clear").status_code == 403


def test_clear_cache_succeeds_with_api_key(client, mock_generator, monkeypatch):
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    response = client.post("/api/v1/cache/clear", headers={"X-API-Key": "secret-key"})
    assert response.status_code == 200


def test_reset_stats_requires_api_key(client, mock_generator, monkeypatch):
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")
    assert client.post("/api/v1/stats/reset").status_code == 403


def test_admin_endpoints_disabled_when_no_key_configured(client, mock_generator, monkeypatch):
    """An unset ADMIN_API_KEY must close the endpoints, not open them."""
    monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "")
    assert client.post("/api/v1/cache/clear").status_code == 503
```

The existing `test_clear_cache` and `test_reset_stats` tests call these endpoints with no header and expect 200. Add `monkeypatch.setattr("src.api.main.ADMIN_API_KEY", "secret-key")` and `headers={"X-API-Key": "secret-key"}` to both so they still exercise the success path.

- [ ] **Step 7: Run to verify it fails**

```bash
pytest tests/test_api.py -k "api_key or admin_endpoints" -q 2>&1 | tail -10
```

Expected: FAIL — the endpoints return 200 because no dependency guards them.

- [ ] **Step 8: Apply the guard**

`require_admin_api_key` already exists at `src/api/main.py:60-76`. Change its body to read the module global at call time rather than closing over the import-time value — otherwise `monkeypatch` cannot reach it:

```python
async def require_admin_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Require a valid admin API key.

    Raises:
        HTTPException: 503 if no key is configured, 403 if the supplied key is wrong.
    """
    import hmac

    configured_key = ADMIN_API_KEY
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints disabled",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
```

Add the dependency to both admin decorators:

```python
@app.post(
    "/api/v1/cache/clear",
    tags=["Administration"],
    dependencies=[Depends(require_admin_api_key)],
)
```

```python
@app.post(
    "/api/v1/stats/reset",
    tags=["Administration"],
    dependencies=[Depends(require_admin_api_key)],
)
```

`Depends` and `Header` are already imported on line 11.

- [ ] **Step 9: Run the suite**

```bash
pytest -q 2>&1 | tail -5
```

Expected: PASS. No test in `tests/test_api.py` covers the ingest endpoints — verified — so the count drops only if you removed something else by accident.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: remove ingestion endpoints, authenticate admin endpoints

Vercel Functions cannot spawn a 15-minute subprocess; ingestion is run
locally, which is already how it works in practice.

The deleted endpoints were the only users of require_admin_api_key, so
it is repointed at /cache/clear and /stats/reset — which had no
authentication at all."
```

---

### Task 5: Remove in-process performance monitoring and rate limiting

The performance monitor and the `_rate_limit_cache` `OrderedDict` are process-global. They already reset on every Render redeploy; on serverless they would report per-instance noise. Rate limiting moves to the Vercel WAF, configured in the dashboard rather than in code.

**Files:**
- Delete: `src/api/performance.py` (292 lines)
- Delete: `tests/test_performance.py` (304 lines)
- Modify: `src/api/main.py` — remove the import, the `performance_middleware`, the four `/api/v1/performance*` endpoints, the rate-limit constants and helpers, and the rate-limit check inside `ask_question`
- Modify: `tests/test_api.py` — delete the `TestPerformanceEndpoints` class and the four rate-limit tests
- Modify: `config/config.yaml` — remove the `rate_limit` block under `api:`

**Interfaces:**
- Consumes: nothing.
- Produces: `src/api/main.py` no longer defines `get_client_ip`, `check_rate_limit`, `_rate_limit_cache`, `RATE_LIMIT_WINDOW`, `RATE_LIMIT_MAX_REQUESTS`, or `performance_middleware`. The endpoint signature becomes `ask_question(question_request: QuestionRequest)` — the `request: Request` parameter existed only to feed `get_client_ip`, and the exception handlers receive their own `request`.

- [ ] **Step 1: Delete the module and its dedicated test file**

```bash
git rm src/api/performance.py tests/test_performance.py
```

- [ ] **Step 2: Run the suite to see the breakage**

```bash
pytest -q 2>&1 | tail -20
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.performance'` from `src/api/main.py` and `tests/test_api.py`.

- [ ] **Step 3: Strip main.py**

In `src/api/main.py`:

1. Delete the import on line 47: `from src.api.performance import get_performance_monitor`
2. Delete the entire `performance_middleware` function (lines 132-150) including its `@app.middleware("http")` decorator
3. Delete the rate-limiting block, lines 174-237: the `from collections import OrderedDict` import, `_rate_limit_cache`, `_RATE_LIMIT_MAX_IPS`, `RATE_LIMIT_WINDOW`, `RATE_LIMIT_MAX_REQUESTS`, `get_client_ip()` and `check_rate_limit()`
4. In `ask_question`, delete the rate-limit guard:

```python
    # Rate limiting
    client_ip = get_client_ip(request)
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_MAX_REQUESTS} requests per minute.",
        )
```

That guard was the only use of the `request` parameter, so drop it from the signature too:

```python
async def ask_question(question_request: QuestionRequest):
```

and remove the `request: FastAPI request object` line from the docstring's `Args:` block. Check whether `Request` is still imported for anything else before removing it from line 11:

```bash
grep -n "Request" src/api/main.py | grep -v RequestValidationError | grep -v QuestionRequest
```

The exception handlers take their own `request: Request`, so the import stays.

5. Delete all four `/api/v1/performance*` endpoint functions (lines 838-956)
6. In the `root()` endpoint, remove the three performance entries from the `endpoints` dict, leaving:

```python
        "endpoints": {
            "ask": "/api/v1/ask",
            "health": "/api/health",
            "stats": "/api/v1/stats",
        }
```

- [ ] **Step 4: Remove the config block**

In `config/config.yaml`, under `api:`, delete:

```yaml
  rate_limit:
    enabled: true
    requests_per_minute: 60
```

- [ ] **Step 5: Delete the obsolete tests**

In `tests/test_api.py`, delete the entire `TestPerformanceEndpoints` class (line 875 to end of file) and these four rate-limit tests: `test_rate_limiting`, `test_rate_limit_disabled`, `test_rate_limit_returns_false_when_limit_exceeded_directly`, `test_rate_limit_exceeded`, plus `test_ask_endpoint_with_rate_limit_check`.

`test_root_endpoint` asserts on the `endpoints` dict — update its expected value to match the three entries from Step 3.

- [ ] **Step 6: Confirm no references survive**

```bash
grep -rn "performance\|rate_limit\|RATE_LIMIT" src/ tests/ config/ --include="*.py" --include="*.yaml" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 7: Run the suite**

```bash
pytest -q 2>&1 | tail -5
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: remove in-process perf monitoring and rate limiting

Both were process-global and already reset on every redeploy. Rate
limiting moves to the Vercel WAF."
```

---

### Task 6: Restructure into the api/ service root

Vercel Services builds each service from its own `root` directory, so all Python the API needs must live under one folder. Configuration is loaded by relative path (`Path("config/prompts.yaml")`), so it moves with the code.

**This task changes every path used by Tasks 7-13.**

**Files:**
- Move: `src/` → `api/src/`, `tests/` → `api/tests/`, `config/` → `api/config/`
- Move: `scripts/ingest_all_articles_low_memory.py` → `api/scripts/ingest.py`
- Move: `requirements.txt` → `api/requirements.txt`
- Create: `vercel.json`
- Modify: `.python-version` → `3.12`
- Delete: `runtime.txt`

**Interfaces:**
- Consumes: the post-Task-5 tree.
- Produces: **all subsequent tasks use `api/`-prefixed paths.** The `from src.…` import statements are unchanged — `api/` is the service root, so `src` remains the top-level package from Python's point of view. Test invocation becomes `cd api && pytest`.

- [ ] **Step 1: Move the Python tree**

```bash
mkdir -p api/scripts
git mv src api/src
git mv tests api/tests
git mv config api/config
git mv requirements.txt api/requirements.txt
git mv scripts/ingest_all_articles_low_memory.py api/scripts/ingest.py
```

- [ ] **Step 2: Delete the superseded ingestion variants**

```bash
git rm scripts/ingest_all_articles.py scripts/ingest_all_articles_to_qdrant.py
rm -f scripts/ingest_all_articles_low_memory.py.bak
```

`api/scripts/ingest.py` is the one that production used and the only one retained.

- [ ] **Step 3: Set the Python version**

```bash
echo "3.12" > .python-version
git rm runtime.txt
```

- [ ] **Step 4: Create vercel.json**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "web": {
      "root": "web-client/"
    },
    "api": {
      "root": "api/",
      "entrypoint": "src.api.main:app",
      "excludeFiles": "{tests/**,scripts/**,**/test_*.py}"
    }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "api" } },
    { "source": "/(.*)", "destination": { "service": "web" } }
  ]
}
```

The `/api/(.*)` rule must stay first — rewrites are evaluated in order and routing into a service is final.

- [ ] **Step 5: Verify tests still pass from the new root**

```bash
cd api && pytest -q 2>&1 | tail -5; cd ..
```

Expected: PASS with the same count as Task 5. The `from src.…` imports resolve because `api/` is now the working directory.

- [ ] **Step 6: Verify config still loads by relative path**

```bash
cd api && python -c "
from src.config_loader import get_config
c = get_config()
assert c.get('vector_db.provider') == 'qdrant', c.get('vector_db.provider')
print('config resolves from api/')
"; cd ..
```

Expected: `config resolves from api/`.

- [ ] **Step 7: Confirm the bundle boundary**

```bash
ls api/ && echo "---" && ls -d scraped_data data 2>/dev/null
```

Expected: `scraped_data` and `data` are listed at the root, **not** inside `api/`. This is what keeps 214 MB out of the function bundle.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: move Python into api/ service root, pin Python 3.12

Vercel Services builds each service from its own root directory. Adds
vercel.json defining the web and api services and the public route table.
Python 3.10.19 -> 3.12; Vercel supports only 3.12+."
```

---

### Task 7: Split runtime and development dependencies

The API imports eight packages. `requirements.txt` installs 36, including langchain, langgraph, ragas, datasets, jupyter, gliner, pandas and the lint/type toolchain. This is the largest single lever on build time and cold start.

**Files:**
- Rewrite: `api/requirements.txt`
- Create: `api/requirements-dev.txt`

**Interfaces:**
- Consumes: the `api/` layout from Task 6.
- Produces: `api/requirements.txt` contains exactly eight packages. Vercel installs only this file.

- [ ] **Step 1: Write the runtime requirements**

Replace `api/requirements.txt` in full:

```
# Runtime dependencies for the Vercel `api` service.
# Every package here must correspond to an import under api/src/.
# Development, test, evaluation and ingestion-only packages live in
# requirements-dev.txt and are never installed on Vercel.

fastapi==0.115.0
pydantic>=2.9.0
openai>=1.109.1
qdrant-client==1.12.1
redis==5.0.1
pyyaml==6.0.1
loguru==0.7.2
python-dotenv==1.0.1
```

`uvicorn` is deliberately absent — Vercel supplies the ASGI server.

- [ ] **Step 2: Write the development requirements**

Create `api/requirements-dev.txt`:

```
# Development, test, evaluation and ingestion dependencies.
# Never installed on Vercel. Install with:
#   pip install -r requirements.txt -r requirements-dev.txt

-r requirements.txt

# Local API server
uvicorn[standard]==0.30.0

# Ingestion (run locally, not in the deployed API).
# psutil is imported by scripts/ingest.py for memory monitoring.
python-frontmatter==1.1.0
psutil==5.9.8
tqdm>=4.66.3

# Testing
pytest==8.0.0
pytest-asyncio==0.23.5
pytest-cov==4.1.0
httpx==0.26.0

# Code quality
black==24.2.0
flake8==7.0.0
mypy==1.8.0

# RAG evaluation (evaluation/ imports pandas, requests and tqdm)
ragas==0.3.9
datasets==4.4.1
langchain==1.0.7
langchain-openai==1.0.3
langchain-community==0.4.1
langchain-text-splitters==1.0.0
langgraph==1.0.3
pandas==2.2.0
requests>=2.32.0

# Notebooks
jupyter==1.0.0
ipython==8.21.0
```

Deliberately dropped entirely, not moved: `anthropic` (never imported —
`llm_client.py` raises `NotImplementedError` for that provider), `neo4j` and `gliner`
(deleted with `graph_api` in Task 1), `rank-bm25` (deleted in Task 2), `markdown`
(no `import markdown` anywhere), `pydantic-settings` (no `BaseSettings` subclass),
and `numpy` (no direct import; `ragas` and `datasets` pull it transitively).

- [ ] **Step 3: Prove every runtime package is actually imported**

```bash
cd api
for pkg in fastapi pydantic openai qdrant_client redis yaml loguru dotenv; do
  printf "%-15s " "$pkg"
  grep -rqE "^(import|from) $pkg" src/ && echo "imported" || echo "NOT IMPORTED — remove it"
done
cd ..
```

Expected: all eight report `imported`.

- [ ] **Step 4: Prove nothing under src/ imports a dev-only package**

```bash
cd api
grep -rnE "^(import|from) (numpy|pandas|anthropic|neo4j|gliner|rank_bm25|frontmatter|psutil|tqdm|langchain|ragas|markdown|requests)\b" src/ \
  && echo "LEAK — a dev package is imported at runtime" || echo "clean"
cd ..
```

Expected: `clean`. Note this greps `src/` only — `scripts/ingest.py` legitimately imports `psutil`, and `evaluation/` legitimately imports `pandas` and `requests`. Neither is bundled into the function.

- [ ] **Step 5: Verify the API boots against runtime deps alone**

```bash
cd api
python -m venv /tmp/cb-runtime-check
/tmp/cb-runtime-check/bin/pip install -q -r requirements.txt
/tmp/cb-runtime-check/bin/python -c "from src.api.main import app; print('API imports on 8 packages')"
rm -rf /tmp/cb-runtime-check
cd ..
```

Expected: `API imports on 8 packages`. A `ModuleNotFoundError` here means a runtime import was missed — add the package to `requirements.txt` and note the discrepancy, since it contradicts the spec's audit.

- [ ] **Step 6: Run the suite in your normal environment**

```bash
cd api && pytest -q 2>&1 | tail -5; cd ..
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "build: split runtime and dev dependencies, 36 -> 8 at runtime

The API imports eight packages. Everything else — langchain, ragas,
jupyter, pandas, the lint toolchain, and ingestion-only packages — moves
to requirements-dev.txt and is never installed on Vercel."
```

---

### Task 8: Move cost counters into Redis

`LLMClient`, `EmbeddingGenerator` and `CacheStats` hold `total_cost`, token counts and `call_count` as instance attributes. On serverless each invocation may see a fresh instance, so `/api/v1/stats` would report near-garbage. Moving them to Redis also fixes the existing bug where every Render redeploy zeroes them.

**Files:**
- Create: `api/src/caching/stats_store.py`
- Create: `api/tests/test_stats_store.py`
- Modify: `api/src/generation/llm_client.py` — `get_stats`/`reset_stats` and the counter updates
- Modify: `api/src/embeddings/embedding_generator.py` — same
- Modify: `api/src/caching/redis_cache.py` — back `CacheStats` with the store

**Interfaces:**
- Consumes: `RedisCache` from Task 6's tree; `redis` from Task 7's runtime set.
- Produces: `api/src/caching/stats_store.py` exporting

```python
class StatsStore:
    def __init__(self, client: Optional[redis.Redis], key_prefix: str = "care_beacon:") -> None
    def incr(self, field: str, amount: int = 1) -> None
    def incr_float(self, field: str, amount: float) -> None
    def get_all(self) -> Dict[str, float]
    def reset(self) -> None
```

Field names used by later readers: `llm_calls`, `llm_input_tokens`, `llm_output_tokens`, `llm_cost`, `embed_tokens`, `embed_cost`, `cache_queries`, `cache_hits`, `cache_misses`, `cache_errors`, `cache_cost_saved`, `cache_time_saved_ms`. All values are returned as `float`; callers cast counts to `int` where they need one. A `StatsStore` built with `client=None` is a working no-op, which is how tests and a Redis-down production stay functional.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_stats_store.py`:

```python
"""Tests for the Redis-backed statistics store."""

import pytest

from src.caching.stats_store import StatsStore


class FakeRedis:
    """Minimal in-memory stand-in for the Redis commands StatsStore uses."""

    def __init__(self):
        self.data = {}

    def hincrby(self, name, key, amount):
        self.data.setdefault(name, {})
        self.data[name][key] = int(self.data[name].get(key, 0)) + amount

    def hincrbyfloat(self, name, key, amount):
        self.data.setdefault(name, {})
        self.data[name][key] = float(self.data[name].get(key, 0)) + amount

    def hgetall(self, name):
        return {k: str(v) for k, v in self.data.get(name, {}).items()}

    def delete(self, name):
        self.data.pop(name, None)


def test_counters_accumulate_across_separate_instances():
    """The whole point: two instances sharing Redis must see one total."""
    shared = FakeRedis()

    StatsStore(shared).incr("llm_calls", 3)
    StatsStore(shared).incr("llm_calls", 2)

    assert StatsStore(shared).get_all()["llm_calls"] == 5


def test_float_and_int_counters_coexist():
    store = StatsStore(FakeRedis())
    store.incr("llm_calls", 2)
    store.incr_float("llm_cost", 0.0025)

    result = store.get_all()
    assert result["llm_calls"] == 2.0
    assert result["llm_cost"] == pytest.approx(0.0025)


def test_missing_field_reads_as_zero():
    assert StatsStore(FakeRedis()).get_all().get("llm_cost", 0.0) == 0.0


def test_reset_clears_every_field():
    store = StatsStore(FakeRedis())
    store.incr("llm_calls", 7)
    store.reset()
    assert store.get_all() == {}


def test_none_client_is_a_silent_no_op():
    """Redis down must degrade to zeros, never raise into the request path."""
    store = StatsStore(None)
    store.incr("llm_calls", 1)
    store.incr_float("llm_cost", 1.5)
    store.reset()
    assert store.get_all() == {}
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd api && pytest tests/test_stats_store.py -q 2>&1 | tail -5; cd ..
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.caching.stats_store'`.

- [ ] **Step 3: Implement the store**

Create `api/src/caching/stats_store.py`:

```python
"""Redis-backed cumulative statistics.

Cost and usage counters must survive both process restarts and the many short-lived
instances a serverless deployment creates. A single Redis hash holds every counter;
readers fetch it in one round trip.

When no Redis client is available the store degrades to a silent no-op rather than
raising, so a cache outage never breaks the request path.
"""

from typing import Dict, Optional

import redis
from redis.exceptions import RedisError


class StatsStore:
    """Cumulative counters held in one Redis hash."""

    def __init__(self, client: Optional["redis.Redis"], key_prefix: str = "care_beacon:") -> None:
        """Initialise the store.

        Args:
            client: Connected Redis client, or None to disable persistence.
            key_prefix: Prefix shared with the rest of the cache keyspace.
        """
        self.client = client
        self.key = f"{key_prefix}stats"

    def incr(self, field: str, amount: int = 1) -> None:
        """Add to an integer counter."""
        if self.client is None:
            return
        try:
            self.client.hincrby(self.key, field, amount)
        except RedisError:
            pass

    def incr_float(self, field: str, amount: float) -> None:
        """Add to a floating-point counter."""
        if self.client is None:
            return
        try:
            self.client.hincrbyfloat(self.key, field, amount)
        except RedisError:
            pass

    def get_all(self) -> Dict[str, float]:
        """Read every counter.

        Returns:
            Field name to value. Empty when Redis is unavailable.
        """
        if self.client is None:
            return {}
        try:
            raw = self.client.hgetall(self.key)
        except RedisError:
            return {}
        return {k: float(v) for k, v in raw.items()}

    def reset(self) -> None:
        """Delete every counter."""
        if self.client is None:
            return
        try:
            self.client.delete(self.key)
        except RedisError:
            pass
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd api && pytest tests/test_stats_store.py -q 2>&1 | tail -5; cd ..
```

Expected: PASS, 5 tests.

- [ ] **Step 5: Wire the store into RedisCache**

In `api/src/caching/redis_cache.py`, add the import at the top:

```python
from src.caching.stats_store import StatsStore
```

At the end of `__init__` (after the try/except that sets `self.client`), add:

```python
        # Cumulative counters shared across instances
        self.stats_store = StatsStore(self.client, self.config.key_prefix)
```

In `get()`, replace the three in-process increments with paired writes so the local object stays correct for the current request while Redis accumulates the true total:

```python
        self.stats.total_queries += 1
        self.stats_store.incr("cache_queries")
```

```python
                self.stats.cache_hits += 1
                self.stats_store.incr("cache_hits")
```

```python
                self.stats.cache_misses += 1
                self.stats_store.incr("cache_misses")
```

And in both `except` blocks that increment errors:

```python
            self.stats.cache_errors += 1
            self.stats_store.incr("cache_errors")
```

In `get_stats()`, prefer the Redis totals when present. Replace the first line of the method:

```python
        stats_dict = self.stats.to_dict()
        persisted = self.stats_store.get_all()
        if persisted:
            queries = persisted.get("cache_queries", 0.0)
            hits = persisted.get("cache_hits", 0.0)
            stats_dict.update({
                "total_queries": int(queries),
                "cache_hits": int(hits),
                "cache_misses": int(persisted.get("cache_misses", 0.0)),
                "cache_errors": int(persisted.get("cache_errors", 0.0)),
                "hit_rate": (hits / queries) if queries else 0.0,
                "miss_rate": (persisted.get("cache_misses", 0.0) / queries) if queries else 0.0,
                "total_cost_saved": persisted.get("cache_cost_saved", 0.0),
                "total_time_saved_ms": persisted.get("cache_time_saved_ms", 0.0),
            })
```

In `reset_stats()`, add the persistent reset:

```python
    def reset_stats(self):
        """Reset cache statistics, in-process and persisted."""
        self.stats.reset()
        self.stats_store.reset()
```

- [ ] **Step 6: Record cache savings in Redis**

In `api/src/generation/answer_generator.py`, inside `generate_answer`'s cache-hit branch, add the two persistent increments beside the existing in-process ones:

```python
            self.cache.stats.total_cost_saved += saved_cost
            self.cache.stats.total_time_saved_ms += saved_time_ms
            self.cache.stats_store.incr_float("cache_cost_saved", saved_cost)
            self.cache.stats_store.incr_float("cache_time_saved_ms", saved_time_ms)
```

- [ ] **Step 7: Give LLMClient and EmbeddingGenerator a stats store**

In `api/src/generation/llm_client.py`, add an optional parameter to `__init__`:

```python
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        stats_store: Optional["StatsStore"] = None,
    ):
```

Add the import at the top of the file:

```python
from src.caching.stats_store import StatsStore
```

Store it alongside the existing counters:

```python
        self.stats_store = stats_store or StatsStore(None)
```

In `_generate_openai`, beside the existing `self.total_cost += cost` block:

```python
                self.stats_store.incr("llm_input_tokens", input_tokens)
                self.stats_store.incr("llm_output_tokens", output_tokens)
                self.stats_store.incr_float("llm_cost", cost)
```

In `generate()`, beside `self.call_count += 1`:

```python
        self.stats_store.incr("llm_calls")
```

In `get_stats()`, prefer persisted values. Insert at the top of the method:

```python
        persisted = self.stats_store.get_all()
        calls = int(persisted.get("llm_calls", self.call_count))
        input_tokens = int(persisted.get("llm_input_tokens", self.total_input_tokens))
        output_tokens = int(persisted.get("llm_output_tokens", self.total_output_tokens))
        total_cost = persisted.get("llm_cost", self.total_cost)
```

then replace `self.call_count`, `self.total_input_tokens`, `self.total_output_tokens` and `self.total_cost` throughout the returned dict with `calls`, `input_tokens`, `output_tokens` and `total_cost`.

In `reset_stats()`, add `self.stats_store.reset()` after the four assignments.

Apply the same pattern to `api/src/embeddings/embedding_generator.py`: add the `stats_store` parameter and import, increment `embed_tokens` and `embed_cost` in both `embed_text` and `embed_batch` beside the existing `self.total_tokens_used`/`self.total_cost` updates, and prefer the persisted values in `get_embedding_stats()`:

```python
        persisted = self.stats_store.get_all()
        tokens = int(persisted.get("embed_tokens", self.total_tokens_used))
        cost = persisted.get("embed_cost", self.total_cost)
```

- [ ] **Step 8: Share one store across the pipeline**

In `api/src/generation/answer_generator.py`, `__init__` currently assigns in the order
`retrieval_engine`, `llm_client`, `config`, `cache` — so the cache does not exist yet
when its consumers are built. Replace the whole assignment block with:

```python
        # Cache first: it owns the StatsStore that the other components share.
        self.cache = cache or RedisCache()
        self.llm_client = llm_client or LLMClient(stats_store=self.cache.stats_store)
        self.retrieval_engine = retrieval_engine or RetrievalEngine(
            embedding_generator=EmbeddingGenerator(stats_store=self.cache.stats_store),
        )
        self.config = config or self._load_config()
```

Add the import at the top of the file:

```python
from src.embeddings.embedding_generator import EmbeddingGenerator
```

The `self.prompts = self._load_prompts()` line that follows the block stays where it is.

- [ ] **Step 9: Add an integration test for shared accumulation**

Append to `api/tests/test_stats_store.py`:

```python
def test_llm_client_reports_persisted_totals_not_instance_totals():
    """A fresh client on the same Redis must report the accumulated total."""
    from unittest.mock import patch
    from src.caching.stats_store import StatsStore
    from src.generation.llm_client import LLMClient

    shared = FakeRedis()
    store = StatsStore(shared)
    store.incr("llm_calls", 10)
    store.incr_float("llm_cost", 0.42)

    with patch("src.generation.llm_client.OpenAI"):
        client = LLMClient(api_key="test-key", stats_store=store)

    stats = client.get_stats()
    assert stats["total_calls"] == 10
    assert stats["total_cost"] == pytest.approx(0.42)
```

- [ ] **Step 10: Run the full suite**

```bash
cd api && pytest -q 2>&1 | tail -10; cd ..
```

Expected: PASS. Tests in `test_llm_client.py`, `test_embeddings.py` and `test_caching.py` construct these classes without a `stats_store`; the `StatsStore(None)` default keeps them passing unchanged. If any fail, the default is not being applied — fix that rather than editing the tests.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: persist cost and usage counters in Redis

Process-global counters report near-garbage on serverless and already
reset on every redeploy. One Redis hash now holds them, shared across
instances, with a no-op fallback when Redis is unavailable."
```

---

### Task 9: Health endpoint with a real Qdrant read

The keepalive is only meaningful if a 200 proves the Qdrant cluster is reachable. The current `/health` hardcodes `"vector_db": True`. The endpoint also moves to `/api/health` so the single `/api/(.*)` rewrite covers every backend call.

**Files:**
- Modify: `api/src/api/main.py` — the `health_check` endpoint
- Modify: `api/tests/test_api.py` — `test_health_check`

**Interfaces:**
- Consumes: `create_vector_database()` from Task 3; `StatsStore` wiring from Task 8.
- Produces: `GET /api/health` returning `HealthResponse` with `services` keys `vector_db`, `redis_cache`, `llm_client`. `status` is `"healthy"` only when `vector_db` is true; a Qdrant failure yields `"degraded"` with HTTP 503. The old `/health` path no longer exists.

- [ ] **Step 1: Write the failing test**

In `api/tests/test_api.py`, replace `test_health_check` with:

```python
def test_health_check_reports_qdrant_reachable(client, mock_generator):
    """A 200 must mean Qdrant answered, since the keepalive relies on it."""
    from unittest.mock import MagicMock, patch

    with patch("src.api.main.create_vector_database") as mock_factory:
        mock_factory.return_value.client.get_collection = MagicMock(return_value=object())
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["services"]["vector_db"] is True


def test_health_check_returns_503_when_qdrant_unreachable(client, mock_generator):
    """A dead cluster must fail the check, not be masked as healthy."""
    from unittest.mock import patch

    with patch("src.api.main.create_vector_database", side_effect=Exception("connection refused")):
        response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["services"]["vector_db"] is False


def test_old_health_path_is_gone(client):
    """The route moved under /api/ so one rewrite covers the whole backend."""
    assert client.get("/health").status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd api && pytest tests/test_api.py -k health -q 2>&1 | tail -10; cd ..
```

Expected: FAIL — `/api/health` returns 404 because the route is still at `/health`.

- [ ] **Step 3: Implement**

In `api/src/api/main.py`, replace the `health_check` endpoint with:

First add the factory import at **module level**, next to the other `from src.…`
imports near line 36:

```python
from src.storage.vector_db import create_vector_database
```

This must be a module-level import, not a function-local one. The tests patch
`src.api.main.create_vector_database`, and a local import would re-fetch the real
function from `src.storage.vector_db` at call time, silently defeating the patch.

Then replace the endpoint:

```python
@app.get("/api/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check(response: Response):
    """Health check that performs a real Qdrant read.

    A 200 from this endpoint proves the vector database is reachable, which is what
    makes it valid as the scheduled keepalive target. A cluster that has been
    reclaimed must fail this check rather than be masked as healthy.

    Returns:
        Health status of the API and its dependent services.
    """
    try:
        vector_db = create_vector_database()
        vector_db.client.get_collection(collection_name=vector_db.collection_name)
        vector_db_healthy = True
    except Exception as e:
        logger.warning(f"Health check: Qdrant unreachable: {e}")
        vector_db_healthy = False

    generator = get_answer_generator()
    services = {
        "vector_db": vector_db_healthy,
        "redis_cache": generator.cache.is_healthy(),
        "llm_client": True,
    }

    if not vector_db_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if vector_db_healthy else "degraded",
        version=API_VERSION,
        timestamp=datetime.now(),
        services=services,
    )
```

Add `Response` to the FastAPI import on line 11 and `from loguru import logger` near the top-level imports if it is not already module-scope.

`redis_cache` being false does not fail the check — a cache outage degrades cost and latency but the API still answers, and the keepalive is about Qdrant.

- [ ] **Step 4: Update the root endpoint's advertised path**

In `root()`, the `health` entry should read `"/api/health"`. Update `test_root_endpoint` to match if it asserts on this value.

- [ ] **Step 5: Run to verify it passes**

```bash
cd api && pytest tests/test_api.py -k "health or root" -q 2>&1 | tail -5; cd ..
```

Expected: PASS.

- [ ] **Step 6: Run the full suite**

```bash
cd api && pytest -q 2>&1 | tail -5; cd ..
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: /api/health performs a real Qdrant read

Moves the route under /api/ so one rewrite covers the backend, and makes
a 200 actually mean the cluster answered — required for the keepalive to
be meaningful. Qdrant failure returns 503."
```

---

### Task 10: Same-origin frontend

Sharing an origin removes CORS, `NEXT_PUBLIC_API_URL` and the Next.js proxy rewrites — all three existed only because the two halves lived at different addresses.

Admin authentication was folded into Task 4, where the guard's previous users were removed; it is not repeated here.

**Files:**
- Modify: `web-client/lib/api.ts` — `API_BASE_URL` and the health path
- Modify: `web-client/next.config.js` — remove `rewrites` and `output: 'standalone'`
- Delete: `web-client/.env.local`
- Modify: `api/src/api/main.py` — remove the CORS middleware
- Modify: `api/config/config.yaml` — remove `cors_origins`
- Modify: `api/tests/test_api.py` — delete `test_cors_headers`

**Interfaces:**
- Consumes: the `/api/health` route from Task 9.
- Produces: every frontend `fetch` is same-origin and relative — no absolute API URL survives anywhere in `web-client/`. The FastAPI app no longer installs `CORSMiddleware`.

- [ ] **Step 1: Point the frontend at its own origin**

In `web-client/lib/api.ts`, replace line 10:

```typescript
// Same-origin: the Vercel route table sends /api/* to the Python service.
const API_BASE_URL = ""
```

And change `getHealth` to use the new path:

```typescript
  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/health`)
    return handleResponse<HealthResponse>(response)
  },
```

- [ ] **Step 2: Strip the proxy config**

Replace `web-client/next.config.js` in full:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
}

module.exports = nextConfig
```

`rewrites` existed only to proxy to a separately-hosted API; the Vercel route table now does that. `output: 'standalone'` was for the Docker image being removed in Task 13.

- [ ] **Step 3: Remove the stale env file**

```bash
rm -f web-client/.env.local
```

- [ ] **Step 4: Confirm no absolute API URL survives**

```bash
grep -rn "NEXT_PUBLIC_API_URL\|localhost:8000\|ngrok\|trycloudflare" \
  web-client/app web-client/components web-client/lib web-client/next.config.js || echo "clean"
```

Expected: `clean`.

- [ ] **Step 5: Remove the CORS middleware**

Delete the `cors_origins` lookup and the `app.add_middleware(CORSMiddleware, ...)` block from `api/src/api/main.py`, and remove `from fastapi.middleware.cors import CORSMiddleware` from the imports. In `api/config/config.yaml`, delete the `cors_origins` list under `api:`.

Delete `test_cors_headers` from `api/tests/test_api.py` — with one origin there is no cross-origin request to test.

- [ ] **Step 6: Run the Python suite**

```bash
cd api && pytest tests/test_api.py -q 2>&1 | tail -5; cd ..
```

Expected: PASS.

- [ ] **Step 7: Typecheck and build the frontend**

```bash
cd web-client && npx tsc --noEmit && npm run build; cd ..
```

Expected: both succeed.

- [ ] **Step 8: Confirm the full suite is green**

```bash
cd api && pytest -q 2>&1 | tail -5; cd ..
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: serve the frontend same-origin with the API

The Vercel route table sends /api/* to the Python service, so the client
uses relative URLs. Removes CORS middleware, NEXT_PUBLIC_API_URL and the
Next.js proxy rewrites — all three existed only to bridge two origins."
```

---

### Task 11: Qdrant keepalive workflow

Qdrant Cloud reclaims free-tier clusters after roughly a week of inactivity. A scheduled request to `/api/health` performs a real read and keeps the cluster active.

**Files:**
- Create: `.github/workflows/keepalive.yml`
- Modify: `README.md` — a Keepalive section

**Interfaces:**
- Consumes: `/api/health` from Task 9, which returns 503 when Qdrant is unreachable.
- Produces: a workflow requiring one repository variable, `SITE_URL` (for example `https://care-beacon.vercel.app`), with no secrets.

- [ ] **Step 1: Create the workflow**

```yaml
name: Qdrant keepalive

# Qdrant Cloud reclaims idle free-tier clusters after roughly a week.
# /api/health performs a real collection read, so a 200 here proves the
# cluster is alive rather than merely that the function booted.
on:
  schedule:
    - cron: "0 9 * * *"
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping /api/health
        run: |
          set -euo pipefail
          if [ -z "${SITE_URL:-}" ]; then
            echo "::error::Repository variable SITE_URL is not set."
            exit 1
          fi
          echo "Pinging ${SITE_URL}/api/health"
          status=$(curl --silent --show-error --location \
                        --max-time 60 --retry 3 --retry-delay 10 \
                        --write-out '%{http_code}' \
                        --output /tmp/health.json \
                        "${SITE_URL}/api/health")
          echo "HTTP ${status}"
          cat /tmp/health.json
          echo
          if [ "${status}" != "200" ]; then
            echo "::error::Health check returned ${status}; Qdrant may be unreachable."
            exit 1
          fi
        env:
          SITE_URL: ${{ vars.SITE_URL }}
```

- [ ] **Step 2: Validate the YAML**

```bash
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/keepalive.yml')); print('workflow YAML valid')"
```

Expected: `workflow YAML valid`.

- [ ] **Step 3: Document the two operational caveats**

Add to `README.md`:

```markdown
## Keepalive

Qdrant Cloud reclaims idle free-tier clusters after roughly a week of inactivity.
`.github/workflows/keepalive.yml` issues a daily request to `/api/health`, which
performs a real Qdrant collection read — a 200 proves the cluster answered.

**Setup:** add a repository variable `SITE_URL` (Settings → Secrets and variables →
Actions → Variables) set to the deployed origin, e.g. `https://care-beacon.vercel.app`.

**Two things to know:**

1. GitHub disables scheduled workflows in a repository with no commits for 60 days.
   If the repo goes quiet, the pings stop silently. The workflow also declares
   `workflow_dispatch`, so it can be run by hand from the Actions tab.
2. A failed ping shows up as a red run in the Actions tab. Check there first if the
   vector database appears empty.
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add daily Qdrant keepalive workflow

Pings /api/health, which performs a real collection read. Documents the
60-day GitHub scheduled-workflow disablement rule."
```

---

### Task 12: Deploy to a Vercel preview and verify

Everything so far is verified only locally. This task proves the real build before production is touched. `render.yaml` is still intact, so Render remains the rollback.

**Files:**
- No source changes expected. Fixes discovered here are committed as they arise.

**Interfaces:**
- Consumes: `vercel.json` from Task 6, `api/requirements.txt` from Task 7.
- Produces: a working preview URL, and the confirmed set of environment variables production needs.

- [ ] **Step 1: Provision Upstash Redis**

In the Vercel dashboard, Storage → Marketplace → Upstash Redis. Attach it to the project. It injects `REDIS_URL` automatically.

`api/src/caching/redis_cache.py:69-77` already parses `REDIS_URL` — it was added for Render and works unchanged.

- [ ] **Step 2: Set the remaining environment variables**

For Preview and Production:

```bash
vercel env add OPENAI_API_KEY preview
vercel env add QDRANT_URL preview
vercel env add QDRANT_API_KEY preview
vercel env add ADMIN_API_KEY preview
vercel env add VECTOR_DB_PROVIDER preview   # value: qdrant
```

`ANONYMIZED_TELEMETRY` and `ENABLE_HYBRID_SEARCH` are no longer read — ChromaDB and BM25 are both gone. Do not carry them over.

- [ ] **Step 3: Run both services locally first**

```bash
vercel dev
```

Then in another shell:

```bash
curl -s localhost:3000/api/health | python -m json.tool
```

Expected: HTTP 200, `"status": "healthy"`, `"vector_db": true`. This is the first real proof that the Services route table sends `/api/*` to Python and that FastAPI sees the unstripped path.

- [ ] **Step 4: Deploy a preview**

```bash
vercel deploy
export PREVIEW_URL="https://<the-url-vercel-printed>"
```

Export the printed URL as `PREVIEW_URL` — the remaining steps in this task use it. If the build fails on bundle size, check that `scraped_data/` and `data/` are outside `api/` (Task 6, Step 7).

- [ ] **Step 5: Verify the deployed health endpoint**

```bash
curl -s -o /dev/null -w "%{http_code}\n" "$PREVIEW_URL/api/health"
```

Expected: `200`.

- [ ] **Step 6: Ask a real question and compare against production**

```bash
curl -s -X POST "$PREVIEW_URL/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the symptoms of breast cancer?","max_results":5}' \
  | python -m json.tool > /tmp/preview-answer.json

curl -s -X POST "https://care-beacon-api.onrender.com/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the symptoms of breast cancer?","max_results":5}' \
  | python -m json.tool > /tmp/render-answer.json

diff <(python -c "import json;print([s['article_title'] for s in json.load(open('/tmp/preview-answer.json'))['sources']])") \
     <(python -c "import json;print([s['article_title'] for s in json.load(open('/tmp/render-answer.json'))['sources']])")
```

Expected: identical citation lists. The generated prose may differ slightly — the LLM is non-deterministic at `temperature=0.1` — but the retrieved sources must match, since retrieval is unchanged. **If the citations differ, stop.** Something in the retrieval path changed that should not have.

- [ ] **Step 7: Verify admin auth is live**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$PREVIEW_URL/api/v1/cache/clear"
```

Expected: `403`.

- [ ] **Step 8: Measure cold start**

```bash
sleep 120
curl -s -o /dev/null -w "cold: %{time_total}s\n" "$PREVIEW_URL/api/health"
curl -s -o /dev/null -w "warm: %{time_total}s\n" "$PREVIEW_URL/api/health"
```

Record both. The spec predicts low single-digit seconds cold. Report the actual figures.

- [ ] **Step 9: Check the frontend end to end**

Open the preview URL. Confirm the Search page returns an answer with citations, the Statistics page renders the Vector DB pie charts, and the browser devtools Network tab shows requests going to the preview origin — no cross-origin calls, no CORS preflights.

- [ ] **Step 10: Commit any fixes**

```bash
git add -A
git commit -m "fix: corrections found during Vercel preview verification"
```

If no fixes were needed, skip this step and record that the preview worked unchanged.

---

### Task 13: Production cutover and scaffolding removal

Only once the preview is verified. This is the point of no easy return, so it is last.

**Files:**
- Delete: `render.yaml`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `web-client/Dockerfile`, `web-client/.dockerignore`
- Delete: `scripts/render_build.sh`, `scripts/start_api.py`, `scripts/trigger_render_ingestion.sh`, `scripts/reingest_production.sh`
- Delete: `start-ngrok.sh`, `start-ngrok-dual.sh`, `start-cloudflared-tunnels.sh`, `start-mixed-tunnels.sh`, `start-ssh.sh`, `ngrok.yml`
- Delete: `docs/RENDER_DEPLOYMENT.md`, `docs/DOCKER_*.md`, `docs/docker.md`, `docs/NGROK_FREE_TIER_FIX.md`, `docs/STATIC_DOMAIN_SOLUTION.md`, `docs/MOBILE_ACCESS.md`, `docs/QUICK_MOBILE_SETUP.md`, `web-client/NGROK_*.md`
- Modify: `Makefile` — remove Docker targets, fix test paths
- Modify: `README.md` — deployment section

**Interfaces:**
- Consumes: a verified preview deployment from Task 12.
- Produces: the final repository state.

- [ ] **Step 1: Promote to production**

```bash
vercel deploy --prod
export PROD_URL="https://<the-production-url>"
```

- [ ] **Step 2: Verify production before deleting the rollback**

```bash
curl -s -o /dev/null -w "%{http_code}\n" "$PROD_URL/api/health"
curl -s -X POST "$PROD_URL/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the symptoms of breast cancer?","max_results":5}' \
  | python -c "import json,sys; d=json.load(sys.stdin); print(len(d['sources']), 'sources')"
```

Expected: `200`, and a non-zero source count. **Do not proceed past this step until both succeed** — the next step removes the Render configuration.

- [ ] **Step 3: Set the keepalive target**

In GitHub, Settings → Secrets and variables → Actions → Variables, add `SITE_URL` set to the production origin. Then trigger the workflow manually from the Actions tab and confirm it goes green.

- [ ] **Step 4: Configure the two dashboard-only protections**

Neither of these lives in code, so they are easy to forget and neither has a test.

**Deployment Protection on the Admin route.** Vercel dashboard → Project → Settings →
Deployment Protection. Add a protected path covering the Admin page so the browser
never needs to hold the admin key. Verify by opening the Admin page in a private
window and confirming you are challenged.

**WAF rate limiting**, replacing the in-process limiter deleted in Task 5. Vercel
dashboard → Project → Firewall → Rate Limiting. Add a rule on `/api/v1/ask` at 60
requests per minute per IP, matching the `requests_per_minute: 60` that was in
`config.yaml`. Verify with:

```bash
for i in $(seq 1 65); do
  curl -s -o /dev/null -w "%{http_code} " -X POST "$PROD_URL/api/v1/ask" \
    -H "Content-Type: application/json" -d '{"question":"test question here"}'
done; echo
```

Expected: `429` appears once the limit is crossed.

- [ ] **Step 5: Delete the Render, Docker and tunnel scaffolding**

```bash
git rm render.yaml Dockerfile docker-compose.yml .dockerignore
git rm web-client/Dockerfile web-client/.dockerignore
git rm scripts/render_build.sh scripts/start_api.py
git rm scripts/trigger_render_ingestion.sh scripts/reingest_production.sh
git rm start-ngrok.sh start-ngrok-dual.sh start-cloudflared-tunnels.sh \
       start-mixed-tunnels.sh start-ssh.sh ngrok.yml
git rm docs/RENDER_DEPLOYMENT.md docs/DOCKER_ARCHITECTURE.md \
       docs/DOCKER_DEPLOYMENT.md docs/DOCKER_QUICKSTART.md docs/docker.md \
       docs/NGROK_FREE_TIER_FIX.md docs/STATIC_DOMAIN_SOLUTION.md \
       docs/MOBILE_ACCESS.md docs/QUICK_MOBILE_SETUP.md
git rm web-client/NGROK_SETUP.md web-client/NGROK_QUICK_FIX.md
```

- [ ] **Step 6: Update the Makefile**

Remove every `docker-*` target, `dev-start`, `dev-stop` and `clean-all`'s docker dependency. Update the test and lint targets for the new layout:

```makefile
test:  ## Run all tests
	cd api && pytest -v

test-cov:  ## Run tests with coverage report
	cd api && pytest --cov=src --cov-report=html --cov-report=term

lint:  ## Run code linting
	cd api && flake8 src/ tests/ && mypy src/

format:  ## Format code with black
	cd api && black src/ tests/

dev:  ## Run both services locally via the Vercel route table
	vercel dev

ingest:  ## Run article ingestion (local only)
	cd api && python scripts/ingest.py
```

- [ ] **Step 7: Rewrite the README deployment section**

Replace the Render and Docker instructions with:

```markdown
## Deployment

One Vercel project, two Services, one domain:

| Service | Root | Framework | Public paths |
|---------|------|-----------|--------------|
| `web`   | `web-client/` | Next.js 16 | everything not under `/api/` |
| `api`   | `api/`        | FastAPI, Python 3.12 | `/api/*` |

Routing is defined in `vercel.json`. The `/api/(.*)` rewrite must stay ahead of the
`/(.*)` catch-all, because rewrites are evaluated in order and routing into a service
is final.

**Environment variables:** `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`,
`ADMIN_API_KEY`, `VECTOR_DB_PROVIDER=qdrant`. `REDIS_URL` is injected by the Upstash
Marketplace integration.

**Local development:** `vercel dev` runs both services behind the same route table as
production. `make test` runs the Python suite.

**Ingestion is local-only:** `make ingest`. It reads `scraped_data/` — which lives
outside `api/` and is never bundled into the function — and upserts into Qdrant Cloud.

**Rate limiting** is configured in the Vercel WAF, not in application code.
```

Also correct the stale "Vector database (ChromaDB) integration" and "ChromaDB" mentions in the Features and Phase 2 sections to say Qdrant.

- [ ] **Step 8: Confirm no stale references survive**

```bash
grep -rniE "render\.com|onrender|ngrok|cloudflared|docker-compose|chromadb" \
  README.md Makefile docs/ api/ web-client/ \
  --include="*.md" --include="*.py" --include="*.ts" --include="*.tsx" --include="Makefile" \
  | grep -v "docs/superpowers/" || echo "clean"
```

Expected: `clean`. Design and plan documents under `docs/superpowers/` legitimately discuss Render and are excluded.

- [ ] **Step 9: Run the full suite one last time**

```bash
cd api && pytest -q 2>&1 | tail -5; cd ..
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "chore: remove Render, Docker and tunnel scaffolding

Production is verified on Vercel. Removes the Render config, both
Dockerfiles, docker-compose, the ngrok and cloudflared tunnel scripts,
and their documentation. Updates the Makefile and README for the
api/ + web-client/ Services layout."
```

- [ ] **Step 11: Suspend the Render services**

In the Render dashboard, suspend `care-beacon-api`, `care-beacon` and `care-beacon-redis`. Suspend rather than delete for the first week, so a rollback is still possible if something surfaces under real traffic.

---

## Post-implementation checklist

- [ ] `https://<domain>/api/health` returns 200 with `"vector_db": true`
- [ ] A question returns the same citations as Render did
- [ ] Statistics page renders the Vector DB pie charts
- [ ] Cost counters increase across separate requests and survive a redeploy
- [ ] `POST /api/v1/cache/clear` without `X-API-Key` returns 403
- [ ] The keepalive workflow has one green manual run
- [ ] `SITE_URL` repository variable is set
- [ ] Upstash Redis is attached and `REDIS_URL` is injected
- [ ] Vercel WAF rate limiting is configured
- [ ] Deployment Protection covers the Admin route
- [ ] Render services are suspended, not deleted
