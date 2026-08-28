# Investigating Ask bugs with Verbiage debug tools

This guide is for developers triaging incorrect, refused, or flaky Ask answers. It covers the tools we use day to day, when to reach for each one, and what to attach when you open a bug or PR.

Field reference (decisions, env flags, audit fields): [ask-run-diagnosis.md](ask-run-diagnosis.md). Span model and TraceQL: [otel-architecture.md](otel-architecture.md).

## What you have available

| Tool | Best for | How to use |
|------|----------|------------|
| **`ask_run` on the response** | Immediate diagnosis of a request you just made | Inspect Network tab (`/ask` or SSE `sources`) or `curl` + `jq` |
| **JSON log line** (`event=ask_run`) | Correlating with server logs / Trace ID | `grep '"event":"ask_run"' logs/verbiage.log` |
| **Request-scoped debug** (`?debug=1` or `X-Verbiage-Debug: 1`) | Extra detail (question preview, chunk snippets) on one request only | Add to a single curl or replay; no process restart |
| **Ring buffer** (`GET /debug/ask-runs`) | “It was wrong a few minutes ago” without a full repro | List recent runs, then fetch by `ask_run_id` |
| **Tempo traces** | Latency / missing stages / errors in the pipeline | Grafana [http://localhost:3000](http://localhost:3000) → Explore → Tempo; paste `ask_run.trace_id` (see [end-to-end](#end-to-end-reproduce-with-ask_run--tempo-trace)) |
| **Prometheus / Grafana** | Trends and regressions (refusals, phase latency) | Local stack or prod dashboards — not for a single answer’s content |

**Design rule:** Tempo spans stay low-cardinality (no full questions or chunk bodies). Citation and content detail live on `ask_run`, the HTTP response, the log line (when verbose/debug), and the ring buffer.

## Local prerequisites

1. API on **:8000** (default).
2. Defaults are usually enough:

   ```bash
   ASK_RUN_LOG_ENABLED=true      # default
   ASK_RUN_BUFFER_ENABLED=true   # default; disable on prod if process-memory PII is a concern
   ```

3. **Tracing (Tempo)** — optional for content bugs; recommended for timing, missing stages, or crashes. Two parts must both be up: the API exporting spans, and the Docker stack receiving them.

   Put these in `.env` (preferred) or export them in the same shell before starting uvicorn:

   ```bash
   OTEL_ENABLED=true
   OTEL_SERVICE_NAME=verbiage
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
   ```

   Start the observability stack, then restart the API (tracing initializes at import time; editing `.env` alone does not pick up `OTEL_*`):

   ```bash
   cd observability && docker compose up -d
   # then restart uvicorn, e.g.:
   # uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   **How to know tracing is on**

   - Uvicorn startup should log:
     `OpenTelemetry tracing enabled (service=verbiage, endpoint=http://localhost:4318)`
   - If you see `OpenTelemetry tracing disabled (OTEL_ENABLED not set)`, it is off.
   - After an `/ask`, `ask_run.trace_id` should be a non-null hex string. `null` / missing means tracing was not initialized for that process.

   Shell exports only last for that process. If you restarted uvicorn later without `.env` (or re-exporting), tracing is probably off again.

## Workflow A — You can reproduce the question now

Use this when you still have the question (or a close variant) and can hit `/ask` again.

### End-to-end: reproduce with `ask_run` + Tempo trace

Use this when you want one complete pass: structured run summary **and** the Tempo waterfall.

1. **Enable tracing** (see [Local prerequisites](#local-prerequisites) §3): `OTEL_*` in `.env`, `cd observability && docker compose up -d`, restart uvicorn. Confirm the startup line says tracing **enabled**.
2. **Ask the question** (UI or curl below). Capture `ask_run` from the JSON response, Network tab, or SSE `sources` event.
3. **Confirm** `ask_run.trace_id` is present. If it is null, stop — tracing is off or the API was not restarted after enabling OTEL.
4. **Open Tempo in Grafana** (there is no separate Tempo UI):
   1. Browser: [http://localhost:3000](http://localhost:3000) — login **admin** / **admin**
   2. Left nav → **Explore**
   3. Datasource → **Tempo**
   4. Paste `ask_run.trace_id` into **Trace ID**, *or* use **Search** with `{resource.service.name="verbiage"}` and time range **Last 15 minutes**
   5. Open the trace: expect `POST /ask` (or `/ask/stream`) → `rag.embed` → `rag.retrieve` → optional `rag.rerank` → `rag.llm`
5. **Classify** with `ask_run.decision` (table below), then attach `ask_run_id` + `trace_id` + `ask_run` JSON to the bug.

If Grafana is down or compose is not running, the API can still log “tracing enabled” but nothing will appear in Tempo.

### Capture and classify

1. **Capture the structured run**

   ```bash
   curl -s http://127.0.0.1:8000/ask \
     -H 'Content-Type: application/json' \
     -d '{"question":"YOUR QUESTION"}' \
     | tee /tmp/ask-response.json \
     | jq '{ask_run, top_chunks: [.top_chunks[] | {chunk_id, doc_id, score, title: .document_title}]}'
   ```

   Or ask in the UI and copy `ask_run` from the Network response / SSE `sources` event. Same summary also appears as a JSON log line with `event=ask_run`.

2. **Add verbose detail for this request only** (snippets + question preview in logs and on `ask_run.question_preview`):

   ```bash
   curl -s 'http://127.0.0.1:8000/ask?debug=1' \
     -H 'Content-Type: application/json' \
     -d '{"question":"YOUR QUESTION"}' | jq '.ask_run'
   ```

   Equivalent header: `X-Verbiage-Debug: 1`. Prefer this over setting `ASK_RUN_LOG_VERBOSE=1` process-wide.

3. **Classify the failure** using `ask_run.decision`:

   | `decision` | Typical meaning | Next check |
   |------------|-----------------|------------|
   | `hard_refuse` | Gate / empty retrieve; little or no LLM | `gate.blocked`, `top_cosine`, empty `chunks` |
   | `soft_refuse` | Model (or rewrite) refused despite chunks | Chunk quality; `rewrite.retried` |
   | `answer` | Pipeline “succeeded” but content may be wrong | Compare `chunks` / `top_chunks` to the answer (retrieval miss vs bad synthesis) |
   | `nearby_storm` | Geo route, not LLM RAG | Claim / storm context inputs |
   | `error` | Exception path | `error_type`, stack in app logs |

4. **Open the Tempo waterfall** — follow [End-to-end: reproduce with ask_run + Tempo trace](#end-to-end-reproduce-with-ask_run--tempo-trace) steps 4–5. Confirm which phases ran and whether spans are marked error.

5. **File the bug** with the checklist at the end of this doc.

## Workflow B — You cannot reproduce (or the user only reported “it was weird”)

RAG failures are often phrasing- or timing-sensitive. Prefer the ring buffer over asking someone to “try again.”

1. **List recent runs** (newest first):

   ```bash
   curl -s 'http://127.0.0.1:8000/debug/ask-runs?limit=20' | jq .
   ```

2. **Identify the suspect** by `question_preview`, `decision`, time order, or `ask_run_id` if the reporter still has it from the UI/network tab.

3. **Fetch the full buffered record**:

   ```bash
   curl -s "http://127.0.0.1:8000/debug/ask-runs/$ASK_RUN_ID" | jq .
   ```

   You get the compact `ask_run` summary plus `question_preview`, `answer_preview`, chunk snippets, and optional `rewritten_query` — enough to distinguish retrieval miss from generation error without another live call.

4. **Correlate with Tempo** via `trace_id` on the buffered record when tracing was enabled for that process.

5. **Note buffer limits:** in-memory, last N runs (`ASK_RUN_BUFFER_SIZE`, default 50), lost on process restart. If the buffer is disabled, these endpoints return **404**.

## Workflow C — Crash, timeout, or SSE `retrieval_failed`

1. Check the SSE `error` event or HTTP status; `ask_run.decision` should be `error` with `error_type` when the stream path emitted a run record.
2. Search logs for the same `ask_run_id` or `trace_id`.
3. In Tempo, look for error status on `rag.*` spans and on the FastAPI request span.
4. Reproduce once with `?debug=1` if the failure is intermittent and you need snippet context around the last successful retrieve.

## Separating “wrong retrieval” from “wrong generation”

When `decision` is `answer` but the text is wrong:

| If… | Likely layer | Evidence |
|-----|--------------|----------|
| Cited docs/chunks are irrelevant to the question | Retrieval / gate / rerank | Low or misleading scores; wrong `doc_id`s in `ask_run.chunks` |
| Chunks are on-topic but the answer invents or ignores them | Generation / prompt | Strong chunks + mismatched `answer` / `answer_preview` |
| Soft refuse then still wrong after rewrite | Corrective path | `rewrite.retried`, compare original vs `rewritten_query` |

Do not rely on Tempo alone for this split — spans show *that* retrieve and LLM ran, not *what* was retrieved.

## What to attach when reporting a bug

Include as many of these as you have:

- [ ] Question text (or `question_preview` from the buffer)
- [ ] `ask_run_id` and `trace_id`
- [ ] Full `ask_run` JSON (or buffered `/debug/ask-runs/{id}` payload)
- [ ] Observed answer (or `answer_preview`) and expected behavior
- [ ] Whether you used `?debug=1` / `X-Verbiage-Debug: 1`
- [ ] Environment notes: local vs demo vs prod; `DEMO_MODE`; embed/LLM provider from `ask_run.models`
- [ ] Timestamp or approximate time (for buffer / log correlation)

Redact or avoid pasting full prompts and PII into public tickets when possible; prefer ids, hashes (`prompt.sha256`), and truncated previews.

## Privacy and production notes

- Compact `ask_run` (ids, scores, models, latencies) is safe for routine logging.
- Verbose / debug / buffer records may include question and snippet text — treat as sensitive.
- Prefer **request-scoped debug** over global `ASK_RUN_LOG_VERBOSE` in shared environments.
- On production, set `ASK_RUN_BUFFER_ENABLED=false` if holding recent question/answer text in process memory is not acceptable. Debug list/detail routes then return 404.
- Do not enable unauthenticated debug tooling as a long-term production support channel without auth; these endpoints are intended for local and trusted environments.

## Related docs

- [ask-run-diagnosis.md](ask-run-diagnosis.md) — Field reference: decisions, env flags, Tempo shapes
- [otel-architecture.md](otel-architecture.md) — Span model and TraceQL
- [prod-observability.md](prod-observability.md) — Render metrics and traces
- [faithfulness-and-rag-metrics-walkthrough.md](faithfulness-and-rag-metrics-walkthrough.md) — Eval / grounding metrics (quality over time, not a single request)
