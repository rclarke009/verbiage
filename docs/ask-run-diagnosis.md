# Diagnosing a bad Ask answer (ask_run + Tempo)

One reconstructable story per request: **what happened**, **from what**, **with what model**.

| Signal | Where |
|--------|--------|
| Structured run summary | `AskResponse.ask_run` / SSE `sources.ask_run` + JSON log `event=ask_run` |
| Phase waterfall | Tempo spans (`rag.embed` → `rag.retrieve` → `rag.llm`) |
| Aggregates | Prometheus / Grafana (`rag_phase_seconds`, refusal counters) |

Tempo stays **low-cardinality** (no chunk ids or full question on spans). Citation detail lives on `ask_run` and `top_chunks`.

## Enable

In `.env` (defaults are fine for local):

```bash
ASK_RUN_LOG_ENABLED=true          # default
# ASK_RUN_LOG_VERBOSE=1           # truncated question + snippet previews in the log line
METRICS_ENABLED=true
OTEL_ENABLED=true
OTEL_SERVICE_NAME=verbiage
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

Restart uvicorn after changing `OTEL_*`. API on **:8000**. Observability stack: `cd observability && docker compose up -d`.

Log lines land in stdout and [`logs/verbiage.log`](../logs/verbiage.log). Format includes `trace=` / `span=` when tracing is on.

## Capture one run

```bash
curl -s http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"YOUR QUESTION"}' | jq '.ask_run, .top_chunks'
```

Or ask in the UI and inspect the `/ask` or `/ask/stream` network payload (`ask_run` on the SSE `sources` event).

Grep the log:

```bash
grep '"event":"ask_run"' logs/verbiage.log | tail -1 | jq .
```

Paste `ask_run.trace_id` into Grafana Explore → Tempo → **Trace ID**.

## Decision tree (good / bad / ugly)

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

**Silent quality failure** = healthy timings and `decision=answer`, but wrong text. Distinguish retrieval miss (wrong chunk ids/docs) vs generation (right chunks, bad synthesis) using `chunks` + `top_chunks` snippets.

**Audit fields (always):** `ask_run_id`, `models.embed` / `models.llm` / `provider`, `prompt.sha256` + `prompt.chars`, chunk ids/scores/titles, `latency_ms`, gate threshold.

**Verbose only:** `ASK_RUN_LOG_VERBOSE=1` adds truncated `question_preview` and chunk `snippet`s to the **log line** (not required on the API summary).

## Known-good refused (seed / corpus)

If a grounded gold question hard-refuses:

1. `chunks` empty + low `top_cosine` or `gate.blocked=true`
2. Confirm demo seed / `eval_fixture` docs exist (`Demo startup seeded…` in logs)
3. Confirm `normalized_query_len` looks sane (instructional fluff stripped for retrieve)

## Related

- [otel-architecture.md](otel-architecture.md) — span attributes and TraceQL
- [prod-observability.md](prod-observability.md) — Render metrics/traces
- Gold set: [`tests/eval/gold_questions.yaml`](../tests/eval/gold_questions.yaml)
