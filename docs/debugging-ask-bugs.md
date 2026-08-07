# Investigating Ask bugs with Verbiage debug tools

This guide is for developers triaging incorrect, refused, or flaky Ask answers. It covers the tools we use day to day, when to reach for each one, and what to attach when you open a bug or PR.

For field-level reference (decision values, env flags, Tempo attributes), see [ask-run-diagnosis.md](ask-run-diagnosis.md) and [otel-architecture.md](otel-architecture.md).

## What you have available

| Tool | Best for | How to use |
|------|----------|------------|
| **`ask_run` on the response** | Immediate diagnosis of a request you just made | Inspect Network tab (`/ask` or SSE `sources`) or `curl` + `jq` |
| **JSON log line** (`event=ask_run`) | Correlating with server logs / Trace ID | `grep '"event":"ask_run"' logs/verbiage.log` |
| **Request-scoped debug** (`?debug=1` or `X-Verbiage-Debug: 1`) | Extra detail (question preview, chunk snippets) on one request only | Add to a single curl or replay; no process restart |
| **Ring buffer** (`GET /debug/ask-runs`) | “It was wrong a few minutes ago” without a full repro | List recent runs, then fetch by `ask_run_id` |
| **Tempo traces** | Latency / missing stages / errors in the pipeline | Paste `trace_id` from `ask_run` into Grafana Explore |
| **Prometheus / Grafana** | Trends and regressions (refusals, phase latency) | Local stack or prod dashboards — not for a single answer’s content |

**Design rule:** Tempo spans stay low-cardinality (no full questions or chunk bodies). Citation and content detail live on `ask_run`, the HTTP response, the log line (when verbose/debug), and the ring buffer.

## Local prerequisites

1. API on **:8000** (default).
2. Defaults are usually enough:

   ```bash
   ASK_RUN_LOG_ENABLED=true      # default
   ASK_RUN_BUFFER_ENABLED=true   # default; disable on prod if process-memory PII is a concern
   ```

3. For traces (optional but recommended when debugging timing or crashes):

   ```bash
   OTEL_ENABLED=true
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
   cd observability && docker compose up -d
   ```

   Restart uvicorn after changing `OTEL_*`.

## Workflow A — You can reproduce the question now

Use this when you still have the question (or a close variant) and can hit `/ask` again.

1. **Capture the structured run**

   ```bash
   curl -s http://127.0.0.1:8000/ask \
     -H 'Content-Type: application/json' \
     -d '{"question":"YOUR QUESTION"}' \
     | tee /tmp/ask-response.json \
     | jq '{ask_run, top_chunks: [.top_chunks[] | {chunk_id, doc_id, score, title: .document_title}]}'
   ```

   Or ask in the UI and copy `ask_run` from the Network response / SSE `sources` event.

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

4. **Open the Tempo waterfall** (if OTEL is on): copy `ask_run.trace_id` → Grafana Explore → Tempo → Trace ID. Confirm which phases ran (`rag.embed` → `rag.retrieve` → optional `rag.rerank` → `rag.llm`) and whether spans are marked error.

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

- [ask-run-diagnosis.md](ask-run-diagnosis.md) — Field reference, decision tree, env flags
- [otel-architecture.md](otel-architecture.md) — Span model and TraceQL
- [prod-observability.md](prod-observability.md) — Render metrics and traces
- [faithfulness-and-rag-metrics-walkthrough.md](faithfulness-and-rag-metrics-walkthrough.md) — Eval / grounding metrics (quality over time, not a single request)
