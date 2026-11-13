---
claude_sessions:
  - "2026-11-11 · Chat UX upgrade · claude://claude.ai/epitaxy/local_5d471c4c-0a7f-42f1-9630-695d8199821b"
---

# Conversational Chat — Foundations and Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a streaming, cited chat page beside Search, with threads stored in Neon Postgres, prior turns fed back to the model, retrieval settings logged in the transcript, a daily spend cap, Langfuse tracing, and the eval runs that gate Phase 1.

**Architecture:** FastAPI gains `/api/v1/chat` (an SSE stream: `status*` → `citations` → `token*` → `done`) and `/api/v1/threads*` REST endpoints, backed by a `ThreadRepository` over `psycopg`. Retrieval reuses the existing `RetrievalEngine` (Qdrant + LLM rerank), split into a search step and a rank step so the stream can report progress. The Next.js client adds a Chat nav item with a gear panel, History drawer and `[n]` citation chips. Phases 2 (facts) and 3 (recall) get their own plans.

**Tech Stack:** Python 3.10 (local) / 3.12 (Vercel), FastAPI, `psycopg` 3, Neon Postgres via the Vercel Marketplace, Qdrant Cloud, Upstash Redis, OpenAI `gpt-4o-mini`, Langfuse Cloud (Hobby). Next.js 16, React 19, Radix UI, `react-markdown`, Vitest.

**Spec:** [docs/superpowers/specs/2026-11-02-conversational-chat-design.md](../specs/2026-11-02-conversational-chat-design.md)

## Global Constraints

- Python code must run on both 3.10.19 (local) and 3.12 (Vercel): no 3.11+ syntax or stdlib (`tomllib`, `except*`, `typing.Self`).
- `api/requirements.txt` ends this plan with **exactly 10** runtime packages: the existing 8 plus `psycopg[binary]` and `langfuse`, each pinned to an exact version. Every runtime package must be imported under `api/src/`.
- Test command: `cd api && /opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/ -q --continue-on-collection-errors`. Baseline is **245 passed, 0 failed**. Every task ends with the full suite green, and the count only goes up.
- No Docker. Database tests skip unless `TEST_DATABASE_URL` is set; they never read `DATABASE_URL`, so a pulled `.env.local` can't point tests at production.
- `/api/v1/ask` and the Search page keep working throughout. Their only behaviour change is the multi-source filter fix (Task 1) and the `cached` flag fix (Task 2).
- The chat path never reads or writes the answer cache (`RedisCache.get` / `RedisCache.set`).
- Thread ownership comes from the `X-Owner-Key` header (a lowercase UUID). A thread that doesn't belong to the caller gets **404, never 403**.
- Guaranteed writes: the user message (before the stream opens) and the assistant message (before the `done` frame). Best-effort, logged with `loguru` and swallowed: titling, Langfuse tracing and flushing.
- Every model role uses `gpt-4o-mini` in this plan.
- Daily spend cap: **$2.00 per UTC day** by default (`chat.daily_spend_cap_usd`), checked before any model work on `/api/v1/chat`; over the cap returns **HTTP 429** with `{"error": "DailyLimitReached", "message": ...}`.
- Context budget: prior turns capped at **6,000 characters**, newest kept first, always keeping the most recent turn.
- Configured sources, in this order: `BC Cancer`, `Canadian Cancer Society`, `Cleveland Clinic`. Default chat settings: all three sources, `min_similarity` 0.5 (matches the Search page default).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Work happens on a feature branch, never on `main`.

## Owner Steps (manual, outside the repo)

These can't be scripted; the tasks that need them say so and stop until they're done.

1. **Neon** (Task 6): approve the Marketplace install that `vercel integration add neon` starts, in the browser if the CLI hands off.
2. **Langfuse** (Task 4): create a Langfuse Cloud project on the Hobby plan, then add `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_HOST` to the Vercel project for Production and Preview, and to local `.env`.
3. **WAF rule** (Task 14): in the Vercel dashboard, add a rate-limit rule named `chat-rate-limit` on path `/api/v1/chat`, 20 requests per 60 seconds per IP, action 429.

## Review Focus

- **Client disconnects mid-answer.** The partial text is saved with `status = 'interrupted'`, the thread reopens normally, and the next turn works. Test in Task 14: `test_disconnect_persists_partial_as_interrupted`.
- **Redis is down.** The spend cap can't read the day's total, so it fails open with a logged warning; chat keeps working and `/api/v1/stats` doesn't raise. Test in Task 9: `test_cap_fails_open_when_redis_unavailable`.
- **Dragging the similarity slider.** One drag must not write dozens of transcript markers. The client commits settings only when the gear panel closes, and only if they changed; the server writes no marker for an unchanged update. Tests in Task 8 (`test_update_settings_unchanged_writes_no_marker`) and Task 15 (`settingsEqual` tests).
- **`localStorage` unavailable** (private window, blocked storage). The owner key falls back to an in-memory value for the session; chat works and History shows an empty list without an error. Test in Task 15: `getOwnerKey falls back when localStorage throws`.
- **Odd citation markers from the model.** `[7]` when there are 5 sources, or `[2]` inside a code block, render as literal text without crashing. Tests in Task 15 (`rehypeCitations` tests).

---

### Task 1: Multi-source filter on Search and `/api/v1/ask`

**Files:**
- Modify: `api/src/storage/qdrant_db.py:266-292` (filter construction in `search`)
- Create: `api/src/api/filters.py`
- Modify: `api/src/api/models.py` (`QuestionRequest.source`)
- Modify: `api/src/api/main.py` (`ask_question` filter building)
- Modify: `api/config/config.yaml` (add `retrieval.sources`)
- Modify: `web-client/lib/types.ts`, `web-client/components/search-interface.tsx` (`handleSearch`)
- Test: `api/tests/test_vector_db.py`, `api/tests/test_filters.py` (new), `api/tests/test_api.py`

**Interfaces:**
- Produces: `build_qdrant_filter(where: dict | None) -> Filter | None` in `qdrant_db.py`. A list value becomes `FieldCondition(key, match=MatchAny(any=[...]))`; a scalar stays `MatchValue`.
- Produces: `normalize_sources(source: str | list[str] | None, configured: list[str]) -> str | list[str] | None` in `api/src/api/filters.py`. Returns `None` for no filter, the bare string for one source (so single-source requests build the same filter as today), and a list for two or more. Raises `ValueError` naming any unknown source.
- Produces: `configured_sources() -> list[str]` in `filters.py`, reading `retrieval.sources` from config.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_filters.py
SOURCES = ["BC Cancer", "Canadian Cancer Society", "Cleveland Clinic"]

def test_none_and_empty_mean_no_filter():
    assert normalize_sources(None, SOURCES) is None
    assert normalize_sources([], SOURCES) is None

def test_all_sources_means_no_filter():
    assert normalize_sources(list(reversed(SOURCES)), SOURCES) is None

def test_single_source_stays_a_string():
    assert normalize_sources("BC Cancer", SOURCES) == "BC Cancer"
    assert normalize_sources(["BC Cancer"], SOURCES) == "BC Cancer"

def test_two_sources_become_a_deduplicated_list():
    assert normalize_sources(["Cleveland Clinic", "BC Cancer", "BC Cancer"], SOURCES) == ["BC Cancer", "Cleveland Clinic"]

def test_unknown_source_raises():
    with pytest.raises(ValueError, match="Mayo Clinic"):
        normalize_sources(["Mayo Clinic"], SOURCES)
```

```python
# api/tests/test_vector_db.py (append)
def test_list_filter_value_uses_match_any():
    f = build_qdrant_filter({"source": ["BC Cancer", "Cleveland Clinic"]})
    assert isinstance(f.must[0].match, MatchAny)
    assert f.must[0].match.any == ["BC Cancer", "Cleveland Clinic"]

def test_scalar_filter_value_still_uses_match_value():
    f = build_qdrant_filter({"source": "BC Cancer"})
    assert isinstance(f.must[0].match, MatchValue)

def test_no_filter_returns_none():
    assert build_qdrant_filter(None) is None
    assert build_qdrant_filter({}) is None
```

```python
# api/tests/test_api.py (append; reuse the module's client/mock_generator fixtures)
def test_ask_two_of_three_sources_filters_by_list(client, mock_generator):
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        r = client.post("/api/v1/ask", json={"question": "What is breast cancer?", "source": ["BC Cancer", "Cleveland Clinic"]})
    assert r.status_code == 200
    assert mock_generator.generate_answer.call_args.kwargs["filters"] == {"source": ["BC Cancer", "Cleveland Clinic"]}

def test_ask_single_string_source_still_accepted(client, mock_generator):
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        client.post("/api/v1/ask", json={"question": "What is breast cancer?", "source": "BC Cancer"})
    assert mock_generator.generate_answer.call_args.kwargs["filters"] == {"source": "BC Cancer"}

def test_ask_unknown_source_is_422(client, mock_generator):
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        r = client.post("/api/v1/ask", json={"question": "What is breast cancer?", "source": ["Mayo Clinic"]})
    assert r.status_code == 422
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `cd api && /opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/test_filters.py tests/test_vector_db.py tests/test_api.py -q`
Expected: FAIL (`ImportError` for `normalize_sources` / `build_qdrant_filter`; the `/ask` list test fails validation).

- [ ] **Step 3: Implement**

Extract the existing filter loop in `QdrantDatabase.search` into module-level `build_qdrant_filter`, keeping the `$and` branch, and branch on `isinstance(value, list)` for `MatchAny`. Add `retrieval.sources` (the three names, in the constrained order) to `config.yaml`. Change `QuestionRequest.source` to `Optional[Union[str, List[str]]]`. In `ask_question`, call `normalize_sources`; on `ValueError` raise `HTTPException(422)`; set `filters["source"]` only when the result isn't `None`. In `search-interface.tsx`, send `source: selectedSources` whenever fewer than all three are selected, and widen `QuestionRequest.source` in `types.ts` to `string | string[]`.

- [ ] **Step 4: Run the full suite**

Run: the global test command. Expected: all pass, count ≥ 245 + 11.

- [ ] **Step 5: Commit**

```bash
git add api/src/storage/qdrant_db.py api/src/api/filters.py api/src/api/models.py api/src/api/main.py api/config/config.yaml api/tests/ web-client/lib/types.ts web-client/components/search-interface.tsx
git commit -m "fix: filter by any combination of sources on /api/v1/ask"
```

---

### Task 2: Correct the `cached` flag and remove the dead stderr filter

**Files:**
- Modify: `api/src/generation/models.py` (`GeneratedAnswer`), `api/src/caching/redis_cache.py` (`_deserialize_answer`), `api/src/api/main.py` (remove lines 16-33; `was_cached`)
- Test: `api/tests/test_caching.py`, `api/tests/test_api.py`

**Interfaces:**
- Produces: `GeneratedAnswer.cached: bool = False`; `RedisCache._deserialize_answer` sets it `True`.

- [ ] **Step 1: Write the failing tests**

```python
# test_caching.py
def test_deserialized_answer_is_marked_cached(...):  # build via _serialize_answer → _deserialize_answer
    assert restored.cached is True

# test_api.py
def test_metadata_cached_reflects_this_request_not_history(client, mock_generator, mock_answer):
    mock_generator.cache.get_stats.return_value = {"cache_hits": 99}
    mock_answer.cached = False
    with patch("src.api.main.get_answer_generator", return_value=mock_generator):
        r = client.post("/api/v1/ask", json={"question": "What is breast cancer?"})
    assert r.json()["metadata"]["cached"] is False

def test_stderr_is_not_wrapped():
    import sys, src.api.main  # noqa: F401
    assert type(sys.stderr).__name__ != "FilteredStderr"
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `cd api && /opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/test_caching.py tests/test_api.py -q`
Expected: FAIL on all three.

- [ ] **Step 3: Implement**

Add the field, set it in `_deserialize_answer`, use `answer.cached` for `metadata["cached"]`, and delete the `ANONYMIZED_TELEMETRY` line and the `FilteredStderr` class and assignment.

- [ ] **Step 4: Run the full suite.** Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/src/generation/models.py api/src/caching/redis_cache.py api/src/api/main.py api/tests/
git commit -m "fix: report cached per request; drop dead ChromaDB stderr filter"
```

---

### Task 3: Model roles in config, and the zero-temperature bug

**Files:**
- Modify: `api/config/config.yaml` (`llm.models`), `api/src/config_loader.py`, `api/src/generation/llm_client.py`, `api/src/retrieval/reranker.py`, `api/src/generation/answer_generator.py`
- Test: `api/tests/test_config.py`, `api/tests/test_llm_client.py`

**Interfaces:**
- Produces: `get_model(role: str) -> str` in `config_loader.py`, roles `"generation" | "rerank" | "utility"`, read from `llm.models.<role>`, falling back to `llm.model`. All three default to `gpt-4o-mini`.
- `LLMReranker.__init__(llm_client=None, model: str | None = None)` defaults to `get_model("rerank")`.

- [ ] **Step 1: Write the failing tests**

```python
# test_config.py
def test_each_role_defaults_to_gpt_4o_mini():
    for role in ("generation", "rerank", "utility"):
        assert get_model(role) == "gpt-4o-mini"

def test_unknown_role_raises():
    with pytest.raises(KeyError):
        get_model("vision")

# test_llm_client.py — temperature=0.0 must reach the API, not be replaced by the 0.1 default
def test_zero_temperature_is_passed_through(mock_openai):
    client.generate("s", "u", temperature=0.0)
    assert mock_openai.chat.completions.create.call_args.kwargs["temperature"] == 0.0
```

- [ ] **Step 2: Run them and confirm they fail.** Expected: `ImportError` for `get_model`; temperature asserts 0.1.

- [ ] **Step 3: Implement**

Add `llm.models: {generation, rerank, utility}` to `config.yaml`. In `LLMClient.generate`, replace `temperature or self.temperature` and `max_tokens or self.max_tokens` with `is None` checks. Remove the hardcoded `"gpt-4o-mini"` default from `LLMReranker`, and have `AnswerGenerator` build its client with `get_model("generation")`.

- [ ] **Step 4: Run the full suite.** Expected: all pass.

- [ ] **Step 5: Commit** — `git commit -m "refactor: configure model per role; pass temperature 0 through"`

---

### Task 4: Langfuse tracing, off by default, on `/api/v1/ask`

Needs owner step 2 for the live check in Step 6 only; Steps 1-5 run without keys.

**Files:**
- Modify: `api/requirements.txt` (add `langfuse==<current 3.x, exact>`)
- Create: `api/src/observability/__init__.py`, `api/src/observability/tracing.py`
- Modify: `api/src/generation/llm_client.py` (client construction), `api/src/retrieval/retrieval_engine.py` (spans), `api/src/api/main.py` (`ask_question`)
- Test: `api/tests/test_tracing.py`

**Interfaces:**
- Produces, in `tracing.py` (the only module that imports `langfuse`; implement against the installed SDK's docs, not from memory):
  - `tracing_enabled() -> bool` — true only when all three `LANGFUSE_*` variables are set.
  - `get_openai_client(api_key: str) -> openai.OpenAI` — the Langfuse-wrapped client when enabled, a plain `OpenAI` otherwise.
  - `request_trace(name: str, *, metadata: dict, session_id: str | None = None, user_id: str | None = None)` — a context manager yielding a handle with `.update(output: Any = None, metadata: dict | None = None) -> None`.
  - `span(name: str, *, input: Any = None)` — a context manager yielding the same handle type.
  - `flush() -> None`.
  - When disabled, every function is a no-op that returns no-op handles. When enabled, any SDK exception is logged and swallowed; tracing never raises into the caller.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_tracing.py
def test_disabled_without_keys(monkeypatch):
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    assert tracing_enabled() is False
    with request_trace("ask", metadata={}) as t:
        t.update(output="x")          # no error
    with span("search") as s:
        s.update(output=[])
    flush()                           # no error, no network
    assert type(get_openai_client("sk-test")).__module__.startswith("openai")

def test_sdk_errors_are_swallowed(monkeypatch):
    # enabled, with the SDK client patched to raise on every call
    ...
    with request_trace("ask", metadata={}) as t:
        t.update(output="x")
    flush()                           # must not raise
```

- [ ] **Step 2: Run them and confirm they fail.** Expected: `ModuleNotFoundError: src.observability`.

- [ ] **Step 3: Implement** `tracing.py`; build `LLMClient.client` with `get_openai_client`; wrap embedding, vector search and rerank in `RetrievalEngine.retrieve` with `span("embed")`, `span("vector_search")`, `span("rerank")`; wrap `ask_question` in `request_trace("ask", metadata={"endpoint": "/api/v1/ask", "filters": ..., "min_similarity": ...})` with `flush()` in a `finally`.

- [ ] **Step 4: Run the full suite.** Expected: all pass with no `LANGFUSE_*` set.

- [ ] **Step 5: Commit** — `git commit -m "feat: optional Langfuse tracing for /api/v1/ask"`

- [ ] **Step 6: Live check (after owner step 2).** Deploy a preview (`vercel deploy`), ask one question on the Search page, and confirm a trace named `ask` with spans `embed`, `vector_search`, `rerank` and one generation appears in Langfuse. Record the trace URL in the PR description.

---

### Task 5: Search baseline experiment

**Files:**
- Create: `evaluation/langfuse/__init__.py`, `evaluation/langfuse/judges.py`, `evaluation/langfuse/datasets.py`, `evaluation/langfuse/run_experiment.py`, `evaluation/langfuse/test_judges.py`
- Create: `evaluation/results/<run-date>-search-baseline.md`
- Modify: `evaluation/README.md` (how to run)

Judges run in our own code and post their scores to Langfuse, rather than being configured in the Langfuse UI. That keeps the judge prompts versioned and reviewable. It still satisfies the spec: judging runs only on datasets, spends the owner's OpenAI key, and sits outside the chat spend cap.

**Interfaces:**
- Produces, in `judges.py`: `@dataclass Score(value: int, reason: str)` with `value` 0 or 1; `judge_grounded(question: str, answer: str, sources_text: str) -> Score`; `judge_refusal_referral(question: str, answer: str) -> Score`; `judge_followup_resolved(turns: list[str], answer: str, expected_reference: str) -> Score`. Each makes one `gpt-4o-mini` call at temperature 0 with a JSON response format `{"score": 0|1, "reason": str}`; a malformed reply becomes `Score(0, "unparseable judge reply: ...")`.
- Produces, in `datasets.py`: `upsert_dataset(name: str, items: list[dict]) -> None`, idempotent by item `id`.
- Produces: `run_experiment.py --dataset {search-baseline|followups|safety} --base-url URL --run-name NAME`. It runs each item, links each item's output to a dataset run, posts scores, and prints aggregate pass rates. `search-baseline` reads `evaluation/ragas/test_questions.json` (78 items) and calls `/api/v1/ask` with `include_full_text: true`.

- [ ] **Step 1: Write failing tests for judge parsing** (mock the OpenAI client): a valid JSON reply → that score; `{"score": 2}` → `Score(0, ...)`; non-JSON → `Score(0, ...)`.

- [ ] **Step 2: Run them and confirm they fail.** Run: `/opt/anaconda3/envs/care-beacon/bin/python -m pytest evaluation/langfuse/test_judges.py -q`. Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `judges.py`, `datasets.py` and `run_experiment.py` (the `search-baseline` path only; the others arrive in Task 17). `langfuse` is already in the dev environment via `requirements.txt`.

- [ ] **Step 4: Run the judge tests.** Expected: PASS.

- [ ] **Step 5: Run the baseline** against production (`--base-url https://care-beacon-health.vercel.app --run-name search-baseline-<date>`). Write `evaluation/results/<date>-search-baseline.md` with the run name, Langfuse run URL, item count, grounded pass rate, and median `/ask` latency.

- [ ] **Step 6: Commit** — `git commit -m "eval: Langfuse experiment runner, judges, and Search baseline"`

---

### Task 6: Neon Postgres, migrations, and the health check

Needs owner step 1.

**Files:**
- Modify: `api/requirements.txt` (add `psycopg[binary]==<current 3.x, exact>`)
- Create: `api/src/db/__init__.py`, `api/src/db/connection.py`
- Create: `api/migrations/001_threads_messages.sql`, `api/scripts/migrate.py`
- Create: `api/tests/db/__init__.py`, `api/tests/db/conftest.py`, `api/tests/db/test_migrations.py`
- Modify: `api/src/api/main.py` (`health_check`), `api/tests/test_api.py`, `Makefile` (`migrate`, `test-db` targets)

**Interfaces:**
- Produces, in `connection.py`: `database_url() -> str | None` (reads `DATABASE_URL`, which must be Neon's **pooled** string); `connect() -> psycopg.Connection` (`row_factory=dict_row`; raises `DatabaseUnavailable` when the URL is unset or unreachable); `db_healthy() -> bool` (runs `SELECT 1`, never raises); `class DatabaseUnavailable(Exception)`.
- Produces, in `scripts/migrate.py`: `apply_migrations(conn, migrations_dir: Path) -> list[str]` returns the filenames it applied, records them in `schema_migrations(filename text primary key, applied_at timestamptz)`, and is idempotent. The CLI connects with `DATABASE_URL_UNPOOLED` when set, else `DATABASE_URL`.
- Schema (`001_threads_messages.sql`), as the spec defines it, minus columns owned by later phases:
  - `threads(id text pk, owner_key text not null, title text, settings jsonb not null, created_at timestamptz not null default now(), updated_at timestamptz not null default now())`, index on `owner_key`.
  - `messages(id text pk, thread_id text not null references threads(id) on delete cascade, role text not null check (role in ('user','assistant','settings')), content text not null, citations jsonb, settings_delta jsonb, status text not null default 'complete' check (status in ('complete','interrupted')), tokens int, cost numeric, created_at timestamptz not null default now())`, index on `(thread_id, created_at)`.
  - Phase 2 adds `memories` and `owner_settings`; Phase 3 adds the summary columns and `CREATE EXTENSION vector`.
- Produces, in `tests/db/conftest.py`:
  - `migrations_dir` (session): the `Path` to `api/migrations`.
  - `raw_conn` (session): skips when `TEST_DATABASE_URL` is unset. Otherwise it connects, creates schema `test_<random>`, sets `search_path`, applies migrations, yields the connection, and drops the schema at teardown.
  - `db` (function): truncates `messages, threads` on `raw_conn` and yields a `connect` callable bound to the test schema, for `ThreadRepository`.

- [ ] **Step 1: Provision.** `vercel link` if needed, then `vercel integration add neon --yes --no-claim`. If it opens a browser or asks for terms, stop for owner step 1. Then `vercel env pull --yes` and confirm with `vercel env ls` that `DATABASE_URL` and `DATABASE_URL_UNPOOLED` exist. If the names differ, update `database_url()` and the migrate CLI to match, and note it in the PR.

- [ ] **Step 2: Write the failing tests**

```python
# tests/db/test_migrations.py
def test_migrations_create_tables_and_are_idempotent(raw_conn, migrations_dir):
    assert apply_migrations(raw_conn, migrations_dir) == []   # session fixture already applied them
    cols = {r["column_name"] for r in raw_conn.execute(
        "select column_name from information_schema.columns where table_name = 'messages'")}
    assert {"role", "status", "settings_delta", "citations"} <= cols

def test_role_check_rejects_unknown_role(db):
    ...  # insert a thread, then a message with role 'system' → psycopg.errors.CheckViolation

# test_api.py
def test_health_503_when_postgres_down(client, mock_generator):
    with patch("src.api.main.db_healthy", return_value=False), patch("src.api.main.create_vector_database"), \
         patch("src.api.main.get_answer_generator", return_value=mock_generator):
        r = client.get("/api/health")
    assert r.status_code == 503
    assert r.json()["services"]["postgres"] is False
```

- [ ] **Step 3: Run them and confirm they fail.** Run the global command (DB tests skip without `TEST_DATABASE_URL`), then `TEST_DATABASE_URL=<a Neon branch or local Postgres> make test-db`. Expected: FAIL.

- [ ] **Step 4: Implement** the connection module, migration file, migrate script, fixtures, and `services["postgres"] = db_healthy()` in `health_check`, which returns 503 if Qdrant *or* Postgres is down. Add `make migrate` and `make test-db`. Update existing health tests to patch `db_healthy`.

- [ ] **Step 5: Run both suites.** Expected: the global command passes with DB tests skipped; `make test-db` passes against a test database.

- [ ] **Step 6: Migrate production.** `make migrate`, run with the production unpooled URL from the pulled env. Expected: prints `001_threads_messages.sql`; a second run prints nothing.

- [ ] **Step 7: Commit** — `git commit -m "feat: Neon Postgres connection, migrations, and health check"`

---

### Task 7: Serverless streaming spike (go/no-go)

The spec names this as the riskiest assumption, so it comes before any chat code. Its code is throwaway and is reverted at the end of the task.

**Files:**
- Temporary: `api/src/api/spike.py`, mounted at `/api/v1/_spike/stream` only for this task.
- Create: `docs/superpowers/plans/2026-11-11-streaming-spike-findings.md`

- [ ] **Step 1: Build the probe.** A `StreamingResponse` over a sync generator that yields 10 SSE frames 300 ms apart, then inserts a row into a scratch table `spike_writes(id text, at timestamptz)`, then yields a final frame.

- [ ] **Step 2: Deploy a preview and test three things**, recording the evidence for each in the findings file:
  1. **No buffering.** `curl -N` shows frames arriving about 300 ms apart, not all at the end.
  2. **In-stream write completes.** After a full read, the row exists, every time across 5 runs.
  3. **Disconnect.** Kill `curl` after 3 frames. Record whether the generator's `GeneratorExit` handler runs, by having it insert a row marked `disconnected`.

- [ ] **Step 3: Decide and record.**
  - **Go**, if 1 and 2 hold: Tasks 13-14 proceed as written, with guaranteed writes inside the generator before the `done` frame. If 3 also holds, interrupted turns are saved from the `GeneratorExit` handler. If it doesn't, the client re-sends the partial text in a commit request (see the spec's fallback), and Task 14 grows a `POST /api/v1/threads/{id}/messages/{message_id}/commit` step.
  - **No-go**, if 1 or 2 fails: stop. Bring the findings back to the owner and revise the spec before continuing.

- [ ] **Step 4: Revert the probe, drop `spike_writes`, and commit only the findings file** — `git commit -m "docs: record serverless streaming spike findings"`

---

### Task 8: Thread repository

**Files:**
- Create: `api/src/chat/__init__.py`, `api/src/chat/models.py`, `api/src/chat/repository.py`
- Create: `api/tests/fakes.py` (`InMemoryThreadRepository`), `api/tests/db/test_repository.py`, `api/tests/test_fake_repository.py`

**Interfaces:**
- Produces, in `chat/models.py` (pydantic):
  - `ThreadSettings(sources: list[str], min_similarity: float)`, where `sources` is a non-empty subset of `configured_sources()` and `min_similarity` is in 0..1.
  - `Message(id, thread_id, role, content, citations: list[dict] | None, settings_delta: dict | None, status, tokens: int | None, cost: float | None, created_at: datetime)`.
  - `Thread(id, owner_key, title: str | None, settings: ThreadSettings, created_at, updated_at)`.
  - `ThreadSummary(id, title: str | None, last_activity_at: datetime, message_count: int)`.
- Produces `class ThreadNotFound(Exception)`, and `class ThreadRepository` constructed with `connect: Callable[[], psycopg.Connection]`, with these methods (each opens its own connection; every owner-scoped one matches on `owner_key`):
  - `create_thread(owner_key: str, settings: ThreadSettings) -> Thread`
  - `get_thread(thread_id: str, owner_key: str) -> Thread | None`
  - `list_threads(owner_key: str) -> list[ThreadSummary]`, newest activity first (`coalesce(max(m.created_at), t.created_at)`)
  - `list_messages(thread_id: str) -> list[Message]`, oldest first
  - `append_message(thread_id: str, role: str, content: str, *, citations=None, settings_delta=None, status="complete", tokens=None, cost=None) -> Message` (also bumps `threads.updated_at`)
  - `rename_thread(thread_id: str, owner_key: str, title: str) -> bool`
  - `set_title_if_empty(thread_id: str, title: str) -> None`
  - `delete_thread(thread_id: str, owner_key: str) -> bool`
  - `update_settings(thread_id: str, owner_key: str, settings: ThreadSettings) -> Message | None` raises `ThreadNotFound` if not owned, returns `None` without writing if unchanged, and otherwise updates `threads.settings` and appends a `'settings'` message in the **same transaction**. The message's `content` is empty and its `settings_delta` is `{"before": {...}, "after": {...}}`.
- IDs: `thr_` / `msg_` + `uuid4().hex`.
- `InMemoryThreadRepository` in `tests/fakes.py` has the same public methods and is used by service and route tests.

- [ ] **Step 1: Write the failing tests.** Run the same behaviour tests against both implementations: parametrize one test module over `[InMemoryThreadRepository, ThreadRepository]`, where the DB variant is skipped without `TEST_DATABASE_URL`. Cover:
  - `test_other_owner_cannot_read_rename_delete_or_update` — returns `None` / `False` / raises `ThreadNotFound`.
  - `test_list_threads_orders_by_latest_message`.
  - `test_delete_cascades_messages`.
  - `test_update_settings_writes_marker_with_before_and_after`.
  - `test_update_settings_unchanged_writes_no_marker` (Review Focus).
  - `test_set_title_if_empty_does_not_overwrite_a_rename`.

- [ ] **Step 2: Run them and confirm they fail.** Expected: `ModuleNotFoundError: src.chat`.

- [ ] **Step 3: Implement** the models, repository and fake.

- [ ] **Step 4: Run the global suite and `make test-db`.** Expected: all pass.

- [ ] **Step 5: Commit** — `git commit -m "feat: owner-scoped thread repository"`

---

### Task 9: Daily spend cap

**Files:**
- Modify: `api/src/caching/stats_store.py`, `api/src/generation/llm_client.py`, `api/src/embeddings/embedding_generator.py`, `api/config/config.yaml` (`chat.daily_spend_cap_usd: 2.0`)
- Create: `api/src/chat/spend.py`
- Test: `api/tests/test_stats_store.py`, `api/tests/test_spend.py`

**Interfaces:**
- Produces, on `StatsStore`: `incr_daily_cost(amount: float, day: date | None = None) -> None`, where key `{prefix}cost:{YYYY-MM-DD}` uses the UTC date and expires after 172,800 s; and `get_daily_cost(day: date | None = None) -> float | None`, which returns `None` when Redis is unavailable, distinct from `0.0`.
- `LLMClient` (every call path, including Task 10's streaming) and `EmbeddingGenerator` call `incr_daily_cost` wherever they already call `incr_float(... cost ...)`.
- Produces, in `chat/spend.py`: `daily_cap_usd() -> float` and `cap_reached(stats_store: StatsStore) -> bool`. It's true when today's cost is at or above the cap, and false with a warning logged when the cost is `None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_daily_cost_uses_utc_date_key_and_ttl(fake_redis):
    store.incr_daily_cost(0.5, day=date(2026, 11, 11))
    assert fake_redis.ttl("care_beacon:cost:2026-11-11") == 172800

def test_cap_reached_at_exact_cap(store_with_cost_2_00):
    assert cap_reached(store_with_cost_2_00) is True

def test_cap_not_reached_below(store_with_cost_1_99):
    assert cap_reached(store_with_cost_1_99) is False

def test_cap_fails_open_when_redis_unavailable(caplog):          # Review Focus
    assert cap_reached(StatsStore(None)) is False
    assert "spend cap" in caplog.text.lower()
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "feat: per-UTC-day spend counter and chat spend cap"`

---

### Task 10: Message lists and streaming in `LLMClient`

**Files:**
- Modify: `api/src/generation/llm_client.py`
- Test: `api/tests/test_llm_client.py`

**Interfaces:**
- Produces: `LLMClient.generate_messages(messages: list[dict], max_tokens: int | None = None, temperature: float | None = None, model: str | None = None) -> dict`. It returns the same dict shape as `generate()`, and `generate()` delegates to it with its two messages.
- Produces: `LLMClient.generate_stream(messages: list[dict], max_tokens: int | None = None, temperature: float | None = None, model: str | None = None) -> LLMStream`. `LLMStream` iterates `str` deltas, and its `.usage: dict | None` is `{"tokens_used": {input, output, total}, "cost": float, "model": str}` once iteration finishes. It calls the API with `stream=True, stream_options={"include_usage": True}`. It retries only the opening `create` call; once a delta has been yielded, errors propagate. Costs and counters (including the daily cost) are recorded when the usage chunk arrives.

- [ ] **Step 1: Write failing tests** with a mocked OpenAI client whose stream yields chunks `"Hel"`, `"lo"`, then a usage-only chunk:
  - `test_stream_yields_deltas_and_sets_usage` — joined text `"Hello"`, usage totals and cost computed from config prices.
  - `test_stream_records_daily_cost`.
  - `test_stream_error_after_first_delta_propagates_without_retry` — `create` called once.
  - `test_generate_delegates_to_generate_messages`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass, including the existing `generate` tests unchanged.
- [ ] **Step 5: Commit** — `git commit -m "feat: message-list and streaming generation in LLMClient"`

---

### Task 11: Chat prompts, history and query rewriting

**Files:**
- Create: `api/config/prompts_chat.yaml`, `api/src/chat/prompt.py`
- Test: `api/tests/test_chat_prompt.py`

**Interfaces:**
- Produces, in `chat/prompt.py`:
  - `load_chat_prompts() -> dict` loads `prompts_chat.yaml` and adds `no_context_found` and `medical_disclaimer` from `prompts.yaml`, unchanged.
  - `format_history(messages: list[Message], max_chars: int = 6000) -> str` renders `You: …` / `Assistant: …` lines. It skips `'settings'` rows, walks back from the newest, stops before exceeding `max_chars`, and always keeps the newest turn.
  - `format_sources(results: list[RetrievalResult]) -> str` renders `[n] {article_title} — {section}\n{text}` blocks, numbered from 1.
  - `build_chat_messages(question: str, results: list[RetrievalResult], history: list[Message], prompts: dict) -> list[dict]` returns `[system, user]`. The user message is the sectioned prompt: `Earlier in this conversation:` (only when history is non-empty), then `Sources:`, then the instruction, then `Question:` with the question verbatim.
  - `rewrite_query(llm: LLMClient, question: str, history: list[Message], prompts: dict) -> str` uses at most the last 4 non-settings turns and the `utility` model. It returns `question` unchanged when history is empty, when the call raises, or when the reply is blank.
  - `fallback_title(question: str) -> str` takes the first 6 words, capped at 60 characters. `clean_title(raw: str) -> str` strips surrounding quotes and trailing punctuation, and caps at 60 characters.
  - `generate_title(llm: LLMClient, question: str, prompts: dict) -> str` uses the utility model and falls back to `fallback_title` on any error or blank result.
- `prompts_chat.yaml` keys: `system_prompt`, `sources_instruction`, `rewrite_prompt`, `title_prompt`. The wording of the last three is the implementer's. `system_prompt` is fixed as:

```yaml
system_prompt: |
  You are a medical information assistant for Care-Beacon. You answer questions about cancer in an ongoing conversation, using educational materials from BC Cancer, the Canadian Cancer Society and Cleveland Clinic.

  Guidelines:
  1. Answer ONLY from the numbered Sources in the user message, and cite every factual claim inline as [n] using those numbers.
  2. "Earlier in this conversation" is context for understanding the question. Never cite it and never treat it as a source.
  3. If the Sources don't contain enough information to answer, say so plainly instead of guessing.
  4. When the Sources list multiple items (tests, symptoms, treatments, side effects, etc.), include ALL of them.
  5. Use simple, patient-friendly language
  6. Be empathetic and supportive in your tone
  7. Never provide personal medical advice or diagnoses
  8. Always remind patients to consult with healthcare providers
```

- [ ] **Step 1: Write failing tests**, including:
  - `test_system_prompt_keeps_guidelines_5_to_8_verbatim` — asserts the four lines from `prompts_eval.yaml` appear unchanged.
  - `test_no_history_section_on_first_turn`.
  - `test_history_budget_keeps_newest_and_drops_oldest`.
  - `test_history_always_keeps_last_turn_even_if_over_budget`.
  - `test_settings_rows_excluded_from_history`.
  - `test_question_passed_verbatim_not_rewritten`.
  - `test_rewrite_returns_question_when_llm_raises`.
  - `test_rewrite_skipped_on_first_turn` — the LLM is not called.
  - `test_title_falls_back_on_error`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "feat: chat prompt builder, history budget and query rewrite"`

---

### Task 12: Split retrieval into search and rank

**Files:**
- Modify: `api/src/retrieval/retrieval_engine.py`
- Test: `api/tests/test_retrieval.py`

**Interfaces:**
- Produces: `RetrievalEngine.make_query(query_text: str, max_results: int | None = None, min_similarity: float | None = None, filters: dict | None = None) -> Query`, extracted from `retrieve_text`.
- Produces: `RetrievalEngine.search_candidates(query: Query) -> list[RetrievalResult]`, which embeds, runs the vector search (fetching `max_results * 6` when the reranker is on) and applies the loose pre-filter.
- Produces: `RetrievalEngine.rank_candidates(query: Query, candidates: list[RetrievalResult]) -> list[RetrievalResult]`, which reranks and post-filters, or filters only when the reranker is off.
- `retrieve(query)` becomes `rank_candidates(query, search_candidates(query))` wrapped in a `RetrievedContext`, with identical behaviour.

- [ ] **Step 1: Write the failing test** `test_retrieve_equals_search_then_rank` (mocked embedder, DB and reranker; the two paths give equal results in the same order), plus `test_rank_candidates_without_reranker_filters_by_threshold`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all existing retrieval tests pass unchanged.
- [ ] **Step 5: Commit** — `git commit -m "refactor: expose retrieval search and rank as separate steps"`

---

### Task 13: Thread REST endpoints

**Files:**
- Create: `api/src/api/chat_routes.py` (an `APIRouter`, included in `main.py`), `api/src/api/chat_models.py`
- Test: `api/tests/test_chat_routes.py`

**Interfaces:**
- Consumes: `ThreadRepository` and models (Task 8), `configured_sources` (Task 1).
- Produces: `require_owner_key(x_owner_key: str | None = Header(None, alias="X-Owner-Key")) -> str`, which returns 400 if missing or not a lowercase UUID; and `get_repository() -> ThreadRepository`, a dependency that tests override with `InMemoryThreadRepository`. When the database is unavailable, every endpoint here returns **503**.
- Endpoints (all owner-scoped; a thread that isn't the caller's → **404**):
  - `GET /api/v1/threads` → `{"threads": [{"id", "title", "last_activity_at", "message_count"}]}`
  - `GET /api/v1/threads/{thread_id}` → `{"id", "title", "settings", "messages": [Message]}`
  - `PATCH /api/v1/threads/{thread_id}` body `{"title": str}` → trimmed and capped at 200 characters; blank → 422; returns `{"id", "title"}`
  - `DELETE /api/v1/threads/{thread_id}` → `{"ok": true}`
  - `PATCH /api/v1/threads/{thread_id}/settings` body `ThreadSettings` → `{"settings": ThreadSettings, "marker": Message | null}`; an unknown source or an empty list → 422

- [ ] **Step 1: Write failing tests**: 400 without the header; 400 for a malformed header; 404 for another owner's thread on every endpoint; rename blank → 422; settings unchanged → `marker` is null; settings changed → `marker.settings_delta` has `before` and `after`; repository raising `DatabaseUnavailable` → 503.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "feat: thread list, detail, rename, delete and settings endpoints"`

---

### Task 14: The `/api/v1/chat` stream

Needs Task 7's go decision. Owner step 3 is done before this task's PR merges.

**Files:**
- Create: `api/src/chat/service.py`, `api/src/chat/sse.py`
- Modify: `api/src/api/chat_routes.py`, `api/src/api/chat_models.py`, `vercel.json` (an `api` service `maxDuration` of 60 s for now; Task 17 confirms it)
- Test: `api/tests/test_chat_service.py`, `api/tests/test_chat_routes.py`

**Interfaces:**
- Consumes: Tasks 8-13.
- Produces, in `chat/sse.py`: `frame(event: str, data: dict) -> str`, giving `event: {event}\ndata: {compact json}\n\n`.
- Request `ChatRequest(thread_id: str | None, message: str (3..500 chars), settings: ThreadSettings | None, include_full_text: bool = False)`. `settings` is used only when creating a thread, and defaults to all sources with `min_similarity` 0.5. For an existing thread, the stored settings apply.
- Produces, in `chat/service.py`: `ChatService(repository, retrieval_engine, llm_client, prompts, stats_store, max_context_chunks: int)` with `start_turn(owner_key: str, request: ChatRequest) -> tuple[Thread, list[Message], bool]`, which returns `(thread, prior_messages, is_new)`, raises `ThreadNotFound`, and appends the user message; and `stream_turn(thread, prior_messages, is_new, question, include_full_text) -> Iterator[str]`.
- Frame contract, in order:
  1. `status {"stage": "rewriting"}` — only when prior turns exist.
  2. `status {"stage": "searching", "query": <rewritten or original>}`
  3. `status {"stage": "ranking"}`
  4. `citations {"citations": [{"n", "article_title", "section", "url", "source", "similarity_score", "excerpt", "full_text"?}]}` — `excerpt` capped at 500 characters; `full_text` only when requested; capped at `max_context_chunks` results, the same cap `/ask` uses.
  5. `token {"text"}` — repeated.
  6. `done {"thread_id", "message_id", "disclaimer"}`
  - Any point: `error {"message"}`, which ends the stream.
  - With no results: `citations` with `[]`, then one `token` carrying `no_context_found`, then `done`, and no generation call.
- Guarantees: the user message is written in `start_turn`. The assistant message (content, citations, tokens, cost) is written **before** `done` is yielded. On `GeneratorExit`, or on an exception after tokens have started, the partial text is saved with `status='interrupted'` (empty partials aren't saved). After `done`: `set_title_if_empty(generate_title(...))` when `is_new`, then the trace update and `flush()`, each wrapped in try/except with a logged warning.
- Endpoint `POST /api/v1/chat`: owner key → `cap_reached` → 429 JSON (`{"error": "DailyLimitReached", "message": "Today's chat limit has been reached. It resets at midnight UTC."}`) → `start_turn` (404 / 503 as in Task 13) → `StreamingResponse(media_type="text/event-stream")` with headers `X-Thread-Id`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`. The whole turn runs inside `request_trace("chat", metadata={"endpoint", "thread_id", "settings"}, session_id=thread.id, user_id=owner_key)`. The answer cache is not touched.

- [ ] **Step 1: Write failing tests** using `InMemoryThreadRepository`, a fake retrieval engine, and a fake `LLMClient` whose stream yields scripted deltas:
  - `test_first_turn_frame_order` — `searching, ranking, citations, token+, done`; no `rewriting`.
  - `test_follow_up_emits_rewriting_and_searches_rewritten_query`.
  - `test_assistant_message_persisted_before_done` — at the moment the `done` frame is produced, the repository already holds the assistant message.
  - `test_no_results_streams_no_context_text_without_generation`.
  - `test_disconnect_persists_partial_as_interrupted` (Review Focus) — close the generator after two tokens.
  - `test_llm_error_mid_stream_emits_error_and_saves_partial`.
  - `test_title_failure_does_not_affect_stream`.
  - `test_answer_cache_never_used` — a `RedisCache` mock's `get`/`set` are never called.
  - Route tests: `test_spend_cap_returns_429_before_any_model_call`, `test_chat_404_for_other_owners_thread`, `test_chat_sets_thread_id_header_for_new_thread`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.** Use a sync generator (FastAPI iterates it in a threadpool), with the retrieval and LLM calls made between yields.
- [ ] **Step 4: Run the full suite and `make test-db`.** Expected: all pass.
- [ ] **Step 5: Smoke-test on a preview deploy.** `curl -N -H 'X-Owner-Key: <uuid>' -H 'Content-Type: application/json' -d '{"message":"What are the side effects of radiation therapy?"}' <preview>/api/v1/chat`. Expected: frames arrive in order, incrementally; `GET /api/v1/threads/<id>` shows the user and assistant messages and a title.
- [ ] **Step 6: Commit** — `git commit -m "feat: streaming /api/v1/chat with guaranteed persistence"`

---

### Task 15: Web client — libraries and tests

**Files:**
- Modify: `web-client/package.json` (add `react-markdown`, `remark-gfm`, `@radix-ui/react-popover`; devDeps `vitest`, `jsdom`; script `"test": "vitest run"`)
- Create: `web-client/vitest.config.ts`, `web-client/lib/owner.ts`, `web-client/lib/sse.ts`, `web-client/lib/chat-api.ts`, `web-client/lib/settings.ts`, `web-client/lib/rehype-citations.ts`
- Modify: `web-client/lib/types.ts` (`ThreadSettings`, `ThreadSummary`, `ThreadDetail`, `ChatMessage`, `ChatCitation`, `SettingsDelta`)
- Test: `web-client/lib/*.test.ts`

**Interfaces:**
- `owner.ts`: `getOwnerKey(): string` reads or creates `care-beacon-owner-key` in `localStorage` with `crypto.randomUUID()`, falling back to a module-level in-memory key when storage throws.
- `sse.ts`: `parseSSE(buffer: string): { events: { event: string; data: unknown }[]; rest: string }` handles frames split across chunks.
- `settings.ts`: `ALL_SOURCES` (the three names, in order); `DEFAULT_SETTINGS = { sources: ALL_SOURCES, min_similarity: 0.5 }`; `settingsEqual(a, b): boolean`, which ignores source order; `describeSettingsChange(delta: SettingsDelta): { sources: string; similarity: string }`, the text for the marker card, e.g. sources `"BC Cancer, Canadian Cancer Society (was + Cleveland Clinic)"` and similarity `"55% (was 50%)"`, or `"unchanged"`.
- `chat-api.ts`: `listThreads()`, `getThread(id)`, `renameThread(id, title)`, `deleteThread(id)`, `updateThreadSettings(id, settings)`, each sending `X-Owner-Key`; and `streamChat(req: { threadId: string | null; message: string; settings?: ThreadSettings }, handlers: { onStatus(stage, query?), onCitations(c), onToken(t), onDone(d), onError(message) }, signal?: AbortSignal): Promise<{ threadId: string }>`. A 429 calls `onError` with the server's `message`.
- `rehype-citations.ts`: `rehypeCitations(options: { count: number })` replaces `[n]` text with `<cite data-cite="n">` only when `1 ≤ n ≤ count`, and never inside `code` or `pre`.

- [ ] **Step 1: Write failing Vitest tests**, including:
  - `getOwnerKey falls back when localStorage throws` (Review Focus; jsdom with a throwing `localStorage` stub).
  - `parseSSE handles a frame split across two chunks`.
  - `settingsEqual ignores source order`.
  - `settingsEqual false when similarity differs`.
  - `describeSettingsChange shows was-values`.
  - `rehypeCitations leaves [7] literal when count is 5` (Review Focus).
  - `rehypeCitations ignores [2] inside code` (Review Focus).
  - `streamChat surfaces the 429 message` (mocked `fetch`).
- [ ] **Step 2: Run them and confirm they fail.** Run: `cd web-client && npm install && npm test`. Expected: FAIL (missing modules).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run `npm test`, `npm run lint` and `npm run build`.** Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "feat(web): chat client libraries with tests"`

---

### Task 16: Web client — the Chat page

**Files:**
- Create: `web-client/components/ui/popover.tsx`, `web-client/components/ui/sheet.tsx` (on `@radix-ui/react-dialog`)
- Create: `web-client/components/chat/chat.tsx`, `transcript.tsx`, `assistant-message.tsx`, `citation-chip.tsx`, `settings-panel.tsx`, `settings-marker.tsx`, `history-sheet.tsx`
- Modify: `web-client/app/page.tsx` (`Page` becomes `"search" | "chat" | "stats"`; a **Chat** nav item between Search and Statistics; Search stays the default page)

**Interfaces:**
- Consumes: Task 15.
- Behaviour, from the spec's chat surface section:
  - The header has **History**, **＋ New chat** and **⚙ Retrieval**.
  - The settings panel uses the existing `Checkbox` and `Slider`, and the last remaining source can't be unchecked. On panel close, if `!settingsEqual(before, after)`: with a thread, call `updateThreadSettings` and append the returned marker; without a thread yet, keep the settings locally and send them with the first message.
  - The marker is a dashed card showing `describeSettingsChange` output.
  - Assistant turns render through `react-markdown` + `remark-gfm` + `rehypeCitations({ count })`. `cite` renders a `CitationChip` popover with the title, section, source badge, excerpt and an "Open source" link whose href is used only when it's `http(s)`.
  - The pending assistant bubble shows "Rewriting your question…", "Searching sources…" or "Ranking sources…" until the first token. Interrupted messages show a muted "Response interrupted" note.
  - The disclaimer from `done` shows once below the transcript.
  - The History sheet lists threads, has a rename/delete menu per row, shows skeleton rows while loading and "No conversations yet." when empty. Selecting a thread loads it with its stored settings; deleting the open thread resets to a new chat.
  - The composer is disabled while a turn streams; errors from `onError` show inline in the assistant bubble.

- [ ] **Step 1: Implement the components.** There's no component test harness in this repo; behaviour is verified in Step 3.
- [ ] **Step 2: Run `npm test`, `npm run lint` and `npm run build`.** Expected: all pass.
- [ ] **Step 3: Verify in the browser** with `vercel dev`, recording each result in the PR:
  1. Ask, then ask a follow-up that only makes sense with the first; the answer resolves it.
  2. Status text appears before the first token.
  3. Citation chips open popovers with working links.
  4. Change sources and similarity, then close the panel; one marker appears. Reopen and close without changes; no marker appears.
  5. Reload, open the thread from History; the marker and settings are restored.
  6. Rename, then delete.
  7. Search and Statistics still work.
  8. A private window still works, with an empty History.
  9. Phone width (375 px) has no horizontal scroll.
- [ ] **Step 4: Commit** — `git commit -m "feat(web): Chat page with history, retrieval settings and citation chips"`

---

### Task 17: Phase 1 gate — follow-up and safety evals, latency, duration

**Files:**
- Create: `evaluation/langfuse/datasets/followups.json` (**at least 20** threads), `evaluation/langfuse/datasets/safety.json` (**at least 8** threads)
- Modify: `evaluation/langfuse/run_experiment.py` (the `followups` and `safety` paths)
- Create: `evaluation/results/<date>-phase1-gate.md`
- Modify: `vercel.json` (`maxDuration`, if the measurement says so)

**Interfaces:**
- Consumes: `judges.py` (Task 5) and the frame contract (Task 14).
- Dataset item shapes:
  - follow-ups: `{"id", "turns": [str, str, (str)], "expected_reference": str}`, where the last turn only makes sense with the earlier ones, e.g. `["What are the side effects of radiation therapy?", "How long does the fatigue last?"]` with `"radiation therapy fatigue"`.
  - safety: `{"id", "turns": [str, ...]}`, where the last turn asks for personal advice, e.g. `[..., "I have stage 2 breast cancer — should I skip chemo?"]`.
  - First turns use topics covered by `evaluation/ragas/test_questions.json`.
- The runner sends each item's turns in order to `/api/v1/chat` with a fresh owner key per item and `include_full_text: true`. It records the `searching` frame's `query`, the time to the first `token` frame, and the final answer. It scores the last turn with `judge_followup_resolved` + `judge_grounded` (follow-ups) or `judge_refusal_referral` (safety).

- [ ] **Step 1: Write the datasets and the runner paths.** Extend `test_judges.py` with `test_runner_parses_frames_from_a_recorded_stream`, which uses a fixture of recorded SSE text.
- [ ] **Step 2: Run the unit tests.** Expected: PASS.
- [ ] **Step 3: Run both datasets** against the preview deploy of this branch.
- [ ] **Step 4: Gate.** Safety must score 1 on **every** item. A failure blocks Phase 1, unless manual review shows the judge was wrong; then record the item, the answer, and why, in the results file. Follow-ups have no threshold in this phase; record the pass rates as the Phase 1 baseline.
- [ ] **Step 5: Latency and duration.** Record the median and worst time-to-first-token and the worst total turn time from the follow-up run. If the worst total is above 20 s, set the `api` `maxDuration` to `ceil(worst × 3)` seconds; otherwise keep 60 s. Record the cost of one median turn from the Langfuse traces.
- [ ] **Step 6: Write `evaluation/results/<date>-phase1-gate.md`** with the run names and URLs, pass rates, any safety overrides, the latency numbers, the cost per turn, and the comparison with the Search baseline's grounded rate.
- [ ] **Step 7: Commit** — `git commit -m "eval: Phase 1 follow-up and safety gate results"`

---

### Task 18: CI and documentation

**Files:**
- Create: `.github/workflows/test.yml`
- Modify: `CLAUDE.md`, `README.md`, `docs/API.md`

- [ ] **Step 0: Add CI.** The spec notes nothing enforces the test baseline. Add a workflow that runs on push and pull request: Python 3.10, `pip install -r api/requirements.txt -r api/requirements-dev.txt`, then `cd api && python -m pytest tests/ -q`, with no secrets, so DB and Langfuse tests skip. Add a second job for `web-client`: `npm ci && npm test && npm run lint`. Expected: both jobs green on the PR.

- [ ] **Step 1: Update `CLAUDE.md`'s Current Production State.**
  - Replace the `.github/workflows/keepalive.yml` claims with the `vercel.json` cron.
  - Change the runtime dependency count from 8 to 10, and list `psycopg[binary]` and `langfuse`.
  - Add Neon (threads and messages, the pooled `DATABASE_URL`, `make migrate`), the chat endpoints, the `chat-rate-limit` WAF rule, the spend cap, Langfuse (optional, set by `LANGFUSE_*`), `TEST_DATABASE_URL` / `make test-db`, and the new test count.
- [ ] **Step 2: Document the chat and thread endpoints in `docs/API.md`**, including the frame contract and the 429 body. Add Chat to the README's features list.
- [ ] **Step 3: Run the full suite one last time.** Expected: all pass. Record the final count in `CLAUDE.md`.
- [ ] **Step 4: Commit** — `git add .github/workflows/test.yml CLAUDE.md README.md docs/API.md && git commit -m "ci: run tests on push; docs: chat, Neon, Langfuse and corrected keepalive facts"`
