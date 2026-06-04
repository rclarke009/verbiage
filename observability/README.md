# Verbiage observability (Prometheus + Grafana)

Local Docker stack that scrapes Verbiage **`GET /metrics`** and shows a pre-provisioned **Verbiage RAG** dashboard.

## Prerequisites

1. **Verbiage API** running on the host at **port 8000** with metrics enabled:
   - `METRICS_ENABLED=true` in `.env`
   - Restart the API after changing env vars
2. **Docker** (Docker Desktop on macOS is fine)

Verify metrics:

```bash
curl -s http://localhost:8000/metrics | head
# With METRICS_TOKEN set locally:
curl -s http://localhost:8000/metrics -H "Authorization: Bearer YOUR_TOKEN" | head
```

If you use a Bearer token locally, create `secrets/metrics_token` (one line, no quotes) and uncomment the `authorization` block in `prometheus.yml` plus the secrets volume in `docker-compose.yml`.

## Start the stack

```bash
cd observability
docker compose up -d
```

| Service     | URL                         |
|------------|-----------------------------|
| Grafana    | http://localhost:3000       |
| Prometheus | http://localhost:9090       |

Grafana login: **admin** / **admin** (change password on first login).

**Prometheus:** Status → Targets → `verbiage-local` should be **UP**.

**Grafana:** Dashboards → folder **Verbiage** → **Verbiage RAG**.

Use the **Environment** dropdown (top of dashboard) to filter or compare scrape targets. Each Prometheus `job_name` appears as an environment (`verbiage-local`, `verbiage-prod`, etc.). Select **All** to aggregate every target; pick one or more jobs to compare side by side.

Generate RAG metrics by asking a question in the app (`/ask` or streaming), then refresh the dashboard.

## Scrape Render production from your machine

1. Copy the job from `prometheus.prod-snippet.yml` into `prometheus.yml` under `scrape_configs`.
2. `echo -n 'YOUR_RENDER_METRICS_TOKEN' > secrets/metrics_token`
3. Uncomment in `docker-compose.yml`:
   ```yaml
   - ./secrets:/etc/prometheus/secrets:ro
   ```
4. `docker compose up -d`

Target: `https://rag-document-analysis-backend.onrender.com/metrics`

## Stop

```bash
docker compose down
```

## Metric reference

See `app/monitoring/metrics.py` and [setup.md](../setup.md#prometheus-metrics-optional).

**Verbiage RAG dashboard panels**

| Panel | Metric(s) |
|-------|-----------|
| HTTP request rate / 4xx–5xx | `http_requests_total` |
| HTTP /ask latency p95 | `http_request_duration_seconds` (POST `/ask`, `/ask/stream`; includes stream completion) |
| RAG phase latency p95 | `rag_phase_seconds` by phase + endpoint (`sync` / `stream`) |
| Empty / low-quality / no-context | `rag_retrieval_empty_total`, `rag_retrieval_low_quality_total`, `rag_no_context_response_total` |
| No-context refusal rate | `rag_no_context_response_total` ÷ successful POST `/ask` or `/ask/stream` (overall + per-route) |
| Top / mean / per-chunk cosine p50 | `rag_retrieval_top_similarity`, `rag_retrieval_mean_similarity`, `rag_retrieval_chunk_similarity` |
| Hybrid lexical & RRF p50 | `rag_retrieval_top_lexical_score`, `rag_retrieval_top_rrf_score` |
| Stream retrieval failures | `rag_stream_retrieval_failed_total` |
| Upstream timeouts & fallbacks | `upstream_timeouts_total` (by `component`), `upstream_fallback_total` |
| Scrape target | Prometheus `up` |

Set **`RAG_SIMILARITY_ALERT_THRESHOLD`** (e.g. `0.35`) in the app `.env` so the low-quality panel increments before the hard relevance gate at `RAG_MIN_RELEVANCE_SCORE` (default `0.5`).

After editing `grafana/dashboards/verbiage.json`, restart Grafana or re-import the dashboard if it was already loaded (`docker compose restart grafana`).

## Load testing and reading the dashboard

Use the repo load script to populate RAG metrics (requires a Supabase Bearer token):

```bash
python scripts/load_test_ask.py --token "$TOKEN" --count 30 --concurrency 3 --endpoint mix
```

**What looks alarming but is often expected**

| Signal | Typical cause |
|--------|----------------|
| **Top cosine p50 ~30%** + **high no-context / low-quality** | Chunks were retrieved but top cosine is below the **0.5 relevance gate** → refusal before the LLM. Not a 5xx or retrieval crash. |
| **Low-quality** without empty retrieval | `RAG_SIMILARITY_ALERT_THRESHOLD` (e.g. 0.35) fires when weak chunks exist; the gate at **0.5** still refuses. |
| **Spikes on “per hour” counters** at low QPS | `increase(...[1h])` on a handful of refusals looks like an incident; prefer **No-context refusal rate** (5m rate ratio) after enough traffic. |
| **Empty retrieval = No data** | Gate clears chunks after hybrid metrics are recorded; refusals from the gate count as **no-context**, not **empty**. |

**Before demo or production sign-off**

1. Index a real corpus on the **same DB** you query in the app.
2. Run **`make eval`** (or `make eval-quick`) — grounded gold questions should pass; unanswerable ones should refuse.
3. Smoke-test 2–3 storm-damage questions in the UI: expect **citations**, not only “I don't have relevant context…”.

**No-context refusal rate panel** divides `rag_no_context_response_total` by successful POST `/ask` or `/ask/stream` with matching `job` labels (overall + per-route). If the panel shows **No data**, check that `METRICS_ENABLED=true`, traffic hit `/ask*`, and the time range includes the load test.

**Latency** — embed + LLM dominate p95; retrieval stays sub-second. Prefer **`/ask/stream`** in the SPA for demos; sync `/ask` can look much slower under concurrent load.

## Grafana MCP / Grafana Cloud

This folder is a **self-hosted** stack. For **Grafana Cloud**, import `grafana/dashboards/verbiage.json`, point a Prometheus/Mimir scraper at each deployment’s `/metrics` URL (with Bearer token when `METRICS_TOKEN` is set), and give each scrape job a distinct `job_name` (e.g. `verbiage-prod`, `verbiage-staging`). The dashboard **Environment** variable lists those jobs so one dashboard can show all projects at once or filter to one.
