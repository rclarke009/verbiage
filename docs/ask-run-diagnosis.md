# Ask run field reference

Compact reference for `ask_run` fields, env flags, and Tempo shapes. For step-by-step triage (curl, ring buffer, reproduce with a Tempo trace, what to attach to a bug), use **[debugging-ask-bugs.md](debugging-ask-bugs.md)** — especially **Workflow A → End-to-end: reproduce with ask_run + Tempo trace**.

One reconstructable story per request: **what happened**, **from what**, **with what model**. Tempo stays **low-cardinality** (no chunk ids or full question on spans). Citation detail lives on `ask_run` and `top_chunks`.

| Signal | Where |
|--------|--------|
| Structured run summary | `AskResponse.ask_run` / SSE `sources.ask_run` + JSON log `event=ask_run` |
| Recent runs (no repro) | In-memory ring buffer → `GET /debug/ask-runs` |
| Phase waterfall | Tempo spans (`rag.embed` → `rag.retrieve` → `rag.llm`) |
| Aggregates | Prometheus / Grafana (`rag_phase_seconds`, refusal counters) |

## Env flags

| Variable | Default | Role |
|----------|---------|------|
| `ASK_RUN_LOG_ENABLED` | `true` | Emit JSON `event=ask_run` + response/SSE summary |
| `ASK_RUN_LOG_VERBOSE` | `false` | Truncated question + snippet previews on the **log line** (process-wide) |
| `ASK_RUN_BUFFER_ENABLED` | `true` | Keep last N rich runs in memory; disable on prod if PII in process memory is unwanted |
| `ASK_RUN_BUFFER_SIZE` | `50` | Ring buffer capacity |
| `METRICS_ENABLED` / `OTEL_*` | — | Prometheus + Tempo; see [otel-architecture.md](otel-architecture.md) |

Request-scoped verbose (same fields as `ASK_RUN_LOG_VERBOSE`, one request only): `?debug=1` or header `X-Verbiage-Debug: 1`. Prefer over process-wide verbose in shared environments.

API default port **:8000**. Observability stack: `cd observability && docker compose up -d`. Restart uvicorn after changing `OTEL_*`.

## `ask_run.decision`

```text
ask_run.decision
├── hard_refuse     → empty/gated retrieve; no LLM (or empty chunks)
├── soft_refuse     → chunks passed gate; model (or rewrite) still refused
├── answer          → grounded path (may still be wrong — silent quality failure)
├── nearby_storm    → structured geo route (no LLM)
└── error           → exception; see error_type + app stack in logs
```

| Symptom | Check `ask_run` | Tempo shape |
|---------|-----------------|-------------|
| “I don't have relevant context…” | `decision=hard_refuse`, `gate.blocked`, `top_cosine`, empty `chunks` | No `rag.llm`; `rag.refused=true` |
| “No source documents…” | `decision=soft_refuse`; chunks present; optional `rewrite.retried` | Has `rag.llm` (maybe two if rewrite) |
| Wrong answer with citations | `decision=answer` + `chunks` / `top_chunks` content | Full healthy waterfall |
| Crash / SSE `retrieval_failed` | `decision=error`, `error_type` | `status=error` spans |

**Silent quality failure** = healthy timings and `decision=answer`, but wrong text. Distinguish retrieval miss (wrong chunk ids/docs) vs generation (right chunks, bad synthesis) using `chunks` + `top_chunks` snippets — or the buffered record if you no longer have the HTTP response.

## Audit fields

**Always:** `ask_run_id`, `trace_id` (when OTEL on), `models.embed` / `models.llm` / `provider`, `prompt.sha256` + `prompt.chars`, chunk ids/scores/titles, `latency_ms`, gate threshold.

**Verbose / debug only:** truncated `question_preview` and chunk `snippet`s on the log line; `ask_run.question_preview` in the API summary when debug/verbose is on.

**Buffered record** (`GET /debug/ask-runs/{id}`): compact `ask_run` plus `question_preview`, `answer_preview`, chunk snippets, optional `rewritten_query`. Returns **404** when `ASK_RUN_BUFFER_ENABLED=false`.

## Known-good refused (seed / corpus)

If a grounded gold question hard-refuses:

1. `chunks` empty + low `top_cosine` or `gate.blocked=true`
2. Confirm demo seed / `eval_fixture` docs exist (`Demo startup seeded…` in logs)
3. Confirm `normalized_query_len` looks sane (instructional fluff stripped for retrieve)

## Related

- [debugging-ask-bugs.md](debugging-ask-bugs.md) — How-to: workflows, curl, what to attach to a bug
- [otel-architecture.md](otel-architecture.md) — Span attributes and TraceQL
- [prod-observability.md](prod-observability.md) — Render metrics/traces
- Gold set: [`tests/eval/gold_questions.yaml`](../tests/eval/gold_questions.yaml)
