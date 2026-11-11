---
claude_sessions:
  - "2026-11-11 · Chat UX upgrade · claude://claude.ai/epitaxy/local_5d471c4c-0a7f-42f1-9630-695d8199821b"
---

# Serverless streaming spike: findings (Task 7)

**Decision: Go with commit-fallback for interrupted turns.** Checks 1 and 2 passed. Check 3 failed in a specific way: the `GeneratorExit` handler never ran, because the generator was never interrupted. It kept running to the end after the client went away.

## Setup

- Probe: `api/src/api/spike.py` (removed after the spike), mounted at `GET /api/v1/_spike/stream`. A FastAPI `StreamingResponse` over a **sync** generator: one `meta` frame, then `n` (default 10) SSE frames 300 ms apart. Then `INSERT INTO spike_writes (id, at)` through `src.db.connection.connect()` (pooled `DATABASE_URL`), then a final `done` frame. On `except GeneratorExit` it inserts `<run>:disconnected` and re-raises. Default response headers: `Cache-Control: no-cache` and `X-Accel-Buffering: no`. `hdr=0` turns both off.
- Scratch table `spike_writes(id text, at timestamptz)`: created with the unpooled URL, dropped at the end (`to_regclass` returned NULL after the drop). No other table was touched.
- Preview deployments only (`vercel deploy --yes`, never `--prod`):
  - `care-beacon-health-jybhx1wa5-kam-lau-s-projects.vercel.app` (checks 1 to 3)
  - `care-beacon-health-ihgl7ctrx-kam-lau-s-projects.vercel.app` (adds `n`/`hdr` params: header-free and long-stream disconnect runs)
- Deployment protection: plain `curl` gets a `302` to `vercel.com/sso-api`. All requests went through **`vercel curl`** (CLI 54.14.0, beta). On first use it printed that it was generating a deployment protection bypass token for the project. Protection settings were not changed by hand.
- Python runtime observed in the function: **3.12.16**.
- Timestamps come from `perl -MTime::HiRes` on each line as it arrives. t=0 is when the `vercel curl` CLI starts, so the first ~1.2-2.2 s is CLI project lookup plus TTFB. The `t=` inside each frame is the server's monotonic clock since the generator started.

## Check 1: No buffering. PASS

Command (one run, warm):

```bash
vercel curl "/api/v1/_spike/stream?run=run1" --deployment <preview> -- -sN 2>/dev/null \
  | perl -MTime::HiRes=time -ne 'BEGIN{$t0=time} next unless /^(data|event)/; printf "%7.3f %s", time-$t0, $_'
```

Raw evidence (run1; runs 2 to 5 have the same shape):

```
  1.486 event: meta
  1.486 data: run=run1 py=3.12.16
  1.861 data: frame 0 t=0.300
  2.076 data: frame 1 t=0.601
  2.377 data: frame 2 t=0.901
  2.678 data: frame 3 t=1.202
  3.032 data: frame 4 t=1.503
  3.280 data: frame 5 t=1.804
  3.580 data: frame 6 t=2.105
  3.891 data: frame 7 t=2.405
  4.182 data: frame 8 t=2.706
  4.482 data: frame 9 t=3.007
  4.512 event: done
  4.512 data: written t=3.037
```

Without `Cache-Control: no-cache` / `X-Accel-Buffering: no` (`hdr=0`, first request to a fresh deployment):

```
  1.717 HTTP/2 200
  1.718 cache-control: public, max-age=0, must-revalidate
  1.718 content-type: text/event-stream; charset=utf-8
  1.728 event: meta
  2.107 data: frame 0 t=0.300
  2.319 data: frame 1 t=0.601
  2.630 data: frame 2 t=0.902
  ...
  4.734 data: frame 9 t=3.006
  4.788 event: done
```

Verdict: frames arrive about 300 ms apart (jitter is roughly ±100 ms) with or without the anti-buffering headers. Vercel does not buffer a sync-generator `StreamingResponse`. In 2 of 7 runs (run2, run5), frame 0 arrived only ~0.03-0.13 s after `meta`, and every frame after that was on cadence. That looks like first-byte jitter, not buffering.

## Check 2: In-stream write completes. PASS (5/5)

Command: the check 1 loop for `run1` to `run5`, then

```sql
SELECT id, at FROM spike_writes ORDER BY at;
```

Raw evidence:

```
warm0:complete 2026-11-11T23:38:55.969860+00:00
run1:complete  2026-11-11T23:39:08.690375+00:00
run2:complete  2026-11-11T23:39:13.812760+00:00
run3:complete  2026-11-11T23:39:18.428199+00:00
run4:complete  2026-11-11T23:39:22.847437+00:00
run5:complete  2026-11-11T23:39:27.804082+00:00
```

Every run's `done` frame came 25-45 ms after frame 9. That gap is a fresh pooled Neon connection plus an INSERT.

Verdict: a DB write inside the generator, before the last frame, completed on 5/5 runs (7/7 counting the warm-up and `hdr=0` runs).

## Check 3: Disconnect. FAIL (`GeneratorExit` never fires), but the generator runs to completion

Command: read until `frame 2`, then `pkill -9` the curl process (3 runs at n=10, 2 runs at n=40):

```bash
vercel curl "/api/v1/_spike/stream?run=disc1" --deployment <preview> -- -sN 2>/dev/null \
  | RUN=disc1 perl -MTime::HiRes=time -ne 'BEGIN{$|=1;$t0=time} next unless /^(data|event)/;
      printf "%7.3f %s", time-$t0, $_;
      if (/frame 2 /) { system("pkill -9 -f \"curl.*run=$ENV{RUN}\""); printf "%7.3f KILLED curl\n", time-$t0; exit 0 }'
```

Client side (disc1; the others are the same):

```
  1.465 event: meta
  1.757 data: frame 0 t=0.300
  2.058 data: frame 1 t=0.601
  2.359 data: frame 2 t=0.902
  2.497 KILLED curl
```

Rows 15-20 s later:

```
disc1:complete     2026-11-11T23:39:54.058989+00:00
disc2:complete     2026-11-11T23:39:56.362614+00:00
disc3:complete     2026-11-11T23:39:58.729166+00:00
longdisc1:complete 2026-11-11T23:42:08.035447+00:00   # n=40: client killed at ~0.9 s, generator started ~23:41:56
longdisc2:complete 2026-11-11T23:42:10.236527+00:00
```

No `:disconnected` row appeared in any run.

Verdict: client disconnects do not reach the sync generator on Vercel. `GeneratorExit` is never raised, so the handler-based save cannot work. The generator keeps yielding into the void until it finishes: about 12 s after the disconnect in the n=40 runs. Its final write still happens.

## Decision (per brief Step 3)

**Go with commit-fallback.**

- Tasks 13-14 proceed as written. The guaranteed writes go inside the generator, before the `done` frame (checks 1 and 2).
- Interrupted turns cannot be saved from a `GeneratorExit` handler (check 3). Use the spec's fallback: the client re-sends the partial text, and Task 14 adds `POST /api/v1/threads/{id}/messages/{message_id}/commit`.

## Surprises and things Tasks 13-14 should know

1. **A stream that has started does not stop when the user leaves.** The server keeps running the whole turn, including the LLM call and the final write. Consequences:
   - The **commit fallback can race the server's own final write**. After a "stop", the server may still persist the full answer seconds later. The commit endpoint needs a clear rule, such as "commit wins if the message is still `streaming`, and the server's final write must not overwrite a `committed`/`interrupted` row" (for example a conditional `UPDATE ... WHERE status = 'streaming'`).
   - **A client "stop" does not save LLM tokens.** Cancellation needs a server-side signal (for example a flag the generator checks between tokens), or acceptance of the cost.
   - We only observed this to 12 s. Behaviour near the function's `maxDuration` was not tested, and it is not documented, so do not rely on the server-side completion as the save path.
2. **Anti-buffering headers are not required** on Vercel. Keep `Cache-Control: no-cache` anyway: without it the response carries `cache-control: public, max-age=0, must-revalidate`. `X-Accel-Buffering: no` is harmless.
3. **Cold start was not observable** at this resolution. The first request to a fresh deployment had headers at 1.72 s from CLI start, against 1.2-2.2 s for warm requests. The variance is dominated by `vercel curl`'s project lookup.
4. **Preview `/api/health` returns 500** (TTFB ~1.2 s), not the documented 503. The preview has no Qdrant/OpenAI/Redis keys. The app still booted and served the probe. Worth a look separately.
5. **Function runtime is Python 3.12.16.**
6. **`vercel curl` generated a protection bypass token for the project** the first time it was used. No protection setting was changed by hand.
