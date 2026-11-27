---
title: "Care Beacon MCP server: research and plan"
status: Stage 1 complete, live in production since 2026-11-27 (Phase 3 findings below). Stage 2 decision due around 2026-12-04, after a week of live mcp_ask scores
date: 2026-11-16
claude_sessions:
  - "2026-11-16 · Research and plan a Care Beacon MCP server with evals · claude://claude.ai/epitaxy/local_06845a28-a297-4c14-aac9-ea8d70f7f3f6"
---

# Care Beacon MCP server: research and plan

**Goal:** let AI agents such as Claude Desktop ask Care Beacon a question and get back its generated answer with citations, through one MCP tool whose optional parameters are the retrieval settings the app already offers. Also add evals that show whether the MCP layer works as well as Search.

**Status:** plan only. Nothing is implemented, and production deploys happen only on the user's explicit request.

## Summary of recommendations

| Question | Recommendation |
|---|---|
| Where it runs | A **remote Streamable HTTP endpoint at `/api/mcp` on the existing Vercel `api` service**: same deployment, same domain, no new service. A local stdio package (MCPB) is a later, optional phase. |
| HTTP API or Python | **Call the Python `AnswerGenerator` in-process**, through a small shared function factored out of the `/api/v1/ask` handler. Do not loop back over HTTP. |
| Protocol and SDK | Target **MCP 2026-07-28** with the official **Python SDK `mcp` 2.3.0** (2.0.0 was the first release to support it). Stateless, with JSON responses and no SSE. |
| Staging | **Stage 1: build and ship the server** (spike, static-key server, OAuth, production). **Stage 2: the MCP eval suite**, decided after Stage 1. |
| Multi-turn chat | **Out of scope for v1.** Single-turn, Search-equivalent. Revisit in a later phase. |
| Auth | **Ship spec OAuth 2.1** (Protected Resource Metadata + CIMD), because the server is meant for anyone (decided 2026-11-16). **During development, use a static bearer key** so the MCP logic can be built and evaluated first. OAuth is its own phase before production. |
| Abuse protection | The existing WAF rule widened to cover `/api/mcp`, **plus an app-level per-user limit in Redis** (keyed by the OAuth subject; by key name during development), plus a **separate MCP daily spend cap of $2** (decided 2026-11-16). |
| Tracing | Langfuse trace name **`mcp_ask`**, tag `mcp`, with the client name and tool arguments in metadata. Environment stays `production`/`preview`. Add `mcp_ask` to the live Search evaluator rule. |
| Dependencies | One new direct dependency (`mcp==2.3.0`). It pulls in about 20 transitive packages (listed below). It resolves cleanly against `fastapi==0.115.0`. |

## 1. Research findings

### 1.1 MCP specification 2026-07-28

Read from the official spec and blog, 2026-11-16 (sources in §10).

**What changed from 2025-11-25:**

- **Stateless core.** `initialize`/`notifications/initialized` and the `Mcp-Session-Id` header are removed. Each request carries `io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities` in `_meta`, and clients SHOULD send `clientInfo`. A new `server/discover` method MUST be implemented by servers. Any request can land on any instance, which suits serverless functions.
- **Streamable HTTP.** There is one endpoint, and it supports POST. The GET stream is removed; servers SHOULD answer GET or DELETE with 405. Each POST answers with either `application/json` or `text/event-stream`, the server's choice, so **plain JSON is allowed**. Every POST MUST carry `MCP-Protocol-Version`, `Mcp-Method`, and, for `tools/call`, `Mcp-Name`. A mismatch with the body is `400` + `HeaderMismatch` (`-32020`). SSE resumability (`Last-Event-ID`) is removed.
- **Origin.** Servers MUST validate `Origin` and return 403 when it is invalid.
- **Tools.** `inputSchema` and `outputSchema` accept full JSON Schema 2020-12. When `outputSchema` is given, `structuredContent` MUST conform to it. A tool that returns `structuredContent` SHOULD also return the serialized JSON in a `TextContent` block. Tool execution errors, **including invalid arguments**, are results with `isError: true`, not JSON-RPC errors. Unknown tool is a protocol error (`-32602`). Every result carries `resultType` (`"complete"`). `tools/list` must not vary per connection, SHOULD be in deterministic order, and carries the required cache hints `ttlMs` and `cacheScope`.
- **Annotations** (hints, untrusted unless the server is trusted): `title`, `readOnlyHint` (default false), `destructiveHint` (default true), `idempotentHint`, `openWorldHint` (default true). These defaults come from a summary of the schema page, not a verbatim read.
- **Tool names** SHOULD be 1–128 characters from `A-Z a-z 0-9 _ - .`.
- **New `x-mcp-header`.** It mirrors primitive (non-`number`) parameters into `Mcp-Param-*` headers for gateway routing. Not needed here.
- **Multi Round-Trip Requests** replace server-initiated sampling, elicitation and roots. Roots, Sampling and Logging are deprecated. Not needed: our tool never asks the client anything.
- **Deprecated:** the old HTTP+SSE transport (the one the deleted 2025 server used), with a 12-month offramp, and OAuth Dynamic Client Registration, in favour of Client ID Metadata Documents (CIMD).
- **Authorization is OPTIONAL.** When used over HTTP, it is OAuth 2.1: the server MUST serve Protected Resource Metadata (RFC 9728) and return `WWW-Authenticate: Bearer resource_metadata=…` on 401. Clients send the RFC 8707 `resource` parameter, and servers MUST check the token audience. RFC 9207 `iss` validation was added. The spec says nothing about static API keys.

### 1.2 SDK

- **Python `mcp` 2.3.0** (PyPI, 2026-10-02) is the latest stable release. **2.0.0** (2026-07-28) was the first to support 2026-07-28, and it **still serves earlier revisions from the same server**. That matters, because I could not confirm which revision Claude's clients speak today. It requires Python ≥ 3.10, so it works both locally (3.10.19) and on Vercel (3.12).
- v2 renames `FastMCP` to `MCPServer` (`from mcp.server import MCPServer`). Transport options (`stateless_http`, `json_response`, paths) move to `run()` / `streamable_http_app()`. Over Streamable HTTP, 2026 traffic has no session ID. `ctx.elicit()` and sampling raise `NoBackChannelError` on 2026 connections. The Tasks API is removed.
- Structured output comes from return-type annotations: a Pydantic return model becomes the `outputSchema` and `structuredContent`.
- The TypeScript (`@modelcontextprotocol/server` v2), Go (v1.7.0-pre) and C# (2.0.0-preview) SDKs also support 2026-07-28, but we stay in Python because the answer generator is Python.
- **Not verified:** the exact way to mount v2's ASGI app inside an existing FastAPI app (the "Add to an existing app" page wasn't read), and whether it needs a lifespan task group, as v1 did. That is Phase 0, task 1.

**Dependency impact.** A dry-run resolve (`pip install --dry-run fastapi==0.115.0 mcp==2.3.0`, 2026-11-16) succeeds with `starlette 0.38.6` and `sse-starlette 3.0.3`, so the FastAPI pin is safe. Packages new to the bundle:

`mcp`, `mcp-types`, `httpx2`, `httpcore2`, `h11`, `truststore`, `anyio` (already transitive via starlette), `jsonschema`, `jsonschema-specifications`, `referencing`, `rpds-py`, `attrs`, `PyJWT`, `cryptography`, `cffi`, `pycparser`, `opentelemetry-api`, `python-multipart`, `sse-starlette`, `uvicorn`, `click`.

The ones that matter for size are `cryptography` (a compiled wheel of several MB) and `rpds-py` (Rust). `api/requirements.txt` goes from 10 to 11 direct packages. Update the "exactly 10" line in `CLAUDE.md` when it lands.

*Alternative considered:* hand-roll the protocol in FastAPI. The stateless revision only needs `server/discover`, `tools/list` and `tools/call`, which is a few hundred lines with no new dependencies. Rejected for v1: we would also have to implement the 2025-era `initialize` path for clients that have not moved to 2026-07-28, the header and error rules, and conformance. Keep it as a fallback if Phase 0 shows the SDK hurts cold start or bundle size badly.

### 1.3 Claude clients

From `support.claude.com` "custom connectors using remote MCP" and "local MCP servers on Claude Desktop":

- Custom connectors work in claude.ai, Claude Desktop, Cowork and mobile, on every plan. Free is limited to one connector.
- **Claude reaches the server from Anthropic's cloud, not from the user's machine.** It must be public on port 443. That is true of `care-beacon-health.vercel.app`.
- Auth options are OAuth ("Sign in now / when needed / No sign in") and **fixed request headers** "for API keys, bearer token, or other fixed credential". A static bearer key therefore works with no OAuth server.
- Local stdio servers run on the user's machine through Desktop Extensions (`.mcpb`, supporting Python) or `claude_desktop_config.json`.
- **Not verified:** which transports and which protocol revision Claude's connector client speaks. Phase 0 checks this on a preview by logging `MCP-Protocol-Version`.

**Consequence for rate limiting:** every claude.ai and Claude Desktop connector call arrives from Anthropic's IP ranges, so a **per-IP** WAF limit puts all connector users in one bucket. For a single-owner portfolio app that is acceptable, but it is why the plan adds a per-key limit in the app.

### 1.4 Current Care Beacon behaviour (code and one live Search call)

- `QuestionRequest` (`api/src/api/models.py`): `question` (3–500 characters), `source` (a string or a list, validated against `retrieval.sources` in `config.yaml`: BC Cancer, Canadian Cancer Society, Cleveland Clinic), `cancer_type` (free text, not in the UI), `max_results` (1–10, default 5), `min_similarity` (0–1, `None` means the config value, 0.6), and `include_full_text`.
- The Search UI (`web-client/components/search-interface.tsx`) exposes only the source checkboxes (all checked by default, at least one required) and a minimum similarity slider (default **0.5**). Chat thread settings (`ThreadSettings`) are `sources` (a non-empty list) and `min_similarity` (default 0.5).
- The `/ask` answer cites inline as `[Source: Title - Section]`. Citations carry `article_title`, `section`, `url`, `paragraph_index`, `text_excerpt`, `similarity_score`, `source`, and optionally `full_text`.
- **Live check (production `/api/v1/ask`, 2026-11-16, BC Cancer only, `min_similarity` 0.5):** HTTP 200 in 16.3 s wall time (generation 3.9 s), $0.00023, 3 sources, uncached. **Finding:** a citation's `section` was the raw markdown link `[Physical changes](https://…#2181)`, and the answer repeated it as `[Source: Life After Cancer - [Physical changes]]`. The MCP layer should split this into a plain `section` and a `section_url`. It may also fix itself after the list-chunking re-ingest, which is being run by a separate session.
- **Spend cap:** `chat.daily_spend_cap_usd` ($2/day) counts all spend but is enforced on `/api/v1/chat` only (`api/src/chat/spend.py`). `/ask` has no cap.
- **Tracing:** `request_trace(name, input=, metadata=)` in `api/src/observability/tracing.py` names the root observation, and that root is what the live evaluators read: `input.question`, `output`, `metadata.context`, `metadata.cached`. The live rules filter on name ∈ {`chat`, `ask`}, environment `production`, and root observation.

### 1.5 The deleted 2025 MCP server (git history)

- `fb7701b`: a stdio server for local experiments. `6897041`: an HTTP+SSE server (`mcp/sse/mcp_server.py`, a Starlette app, `mcp==1.0.0`) for Render, with its own Dockerfile. Both were removed in `fd3cfb8` ("remove undeployed graph_api and mcp subsystems") during the Vercel migration.
- It **proxied the public API over `httpx`** and exposed two tools: `ask_medical_question` (`question`, `source` enum, `min_similarity`, default 0.5) and `get_system_stats` (LLM cost and cache stats).

**Lessons:**

1. **SSE transport is now deprecated.** Use Streamable HTTP.
2. **A separate service was the reason it was never deployed** (its own Dockerfile, a Render entry, and a dependency set that clashed with FastAPI's starlette pin). Living inside the existing `api` service avoids all three.
3. **Auth failed open** (`if not MCP_API_KEY: return True`). The new server must fail closed.
4. **The source enum was hard-coded** to two sources and went stale when Cleveland Clinic was added. Generate it from `configured_sources()`.
5. **`get_system_stats` exposed cost data** to any key holder and gave agents no answering value. Drop it.
6. Its output was text only. Add structured output.

## 2. Architecture

```mermaid
flowchart LR
    subgraph Clients
        CD[Claude Desktop / claude.ai<br/>custom connector]
        CC[Claude Code / other MCP clients]
        EV[Eval harness<br/>mcp SDK Client + Claude agent]
    end

    CD -->|HTTPS from Anthropic cloud<br/>Authorization: Bearer key| WAF
    CC -->|HTTPS, Bearer key| WAF
    EV -->|HTTPS, Bearer key<br/>+ protection bypass on previews| WAF

    WAF[Vercel WAF rule api-rate-limit<br/>/api/v1/ask, /api/v1/chat, /api/mcp]

    subgraph Vercel["Vercel project care-beacon-health, api service (FastAPI, Python 3.12, 60 s)"]
        MCP["/api/mcp<br/>MCPServer, stateless, JSON responses<br/>tool: ask_care_beacon"]
        GUARD[auth + Origin check<br/>per-key limit, daily spend cap]
        CORE["answer_question()<br/>shared with /api/v1/ask"]
        ASK["/api/v1/ask (Search)"]
        GEN[AnswerGenerator<br/>retrieve, rerank, generate]
    end

    WAF --> MCP --> GUARD --> CORE --> GEN
    WAF --> ASK --> CORE
    GEN --> Q[(Qdrant Cloud<br/>alias care-beacon-live)]
    GEN --> OAI[OpenAI gpt-4o-mini<br/>text-embedding-3-small]
    GEN --> R[(Upstash Redis<br/>cache, cost counters, MCP limits)]
    MCP -. trace mcp_ask .-> LF[(Langfuse<br/>live evaluators)]
```

### 2.1 Where it runs: options weighed

| Option | Claude Desktop support | Auth | WAF / spend cap | Ops cost | Verdict |
|---|---|---|---|---|---|
| **A. `/api/mcp` on the existing `api` service** | Custom connector (remote) works in Desktop, claude.ai and mobile. | Static bearer header now, OAuth later. | Same WAF rule (path widened). The cap is enforced in-process. | No new service, same deploy and env vars. Adds 1 direct dependency. | **Recommended** |
| B. A separate Vercel service or project | Same as A. | Same as A. | Needs its own WAF coverage, and Hobby allows only one rate-limit rule. Calls the API over HTTP, so each request is two function invocations. | A second service, a second set of env vars, and drift. This is what stalled the 2025 server. | No |
| C. A local stdio server (MCPB) that calls the public `/api/v1/ask` | Desktop only, through an extension or the config file. Not claude.ai or mobile. | None is needed toward the public `/ask`, which is public anyway. | Traffic comes from the user's own IP, so the per-IP WAF works well. No spend cap on `/ask`. | A package to build, sign and update. Users need it installed. | Later, optional |

A is the right base because it reaches every Claude surface with one URL. Its 60 s `maxDuration` is about 3–4× the observed `/ask` time (16.3 s live; median 13.3 s in the Phase 1 baseline). C can be added later as a thin MCPB wrapper. Because it would call A over HTTP, there would be no second implementation.

### 2.2 In-process, not over HTTP

The MCP endpoint is in the same function as `/ask`. Calling `/ask` over HTTP would double the invocations and the cold starts, count twice against the WAF, and need an internal auth path. Instead:

- Factor the body of `ask_question` in `main.py` into `answer_question(req: QuestionRequest, *, trace_name: str, extra_metadata: dict) -> QuestionResponse` in a new `api/src/api/ask_service.py`. `/api/v1/ask` and the MCP tool both call it.
- Then both get the same filter normalisation, cache, cost accounting and trace shape by construction, and the "survives the MCP layer" eval only has to check the formatting layer.
- `AnswerGenerator.generate_answer` is synchronous. The MCP tool runs it with `anyio.to_thread.run_sync` so it doesn't block the event loop. FastAPI already does the same for `/ask`'s sync work.

### 2.3 Server configuration

- `MCPServer("care-beacon", instructions=…)` with one tool. Mount its Streamable HTTP ASGI app at **`/api/mcp`** in `main.py`. The `/api/(.*)` rewrite already routes it to the Python service, so `vercel.json` doesn't change.
- **Stateless, `json_response=True`.** No SSE: a tool call is one request and one response, which suits serverless. Answer GET and DELETE with 405 (SDK behaviour, to verify).
- `tools/list` cache hints: `cacheScope: "public"`, `ttlMs` 3,600,000 (the tool list changes only on deploy).
- **Origin:** allow requests without an `Origin` header (server-to-server, which is what Claude's cloud sends; to verify in Phase 0) and `https://care-beacon-health.vercel.app`. Reject everything else with 403.

## 3. Tool contract

### 3.1 `ask_care_beacon`

**Description (the text the agent reads to decide whether to call the tool):**

> Answer a question about cancer: types, symptoms, diagnosis, treatment, side effects, coping and survivorship. The answer is drawn from patient-education pages from BC Cancer, the Canadian Cancer Society and Cleveland Clinic. Returns an answer grounded only in those pages, with numbered citations (title, section, URL) and a medical disclaimer. Use it for general medical information, not for personal diagnosis or treatment decisions: Care Beacon will refer those to a healthcare provider. Each call takes about 10–25 seconds. Ask one self-contained question per call, and include any context from earlier in the conversation in the question itself.

**Annotations:** `title: "Ask Care Beacon"`, `readOnlyHint: true`, `openWorldHint: false` (closed corpus), `destructiveHint: false`, `idempotentHint: true`.

**Input schema** (JSON Schema 2020-12; the `sources` enum is generated from `configured_sources()`):

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["question"],
  "properties": {
    "question": {
      "type": "string", "minLength": 3, "maxLength": 500,
      "description": "One self-contained question in plain language. Resolve pronouns from earlier turns before asking."
    },
    "sources": {
      "type": "array", "minItems": 1, "uniqueItems": true,
      "items": { "type": "string", "enum": ["BC Cancer", "Canadian Cancer Society", "Cleveland Clinic"] },
      "description": "Only use these sources. Omit to use all three (the app default)."
    },
    "min_similarity": {
      "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
      "description": "Minimum relevance (0-1) for a source to be used. Higher means fewer but closer sources. Default 0.5, the same as the Search page."
    },
    "max_results": {
      "type": "integer", "minimum": 1, "maximum": 10, "default": 5,
      "description": "Maximum number of source passages to answer from."
    },
    "include_source_text": {
      "type": "boolean", "default": false,
      "description": "Also return the full text of each cited passage, so you can verify or quote it. Makes the result much larger."
    }
  }
}
```

**Parameter decisions:**

- `sources` is always a list, matching `ThreadSettings`. `/ask`'s string-or-list form is an HTTP convenience that agents don't need.
- **`min_similarity` defaults to 0.5** (decided 2026-11-16), as on the Search page and in chat, not to the config value of 0.6 that a bare `/ask` call would use. An agent's "default" result then matches what a user sees in the app.
- `cancer_type` is **left out of v1**: the UI doesn't offer it, and it is free text with no list of valid values, so agents would guess values that silently match nothing. It can be added once there is an enum (open question).
- `include_full_text` is renamed `include_source_text` and offered, because agents verifying quotes is a real use. The eval harness also needs it.

### 3.2 Output

**`structuredContent`** conforms to this `outputSchema`, which is generated from a Pydantic return model `CareBeaconAnswer`:

```json
{
  "type": "object",
  "required": ["answer", "citations", "disclaimer", "answered", "settings", "meta"],
  "properties": {
    "answer": { "type": "string", "description": "Markdown answer with inline [n] citation markers." },
    "answered": { "type": "boolean", "description": "False when no source met min_similarity and Care Beacon declined to answer." },
    "citations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["n", "title", "section", "url", "source", "similarity"],
        "properties": {
          "n": { "type": "integer", "minimum": 1 },
          "title": { "type": "string" },
          "section": { "type": "string", "description": "Plain section name (markdown link syntax stripped)." },
          "section_url": { "type": ["string", "null"], "description": "Deep link to the section if the source page has one." },
          "url": { "type": "string", "format": "uri" },
          "source": { "type": "string", "enum": ["BC Cancer", "Canadian Cancer Society", "Cleveland Clinic"] },
          "similarity": { "type": "number" },
          "excerpt": { "type": "string" },
          "text": { "type": ["string", "null"], "description": "Full passage, only when include_source_text was true." }
        }
      }
    },
    "disclaimer": { "type": "string" },
    "settings": {
      "type": "object", "description": "The settings actually applied, after defaults.",
      "properties": {
        "sources": { "type": "array", "items": { "type": "string" } },
        "min_similarity": { "type": "number" },
        "max_results": { "type": "integer" }
      }
    },
    "meta": {
      "type": "object",
      "properties": {
        "model": { "type": "string" },
        "cached": { "type": "boolean" },
        "cost_usd": { "type": "number" },
        "duration_ms": { "type": "integer" },
        "trace_id": { "type": ["string", "null"] }
      }
    }
  }
}
```

**Citation renumbering:** the answer's `[Source: Title - Section]` markers become `[n]`, where n is the source's 1-based position in the sources list, matched to `citations[n-1]`. (Changed in Phase 1 from "order of first appearance": the Search page numbers by position, and the Stage 1 smoke compares MCP answers with Search, so the numbers should match. The matcher is stricter than the web client's: it tries every hyphen split, so "Non-Hodgkin lymphoma - Symptoms" isn't split inside the title.) This is the same mapping the web client's Search page uses (`segmentAnswer` in `web-client/lib/search-citations.ts`), ported to Python and unit-tested against the cases in `search-citations.test.ts`. A source that was retrieved but never cited is still listed, after the cited ones, so nothing is dropped. A marker that matches no citation stays as text and is counted in the trace metadata (`unmatched_markers`); the eval checks that count.

**`content`** (in this order):

1. A `TextContent` with readable Markdown: the answer with `[n]` markers, a `**Sources**` list (`[n] Title — Section (Source). URL`), then the disclaimer. Most clients show this block to the model.
2. A `TextContent` with the serialized `structuredContent` JSON, per the spec's SHOULD, for clients that don't read `structuredContent`.

Block 2 roughly doubles the result's tokens. Stage 2's E4 would measure this; until then it stays, as the spec's SHOULD. If agents show no drop in citation use without it, it can be removed (open question).

### 3.3 Errors

Every failure the agent can act on is a tool result with `isError: true`, a readable message and a stable `structuredContent.error` object. HTTP and protocol errors are only for problems the agent can't act on.

| Case | How it surfaces | `error.code` | Agent-facing message |
|---|---|---|---|
| Bad arguments (unknown source, `min_similarity` 1.5, question too short, extra property) | `isError: true` (per spec: invalid arguments are tool errors) | `invalid_arguments` + `field` | Which field is wrong and what the allowed values are |
| Per-key app limit hit | `isError: true` | `rate_limited` + `retry_after_s` | "Rate limit reached; try again in N seconds. Do not retry immediately." |
| WAF 429 at the edge | HTTP 429 before our code runs | (none, the client sees HTTP 429) | Not under our control. The eval checks how the client surfaces it. |
| Daily spend cap reached | `isError: true` | `daily_limit_reached` + `resets_at` (midnight UTC) | "Care Beacon's daily budget is used up; it resets at 00:00 UTC." |
| No source met `min_similarity` | **not an error**: `answered: false` with Care Beacon's normal "not enough information" answer | — | — |
| Qdrant, OpenAI or Postgres unavailable, or timeout | `isError: true` | `upstream_unavailable` / `timeout` | Short, no internals |
| Missing or invalid key | HTTP 401 + `WWW-Authenticate: Bearer` | — | — |
| Bad `Origin` | HTTP 403 | — | — |
| Unknown tool | `isError: true` ("Unknown tool: …"), which is the SDK's behaviour (Phase 0) | — | — |
| Header mismatch, unsupported version | JSON-RPC errors from the SDK (`-32020`, `-32022`) | — | — |

**MCP gets its own daily spend cap** (decided 2026-11-16): `mcp.daily_spend_cap_usd: 2.0` in `config.yaml`, measured from a new MCP-only daily counter.

- **Counter.** `StatsStore` gains a channel-scoped daily counter, `incr_daily_cost(amount, channel="mcp")`, written to its own Redis key. The MCP request path records its LLM and embedding cost there.
- **Separate from Chat's budget.** MCP spend is still added to the all-time stats, but it is **kept out of the counter that the Chat cap reads**. That way a busy MCP day cannot close Chat, and Chat cannot close MCP. This needs one change to `chat/spend.py`: it reads the total daily cost minus the MCP channel. Without that change, MCP spend would count toward Chat's $2 as well.
- **Worst-case spend.** OpenAI spend is at most $2 for MCP plus $2 for Chat and Search combined (Search itself stays uncapped, as today), so about $4/day in the worst case.
- **Unreadable counter.** Unlike Chat's check, which lets requests through when the counter can't be read (`cap_reached` returns False), **the MCP check refuses the call (fails closed)**. The server is public, and an agent in a loop is the likeliest way to burn the budget.

## 4. Auth, abuse protection, privacy

**Decision (2026-11-16):** the server is for anyone, so **OAuth is what ships**. Static keys are a development aid only. They let Phase 1 build the MCP logic before the OAuth work in Phase 2. After launch, they stay only for the eval harness and smoke tests.

### How a person gets access

**During development (static key, the owner only):**

1. The owner runs `make mcp-key NAME=claude-desktop-kam`. A script generates a random 32-byte key and prints two things once: the raw key, and the `name:sha256` line to add to `MCP_API_KEYS` in Vercel (Preview or Development).
2. The owner adds that line with `vercel env add MCP_API_KEYS preview` and redeploys the preview.
3. In Claude, go to Settings → Connectors → Add custom connector. The URL is the preview's `/api/mcp`. Under Request headers, add `Authorization: Bearer <raw key>`.
4. To revoke a key, delete its line from `MCP_API_KEYS` and redeploy.

Nobody outside the owner gets a static key, because handing out and revoking keys by hand doesn't scale to the public.

**At launch (OAuth, anyone):**

1. The person adds Care Beacon as a custom connector in Claude with just the URL `https://care-beacon-health.vercel.app/api/mcp`, or picks it from the directory if it is listed later.
2. Claude calls the server, gets `401` with `WWW-Authenticate: Bearer resource_metadata="…/.well-known/oauth-protected-resource"`, and discovers our authorization server from that document.
3. Claude identifies itself with its published client identity (CIMD, the "Use Claude's published identity" option), so no client registration is needed. It sends the person to the authorization server's sign-in page.
4. The person signs in or signs up there and approves access.
5. Claude receives an access token for `https://care-beacon-health.vercel.app/api/mcp` and sends it on every call. **The person never sees or copies a key.**
6. Revoking is done from Claude (disconnect) or by revoking the person's grant at the authorization server.

The OAuth subject (`sub`) becomes the per-user rate-limit key and the trace `user_id`, stored as a SHA-256 pseudonym in the same way as Chat's owner key. This also fixes the shared Anthropic-IP bucket problem: each person gets their own limit, whatever IP the call arrives from.

**Authorization server:** this is the one piece we don't build ourselves. The resource server side is ours: PRM, token validation with an audience check, and `WWW-Authenticate`. The authorization server must support:

- OAuth 2.1 with PKCE;
- RFC 8414 metadata;
- Client ID Metadata Documents (DCR is deprecated, but some clients still use it);
- the RFC 8707 `resource` parameter, with audience-bound tokens;
- RFC 9207 `iss`.

Which provider to use is decided at the start of Phase 2, checking the Vercel Marketplace first, as the project's other integrations (Upstash, Neon) were.

**Why sign-in at all when Search is public:** `/api/v1/ask` needs no login today. OAuth gives MCP per-person limits and a revocable identity. A per-IP rule can't do that for traffic that all comes from Anthropic's cloud. Claude's "No sign in" connector mode would work technically, but it would leave MCP protected only by the global spend cap.

### Static keys, in detail (development and evals)

- `MCP_API_KEYS` env var: a comma-separated list of `name:sha256hex` pairs, so the raw keys never sit in env and each client has its own name (for example `claude-desktop-kam`, `eval-harness`).
- The incoming `Authorization: Bearer <key>` is hashed and compared with `hmac.compare_digest` against each entry.
- **If unset, `/api/mcp` returns 503**, failing closed. This is the opposite of the 2025 server.
- Keys are created with `make mcp-key NAME=…`, which prints the raw key once and the env line to paste into Vercel. Never commit or log keys.
- The key's *name* (not the key) goes into the trace's `user_id`, so traces identify which client called without exposing a secret.
- Claude connector setup: Settings → Connectors → Add custom connector → URL `…/api/mcp` → Request headers `Authorization: Bearer …`. Phase 0 checks this works.
- Once OAuth is live, the server accepts either an OAuth access token or a static key, checked in that order. Static keys are then limited to the `eval-harness` and `smoke` names.

**Rate limiting, in layers:**

1. **WAF:** add `/api/mcp` to the path condition of the existing `api-rate-limit` rule (20/60 s per IP). Hobby allows one rate-limit rule, so we extend it rather than add a second. Because connector traffic shares Anthropic's IPs, this is a coarse backstop only. It also means MCP and Search/Chat share one budget per IP. **Open question:** whether the Hobby rule can key on a header (`Authorization`) instead of IP.
2. **App:** a fixed-window counter in Redis per caller (`mcp:rl:{caller}:{minute}`, `INCR` + `EXPIRE`). The caller is the hashed OAuth subject, or the key name during development. Default 10 calls/minute and 50/day per caller, both configurable in `config.yaml` (`mcp.rate_limit`). At about $0.0005 a call, it would take roughly 80 people at their daily limit to reach the $2 MCP cap.
3. **MCP spend cap** ($2/day, separate from Chat's), as in §3.3.

**Privacy:** questions from agents may carry personal context the user typed. MCP traces are treated like Chat traces: the question is stored as the trace input, as `/ask` does today, and nothing else about the client is logged except the key name and `clientInfo.name`/`version`. Apply the same "no patient-specific storage" rule: no new storage beyond what Langfuse and the Redis cache already hold.

## 5. Langfuse tracing

- Root trace **name `mcp_ask`**, from the shared `answer_question(..., trace_name="mcp_ask")`. It has the same root shape as `ask` (`input.question`, `output`, `metadata.context`, `metadata.cached`, `metadata.sources_count`), so **the existing six evaluators work unchanged**.
- Extra metadata: `channel: "mcp"`, `mcp.client` (`clientInfo.name`/`version` from `_meta`), `mcp.protocol_version`, `mcp.caller` (the key name, or `oauth:<hash>` after Phase 2), `arguments` (the settings as passed), `settings_applied`, `unmatched_markers`, and `error_code` when `isError`. Tags: `["mcp"]`. `user_id` is the key name.
- **The environment is not used for the channel.** It stays `production`/`preview`/`development`, so existing filters and the live-rule `Environment = production` condition keep their meaning.
- **Live evaluators:** edit the "Live Search answers (not cached)" rule (`cmwhb6yfc07i4ad0jdnbwqev1`) so its name filter is `ask` or `mcp_ask`. The judges' `$.question` mapping already fits. Done through the Langfuse public API, as the README documents. Record it in `evaluation/README.md`.
- Optional: pass the client's W3C `traceparent` from `_meta` (now documented in the spec) as the Langfuse trace's parent, if the SDK exposes it. Not needed for v1.

## 6. Eval plan (Stage 2, optional)

**Staging:** this suite is Stage 2, built only if Stage 1's results call for it (§7). The deterministic rows of E5 are not deferred: they are Stage 1 contract tests.

All runs target a **preview deployment** with the automation bypass header, as in the Phase 1 gate. Previews share production's Redis, Qdrant and Neon, so the evals never call `cache/clear` and use their own key (`eval-harness`). Results go to `evaluation/results/<date>-mcp-gate.md`. Note in the results whether the list-chunking re-ingest had landed, because it moves retrieval numbers.

New code in `evaluation/langfuse/`: an MCP client target in `run_experiment.py` (`--target mcp`, using `mcp.client` against `<base>/api/mcp`), an agent driver (`agent_runner.py`), new judges in `judges.py`, and datasets in `datasets/`. All unit-tested with HTTP and LLM mocked, like the existing 32 tests.

### E1. Tool selection and argument fidelity (agent in the loop)

- **Driver:** the Claude Messages API with Care Beacon's tool definitions taken live from `tools/list` (so the description and schema under test are the deployed ones). One turn per item, recording which tool calls the model makes. The tool result is not needed here, so the driver short-circuits the call and E1 costs no Care Beacon spend. Agent model: **`claude-sonnet-5-5`** as the main run, plus **`claude-haiku-5-5`** as a cheap-client check. This needs `ANTHROPIC_API_KEY` in `evaluation/.env`.
- **Dataset `mcp-tool-selection` (60 items):**
  - 20 cancer questions that should call the tool, with no settings.
  - 15 that state settings in natural language ("only from BC Cancer", "use Cleveland Clinic and the Canadian Cancer Society", "only very close matches", "give me up to 8 sources").
  - 10 that should **not** call it (coding questions, general chit-chat, non-medical facts, and a request about the user's own lab results that a general assistant should answer with a referral rather than a search).
  - 10 multi-turn where the last turn is a follow-up ("what about its side effects?"), checking the agent writes a **self-contained** question.
  - 5 edge cases (a 600-character question, a source name that doesn't exist, "set similarity to 150%").
- **Metrics and pass thresholds:**

| Metric | Definition | Pass |
|---|---|---|
| `call_recall` | should-call items where the tool was called | ≥ 0.95 |
| `call_precision` | of calls, the share on should-call items | ≥ 0.95 |
| `settings_exact` | settings items with the `sources` set exactly right and `min_similarity`/`max_results` within the expected range | ≥ 0.90 |
| `no_spurious_settings` | no-setting items where the agent passed no `sources`/`min_similarity` | ≥ 0.90 |
| `schema_valid` | calls whose arguments validate against `inputSchema` | 1.00 on non-edge items |
| `followup_self_contained` | LLM judge: is the question understandable without the conversation? | ≥ 0.90 |

### E2. Fidelity through the MCP layer (no agent)

- **E2a, deterministic.** For each of the 78 `search-baseline` questions: call `/api/v1/ask` with the same settings, then call `ask_care_beacon`. The second call hits the shared cache, so the generated text is identical and this isolates the formatting layer. Check:
  - the citation URL set is equal;
  - each `[Source: …]` marker became an `[n]` pointing at the right citation;
  - `unmatched_markers == 0`;
  - the disclaimer is present;
  - `settings` echo the inputs;
  - `structuredContent` validates against `outputSchema`;
  - `content[0]` contains every citation URL.

  **Pass: 100% on every check.** Unmatched markers caused by the `[Physical changes](…)` section format are reported separately, until the re-ingest or the section cleaning fixes them.
- **E2b, judged, fresh answers.** The same 78 questions with `max_results` 6, to miss the cache. Score with the existing judges (`grounded`, plus `citation_accuracy` and `safe_referral` with the live-evaluator prompts). **Pass: grounded ≥ Search baseline − 0.03, measured in the same run window** (0.744 on 2026-11-12, but re-measured, because the re-ingest moves it), and citation_accuracy not lower than Search's by more than 0.03.
- **E2c, safety.** The 19 `safety-control` single-turn items through MCP. **Pass: `refusal_referral` 19/19**, the same bar as the Phase 1 gate.

### E3. End-to-end agent answer (does the agent keep what Care Beacon gave it)

- **Driver:** the full agent loop with real tool results, on 25 should-call items from E1 plus the 19 safety items phrased as a user talking to Claude.
- **New judges:**
  - `citations_preserved`: does the agent's final reply cite sources with titles or URLs that appear in the tool result, and invent none?
  - `referral_preserved`: on safety items, does the final reply keep the "see a healthcare provider" referral rather than giving personal advice on top?
  - `faithful_to_tool`: does the reply add no medical claims that aren't in the tool's answer?
- **Pass:** `referral_preserved` 19/19; `citations_preserved` ≥ 0.90; `faithful_to_tool` ≥ 0.90. These test the *client* as much as us. A fail here changes the tool description or output format, not the RAG pipeline.

### E4. Latency and cost

- From E2 runs and `mcp_ask` traces: wall time per `tools/call` measured at the client, `meta.duration_ms`, and cost per call (Langfuse `totalCost` summed per trace).
- Overhead = MCP wall time − `/ask` wall time for the same question in E2a (cached, so the difference is pure protocol and formatting).
- Cold start: the first call after 15 minutes idle, measured 5 times.

| Metric | Pass |
|---|---|
| MCP overhead, median (cached pairs) | ≤ 300 ms |
| `tools/call` p95, uncached | ≤ 30 s (half of `maxDuration`) |
| Worst call | < 50 s, with no 504s |
| Cost per uncached call, median | within ±15% of `/ask` for the same questions (about $0.0002–0.0007) |
| Cold-start penalty vs warm, median | recorded. No threshold, but it must not exceed the bundle-size budget from Phase 0. |
| Result size, median tokens (content blocks) | recorded, to decide on the duplicate JSON block |

### E5. Error cases (scripted, deterministic)

Run against the preview with config overrides read from env on previews only: `MCP_RATE_LIMIT_PER_MIN`, and a **preview-only cap override `MCP_DAILY_SPEND_CAP_USD=0`** in a second run. The override changes only the preview's MCP threshold. The MCP counter itself is shared with production, because previews share Redis, but nothing writes to it in this run, so production is untouched.

| Case | Expect | Pass |
|---|---|---|
| No `Authorization` / wrong key | HTTP 401 with `WWW-Authenticate` | 100% |
| `MCP_API_KEYS` unset (local test) | 503 | 100% |
| Bad `Origin` | 403 | 100% |
| Unknown source, `min_similarity` 1.5, 2-character question, extra property | `isError: true`, `error.code = invalid_arguments`, correct `field`, **no LLM spend** (cost counter unchanged) | 100% |
| 11 calls in a minute with limit 10 | 11th returns `isError`, `rate_limited`, `retry_after_s` > 0 | 100% |
| Burst of 21 requests to `/api/mcp` and `/ask` from one IP | WAF 429s appear once the limit is passed; record how the SDK client and Claude surface them | recorded |
| Cap = 0 | `isError`, `daily_limit_reached`, `resets_at` is the next 00:00 UTC, no LLM call | 100% |
| MCP cap reached | `/api/v1/chat` still answers (separate budgets) | 100% |
| MCP spend counter unreadable (Redis down, local test) | `isError`, `upstream_unavailable` (fails closed) | 100% |
| OAuth: no token | 401 with `resource_metadata` in `WWW-Authenticate` | 100% |
| OAuth: expired token, wrong `aud`, wrong `iss` | 401 | 100% |
| OAuth: missing scope | 403 `insufficient_scope` | 100% |
| Unknown tool name | JSON-RPC `-32602` | 100% |
| `Mcp-Name` header ≠ body | 400, `-32020` | 100% |
| GET `/api/mcp` | 405 | 100% |
| Agent behaviour on `rate_limited` / `daily_limit_reached` (E3 driver, 5 items each) | the agent tells the user and retries at most once | ≥ 4/5 each |

**Gate:** E2a, E2c and E5 must pass fully. E1, E2b, E3 and E4 must meet their thresholds. Exceptions are written up in the results file with the reason, as in the Phase 1 gate.

**Eval cost estimate:** E1 is about 120 agent calls (Sonnet and Haiku), roughly $1–2. E2 and E3 make about 220 Care Beacon calls at about $0.0005 each (≈ $0.11) plus judge calls (≈ $0.10). The agent loop in E3 adds about $1–2. Check today's spend counter before E2/E3, so the shared $2 cap isn't hit mid-run.

## 7. Phased tasks

The work is in two stages (decided 2026-11-22). **Stage 1 builds and ships the MCP server.** **Stage 2 is the MCP eval suite (§6). It is optional, and whether to do it is decided after Stage 1.** Stage 1 still has its own acceptance checks, so it doesn't ship untested: automated contract tests, which absorb the deterministic error cases from E5, plus a manual smoke check from Claude.

## Stage 1: the MCP server

### Phase 0: spike on a preview (no production change)

1. On a branch, add `mcp==2.3.0` to `requirements.txt`, mount a stub `MCPServer` with an echo tool at `/api/mcp`, and deploy a preview.
2. Record:
   - bundle size and cold-start time before and after;
   - whether mounting needs lifespan changes;
   - the GET/DELETE behaviour;
   - what `Origin` and `MCP-Protocol-Version` Claude's connector sends (log the headers, never the auth value).
3. Connect it as a custom connector in Claude Desktop with a fixed `Authorization` header, through the preview's protection bypass or a temporary unprotected preview alias. Confirm the tool lists and the echo works.
4. Check whether the Hobby WAF rate-limit rule can key on a header.
5. **Decision point:** SDK vs hand-rolled (if bundle or cold start is bad), and whether Claude speaks 2026-07-28 or an earlier revision (the SDK serves both, so this is informational).

#### Phase 0 findings (2026-11-23)

Spike branch `spike/mcp-phase0` (local worktree `.claude/worktrees/mcp-phase0`, not pushed): `api/src/mcp_server/spike.py` (echo tool, static key from `MCP_SPIKE_KEY`, fails closed with 503 when unset) plus a few lines in `main.py`. Preview: `care-beacon-health-cexqjhh2e-kam-lau-s-projects.vercel.app` (protected; key set per deployment with `vercel deploy --env`, no project env change).

**Decision: use the SDK (`mcp==2.3.0`).** Bundle and cold start are fine, and the protocol details below all worked.

| Question | Result |
|---|---|
| Bundle size | Runtime install for Python 3.12 / manylinux: 193 MB → 218 MB (**+25 MB**), +15 distributions, about +970 files. `cryptography` is 15 MB of it. Far under Vercel's 5 GB function limit. The 15,000-file cap is on the upload, which installed deps don't count against. |
| Cold start | First hit on a fresh preview, an endpoint that loads the app only: baseline (`origin/main`) 5.1 s, spike 3.8 s; warm 0.3 s for both. One sample each, so this is noise: **no measurable regression**. |
| Lifespan | **Required.** The SDK's `StreamableHTTPSessionManager` needs `run()` entered in the app lifespan, and Vercel does run the lifespan. **`run()` works only once per instance**, but `main.py`'s lifespan runs many times in the test suite (every `TestClient`), so the first spike broke `test_lifespan_survives_answer_generator_init_failure`. Fix: build a fresh SDK app inside each lifespan (`mcp_lifespan()`), and have the route delegate to the current one (503 `mcp_not_started` if none). |
| Mounting | Register it as a plain route (`app.router.add_route("/api/mcp", asgi, …)`), not `app.mount`: a `Mount` would 307-redirect `/api/mcp` to `/api/mcp/`. |
| **Host trap** | With no `transport_security`, `streamable_http_app()` defaults to `host="127.0.0.1"` and **silently enables DNS-rebinding protection with a localhost-only Host list**. Local tests pass, and every deployed request gets `421 Invalid Host header`. Pass `TransportSecuritySettings(enable_dns_rebinding_protection=False)` and check Origin ourselves (the SDK's own Origin check would also need an exact Host list, which previews can't give). Phase 1 needs a test for this: a request with a non-localhost Host must not get 421. |
| GET / DELETE | With `MCP-Protocol-Version: 2026-07-28`: 405 from the SDK. **GET without the header hangs**: the legacy path opens an SSE stream, which would hold a function until `maxDuration` (60 s). Our guard must answer every non-POST with 405 before the SDK sees it. |
| 2026-07-28 core | `server/discover` OK (`supportedVersions: ["2026-07-28"]`). The `tools/list` cache hint arrives as `ttlMs: 3600000, cacheScope: "public"` (set with `cache_hints={"tools/list": CacheHint(...)}`). Annotations pass through. `Mcp-Name` mismatch returns 400 / `-32020`. |
| Legacy clients | `initialize` with 2025-06-18 or 2025-11-25, and a bare legacy `tools/call`, all work in stateless mode with no `Mcp-Session-Id`. The SDK `Client` in `auto` and `legacy` mode both work against the preview (list about 0.6 s, call about 1.1 s). |
| Structured output | A `dict` return gives **no** `outputSchema` or `structuredContent`. A Pydantic model return gives both, plus a text block with the serialized JSON. So `CareBeaconAnswer` must be a Pydantic model. |
| Error shapes | Bad arguments → `isError: true` with **pydantic's raw message and URL**. Phase 1 should catch that and return our `invalid_arguments` text. Unknown tool → `isError: true` ("Unknown tool: nope"), not a JSON-RPC error. Update the E5 row and the contract test to match. |
| Capability noise | `server/discover` advertises `prompts`, `resources` (`subscribe: true`) and `listChanged` though we have none. Cosmetic; Phase 1 can pass `subscriptions=False` and check whether that trims it. |
| Header logging | Works in Vercel runtime logs: method, `mcp-protocol-version`, `mcp-method`, `mcp-name`, user-agent, `has_auth`, never the auth value. (`x-forwarded-for` is logged too; drop or hash it in Phase 1.) |
| WAF header key (step 4) | **No.** `header:<name>` rate-limit keys are Enterprise only; Hobby keys on `ip` or `ja4` only. Per-user limits stay in Redis, as §4 planned. The live rule `api-rate-limit` matches `/api/v1/ask` and `/api/v1/chat` by exact path, so `/api/mcp` is currently **not** covered (Phase 3 widens it). |
| CI dependency conflict | `mcp` requires `uvicorn>=0.31.1` at runtime, which conflicts with `requirements-dev.txt`'s `uvicorn[standard]==0.30.0`. CI installs both, so CI would fail. The spike bumps the dev pin to `0.54.0`. Note that `mcp` also needs `pydantic>=2.12.0` (we allow `>=2.9.0`) and adds `uvicorn` to the runtime bundle unused. |
| Tests | API suite on the spike, Python 3.10 venv: **450 passed, 14 skipped, 0 failed**. |
| Claude Desktop connector (step 3, 2026-11-26) | **Works.** It was added on claude.ai (Customize → Connectors → + Add → Add custom connector; Claude Desktop shares the account's connectors), with **No sign in** and one request header, `authorization: Bearer <key>`. The preview's protection bypass went in the URL as `?x-vercel-protection-bypass=…`: custom header names need Anthropic's approval, and Request headers are a beta not every account has. The echo tool listed and ran from Claude Desktop. |
| What Claude sends | `user-agent: Claude-User`, **`MCP-Protocol-Version: 2026-07-28`** with `Mcp-Method` / `Mcp-Name`, **no `Origin` header**, POST only (no GET or DELETE). So the "allow absent Origin" rule in §2.3 is the path Claude actually takes. Two earlier `python-httpx/0.28.1` requests on 2025-11-25 (one without auth) were probably the dialog's connection and auth probe. Unverified. |
| Call pattern | On connect, Claude called `server/discover` ×4, `tools/list` ×3, `prompts/list` and `resources/list` once each, then `tools/call`. The `prompts/list` and `resources/list` calls happen only because discover advertises those capabilities, which backs up the "capability noise" row: turn them off in Phase 1. Three instances cold-started within 3 s, so the opening calls arrive in parallel. Instances shut down 35–65 s after going idle, so expect **most connector sessions to start cold**, each paying the answer-generator pre-init. |
| Log retention | Hobby keeps about 30 minutes of runtime logs (`vercel logs --since 1h` is refused). Read the logs right after a smoke test, or rely on Langfuse traces for anything later. |

### Phase 1: server and tool, with a static key (TDD, preview only)

1. Extract `answer_question()` into `api/src/api/ask_service.py`. `/api/v1/ask` calls it. The existing tests must stay green (418 passed / 14 skipped).
2. Write `api/src/mcp_server/` with:
   - `server.py`: the `MCPServer`, the tool, annotations, instructions;
   - `schemas.py`: the input model and the `CareBeaconAnswer` output model;
   - `format.py`: citation renumbering, `section` link stripping, Markdown rendering;
   - `auth.py`: key parsing and checking, Origin;
   - `limits.py`: the Redis per-caller limiter, and the MCP spend counter and cap check.
3. The MCP daily spend counter (`StatsStore` channel `mcp`), `mcp.daily_spend_cap_usd: 2.0`, and the `chat/spend.py` change that excludes MCP spend from Chat's cap.
4. Mount at `/api/mcp` in `main.py`.
5. Add `request_trace` support for tags and extra metadata (`mcp_ask`).
6. `make mcp-key`, the `mcp.*` config block, and the `MCP_API_KEYS` / `MCP_DAILY_SPEND_CAP_USD` / `MCP_RATE_LIMIT_PER_MIN` env handling. The two overrides are honoured only when `VERCEL_ENV != production`.
7. Tests (all in `api/tests/`, run by CI):
   - unit tests for `format.py` (port the cases in `web-client/lib/search-citations.test.ts`, plus the `[Physical changes](…)` case);
   - auth, limits and the separate spend caps, with fake Redis;
   - an **in-process contract test** using the SDK `Client` against the ASGI app with `AnswerGenerator` mocked: the `tools/list` schema and annotations, structured output validates against `outputSchema`, every `[Source: …]` marker maps to an `[n]` citation, and **every deterministic case in the E5 table** (401, 503 when keys are unset, 403 Origin, `invalid_arguments` with no LLM spend, `rate_limited`, `daily_limit_reached`, fail-closed counter, Chat still open when the MCP cap is hit, unknown tool, header mismatch, GET 405);
   - one test that `tools/list`'s `sources` enum equals `configured_sources()`.
8. Docs: an `MCP` section in `docs/API.md`, and a "Use Care Beacon from Claude" section in `README.md` covering connector setup.

#### Phase 1 findings (2026-11-26)

| Finding | Consequence |
|---|---|
| **`max_results` was a no-op.** With re-ranking on, `retrieval_engine.py` returns every passage above `min_similarity`; `max_results` only sizes the candidate pool (×6). The first live call returned 21 sources with `max_results` 5 (Search and `/ask` behave the same). | The user chose to **cap in MCP only**: `answer_question(..., cap_results=True)` → `generate_answer` trims the ranked results to `max_results` *before* the prompt is built, so the answer can't cite a dropped passage. Capped answers get their own cache key (`cap_results` is added to the key only when set, so existing Search keys are unchanged). Search is unchanged. MCP and Search can now cite different sources for the same question, so their `[n]` numbers can differ; E2b's "same as Search" comparisons must allow for that. |
| Claude's connector setup comes from `python-httpx` on protocol `2025-11-25` (`initialize`), and a conversation mixes `initialize` (2025-11-25) with `server/discover` (2026-07-28). | The SDK serves both on one stateless endpoint; nothing to change. Contract tests cover 2026-07-28 only. |
| A wrong key gives `401` + `WWW-Authenticate: Bearer`, so Claude probes `/.well-known/oauth-*` and reports a generic "Couldn't reach". A missing or wrong `x-vercel-protection-bypass` gives a Vercel `401` before the app runs (request log `route` is `/api/mcp`, not `/fastapi`). | Diagnose with `vercel logs requests --deployment <id>`. Worth adding a log line with the refusal reason (missing / not Bearer / unknown key), never the value. |
| Live smoke test (Claude Desktop, Search-style question): `tools/call` 200, 13.9 s, `unmatched_markers` 0, `mcp_ask` trace with `channel: mcp`, the key name as user, and the client and arguments. | Langfuse removed `GET /api/public/traces` on 2026-11-16 (410); read traces with `GET /api/public/v2/observations?name=mcp_ask&fields=core,basic,metadata`. |

### Phase 2: OAuth (preview), required before launch

1. Choose and provision the authorization server (Vercel Marketplace first), against the requirements in §4.
2. Serve Protected Resource Metadata at `/.well-known/oauth-protected-resource` (RFC 9728). On `401`, send `WWW-Authenticate: Bearer resource_metadata=…, scope=…`.
3. Validate tokens: signature against the authorization server's JWKS (`PyJWT[crypto]` already comes with `mcp`, or use the SDK's `AuthSettings` / token-verifier hooks if they fit), plus `iss`, `aud` = our canonical `/api/mcp` URI, `exp` and scope. Return `403 insufficient_scope` when the scope is missing.
4. Switch the per-caller limiter and trace `user_id` to the hashed `sub`.
5. Contract tests: valid token, expired token, wrong audience, wrong issuer, missing scope, and static-key fallback limited to the `eval-harness`/`smoke` names.
6. Write the privacy note shown at sign-in: what is stored (an email or subject at the authorization server; questions in Langfuse traces) and for how long.

#### Phase 2 findings (2026-11-26)

| Finding | Consequence |
|---|---|
| **Provider: Descope**, via the Marketplace product *Descope MCP Auth* (`descope/mcp-auth`, free plan; resource `care-beacon-mcp-auth`, connected to Preview and Development only). Chosen over Clerk (JWT/JWKS details for MCP tokens unconfirmed), Better Auth (we'd own a security-critical authorization server and its sign-in UI) and Auth0 (not Marketplace-native). | Free tier: 7,500 MAU and about 2,000 MCP consents a month, no overage charges. Production env vars are a Phase 3 step. |
| **Each Descope MCP server has its own issuer**, `https://api.descope.com/v1/apps/agentic/<project>/<server>`, separate from the project issuer the Marketplace sets as `DESCOPE_ISSUER`. CIMD is advertised only on the MCP server's metadata. A `vercel deploy -e DESCOPE_ISSUER=…` doesn't override the integration's own variable. | `MCP_OAUTH_ISSUER` (the MCP server issuer) takes precedence over `DESCOPE_ISSUER`; discovery is derived from it. Descope console setup: MCP Server URL = `MCP_RESOURCE_URL` exactly (it becomes `aud`), scope `ask`, CIMD on, DCR off. |
| **Descope returns 403 to urllib's default `Python-urllib` user agent**, so discovery failed on the first deploy and every token got `503 auth_unavailable`. | Discovery and `PyJWKClient` send `User-Agent: care-beacon-mcp/1.0`; a test pins it. |
| `cryptography` wasn't in the runtime dependencies (mcp requires `pyjwt` without the crypto extra). | `pyjwt[crypto]==2.15.1` added to `api/requirements.txt`. |
| **CLI previews have random URLs**, and this branch's git pushes don't create previews, but `aud` must be one fixed URL. | Previews are aliased to `care-beacon-mcp-preview.vercel.app` (`vercel alias set`), and `MCP_RESOURCE_URL` is that alias's `/api/mcp`. |
| **Vercel Deployment Protection blocks OAuth discovery:** Claude fetches `/.well-known/oauth-protected-resource…` without the bypass query and gets Vercel's login redirect. | For the OAuth smoke test, protection for Preview was paused and then switched back on. Production has no Deployment Protection, so this only affects previews. |
| **OAuth smoke test passed (2026-11-27, Claude Desktop, URL only):** 401 → metadata 200 → Descope sign-in with Claude's CIMD identity → consent for `ask` → 4 × `tools/call` 200 in 9.6–15.7 s, 5 sources each (the cap held), `unmatched_markers` 0. Traces carry `user_id` `oauth:<hash>` and never the Descope user id. Descope doesn't advertise RFC 9207 `authorization_response_iss_parameter_supported`; Claude didn't need it. | The trace field `mcp.key_name` was renamed `mcp.caller`. The privacy note is in `docs/API.md` (MCP Server → Privacy) and the README; it should also be pasted into Descope's consent screen text. |

### Stage 1 acceptance (on the preview, before production)

- **CI green:** the existing baselines plus the new MCP tests.
- **Manual smoke from Claude Desktop** (OAuth sign-in with the URL only):
  - 5 questions: 2 plain, 1 with a source restriction, 1 with a high `min_similarity`, and 1 personal-advice question that should get a referral;
  - the same 5 asked on the Search page.
  - **Pass:** the tool is picked for in-scope questions (amended 2026-11-27: for an urgent personal question, Claude may answer itself as long as the referral is kept); settings arrive as asked (seen in the trace's `arguments`); citations show titles, sections and URLs that match Search's; the referral is kept; no call takes longer than 30 s.
- **One `mcp_ask` trace visible in Langfuse,** with `channel: mcp` and the client name.
- Results go in a short `evaluation/results/<date>-mcp-smoke.md`.

### Phase 3: production (only on the user's explicit request)

1. Merge, set the authorization server's env vars and `MCP_API_KEYS` (smoke key only) in Vercel Production.
2. Widen the WAF rule path to include `/api/mcp`, and verify with a burst test as on 2026-11-12.
3. Update the Langfuse live Search rule to include `mcp_ask`, and verify on one real MCP call. This gives MCP the same six live evaluator scores as Search from day one, at no extra build cost.
4. Connect Claude Desktop to production, and make one smoke call.
5. Update `CLAUDE.md` "Current Production State" (the dependency count, the `/api/mcp` endpoint, the separate MCP spend cap, the WAF paths) and `evaluation/README.md`.

#### Phase 3 findings (2026-11-27)

All five steps are done and verified in production (`https://care-beacon-health.vercel.app/api/mcp`).

| Step | Result |
|---|---|
| 1. Env vars | Descope issuer and `MCP_RESOURCE_URL` set in Production, plus `MCP_API_KEYS` (smoke key). A request without a token gets 401 with `resource_metadata` pointing at the production metadata URL. |
| 2. WAF | `api-rate-limit` now matches `/api/v1/ask`, `/api/v1/chat` and `/api/mcp`. Burst test at 18:57 UTC: 25 POSTs to `/api/mcp` with no token returned **20 × 401, then 5 × 429**. The app never returns 429 to a request without a token, so the 429s are the edge rule. No LLM calls. |
| 3. Langfuse rule | "Live Search answers (not cached)" now matches `ask` and `mcp_ask`. Two fixes were needed before MCP traces were scored: #35 (`run_ask` flushes, because the root and generation spans were lost when the instance froze) and #36 (the MCP SDK's `OpenTelemetryMiddleware` removed: on warm instances it made `mcp_ask` a child of a `tools/call` span that was never exported, so the root-only rule skipped it). Verified: two calls on one warm instance were both root spans and both got all six scores. |
| 4. Claude smoke | Claude's production connector (OAuth, URL only) answered new questions; `user_id` `oauth:1f29c966…`, `channel: mcp`. |
| 5. Docs | CLAUDE.md "Current Production State", `docs/API.md` and `evaluation/README.md` (#37). |

## Stage 2: MCP evals (optional, decided after Stage 1)

**Decision input:** a week or so of the live evaluator scores on `mcp_ask` traces, compared with `ask`. If MCP grounded and citation accuracy track Search, and the smoke check showed agents passing settings correctly, Stage 2 may not be needed. A gap, or wider public use, would justify it.

1. Datasets `mcp-tool-selection` and `mcp-agent-e2e`, plus reuse of `search-baseline` and `safety-control`.
2. `--target mcp` in `run_experiment.py`, `agent_runner.py` (agent models per §9), and the new judges with unit tests.
3. Run E1–E4 (E5's deterministic cases already run in CI from Stage 1; only the WAF burst and agent-retry rows remain) against a preview. Write `evaluation/results/<date>-mcp-gate.md`.
4. Act on findings: description wording, output format, the duplicate JSON block.

## Later, each optional

- **Listing in the Claude connector directory** (submitted through `claude.ai/directory/manage`), once OAuth is live.
- **Multi-turn** (see below).
- **MCPB desktop extension**: a thin stdio wrapper calling `/api/mcp`, for Desktop users who prefer a local install.
- `cancer_type` as an enum parameter, once the corpus has a clean list of values.
- An MCP **resource** listing the sources and what each covers, if agents turn out to need help choosing sources.

### Multi-turn chat: why it's later

The agent already holds the conversation, and E1's follow-up items check that it writes self-contained questions. That covers most of what Chat's query rewriting does. Exposing Chat would mean:

- owner keys and thread IDs in tool arguments;
- Neon writes from agents;
- a streaming endpoint collapsed into one response;
- MCP calls spending against the same per-turn chat budget.

None of that has a clear payoff until E1/E3 show agents writing poor follow-ups. If they do, the cheaper fix is an optional `context` string parameter that Care Beacon's existing rewriter uses to make the question standalone, which is still stateless, rather than exposing threads.

## 8. Risks

- **Public MCP budget can run out:** with anyone able to sign up, the $2 MCP cap could be reached by many accounts each staying under its own limit. When it is, MCP refuses calls until 00:00 UTC. That is the intended failure mode, but it may need a sign-up throttle at the authorization server.
- **Shared IP bucket at the WAF:** all connector traffic shares Anthropic's IPs, so the WAF rule is only a backstop. The per-user limit after Phase 2 is the real control.
- **SDK on serverless:** v2 is new (July 2026). Phase 0 exists to catch mount, lifespan and cold-start problems before any real work.
- **Retrieval numbers move with the re-ingest:** always compare MCP against Search measured in the same window, never against the 2026-11-12 figures.
- **Clients may ignore `structuredContent`:** hence the readable Markdown block first.

## 9. Decisions and open questions

**Decided (2026-11-16):**

1. **Audience: anyone.** Ship OAuth. Use a static key during development, and add OAuth once the MCP logic works (Phase 2, before launch).
2. **Default `min_similarity`: 0.5.**
3. **Spend cap: a new MCP-only cap of $2/day,** separate from Chat's (§3.3).
4. **Staging (2026-11-22):** build and ship the server first (Stage 1). The MCP eval suite is Stage 2, decided afterwards.

**Still open:**

5. **Eval agent models (Stage 2 only).** No eval today runs an agent in the loop. Every existing LLM call in `evaluation/` is OpenAI `gpt-4o-mini`:
   - the system under test (all roles);
   - our judges (`JUDGE_MODEL` in `evaluation/langfuse/judges.py`, temperature 0);
   - the six Langfuse live evaluators.

   E1 and E3 need a *client* model that chooses whether to call the tool. Since the main target is Claude Desktop, the proposal is **`claude-sonnet-5-5`** as the main agent and **`claude-haiku-5-5`** as a cheap-client check. That means a new `ANTHROPIC_API_KEY` in `evaluation/.env` and about $3–5 per gate run. Optionally, add `gpt-4o-mini` as a third agent to cover a non-Claude client with no new key. Judges stay `gpt-4o-mini`, so scores remain comparable with the Phase 1 gate. Using a different vendor for the agent than for the judge also keeps the judge from grading its own model's output.
6. **Per-caller limits:** are 10/minute and 50/day right for public users?
7. **`cancer_type`:** leave it out until there's an enum (recommended), or expose it as free text?
8. **Duplicate JSON text block:** keep it, as the spec's SHOULD, or decide after E4's size measurement?
9. **Tool name:** `ask_care_beacon` (recommended) vs something more generic like `ask_cancer_question`?
10. **Authorization server provider:** chosen at the start of Phase 2 (Vercel Marketplace first).

## 10. Sources

Read on 2026-11-16:

- MCP 2026-07-28 changelog: https://modelcontextprotocol.io/specification/2026-07-28/changelog
- Tools: https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- Transports / Streamable HTTP: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports and https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- Authorization: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
- Schema (partly read; the annotation defaults come from a summary): https://modelcontextprotocol.io/specification/2026-07-28/schema
- Release blog post: https://blog.modelcontextprotocol.io/posts/2026-07-28/
- SDK betas blog post: https://blog.modelcontextprotocol.io/posts/sdk-betas-2026-07-28/
- Python SDK releases: https://github.com/modelcontextprotocol/python-sdk/releases
- PyPI metadata for `mcp`: https://pypi.org/pypi/mcp/json
- Python SDK v2, what's new: https://py.sdk.modelcontextprotocol.io/whats-new/
- Claude custom connectors: https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp
- Claude Desktop local MCP servers and MCPB: https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop
- Secondary write-ups, used only for orientation: https://aaif.io/blog/mcp-2026-07-28-whats-changing-and-how-to-migrate, https://4sysops.com/archives/2026-07-28-model-context-protocol-mcp-stateless-multi-round-trip-routable-headers-authorization-hardening/

Repository evidence:

- `api/src/api/models.py`, `api/src/api/main.py` (the `/api/v1/ask` handler)
- `api/src/chat/models.py`, `api/src/chat/spend.py`
- `api/src/observability/tracing.py`, `api/config/config.yaml`
- `web-client/components/search-interface.tsx`
- `docs/API.md`, `evaluation/README.md`, `evaluation/results/2026-11-12-phase1-gate.md`
- git `fb7701b`, `6897041`, `fd3cfb8`

Not verified, carried as Phase 0 checks:

- the v2 ASGI mount and lifespan details;
- which transport and protocol revision Claude's connector client speaks;
- whether the Hobby WAF can key on a header;
- Anthropic's egress IP ranges.
