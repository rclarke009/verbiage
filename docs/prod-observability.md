# Production observability (Render)

How to enable metrics and tracing on **rag-document-analysis-backend** without a code push. Both signals initialize at **process startup** — changing env vars in the Render dashboard requires a **restart** (Manual Deploy → Deploy latest commit, or Restart service). You do **not** need to merge new code unless you are changing the app itself.

**Local stack:** [observability/README.md](../observability/README.md) · **Why traces look like this:** [otel-architecture.md](otel-architecture.md)

---

## Two tiers

| Tier | When to use | Render env | Restart needed? | Historical data |
|------|-------------|------------|-----------------|-----------------|
| **A — Metrics always on** | Baseline dashboards, alerts, incident triage | `METRICS_ENABLED=true` + `METRICS_TOKEN` | Once at setup | From first scrape after enable |
| **B — Traces on demand** | Debug one slow/broken `/ask` | Also `OTEL_ENABLED=true` + OTLP endpoint | Each time you flip tracing | **Forward only** — no traces from before enable |

**Recommendation:** enable **Tier A** on prod permanently (low overhead). Turn on **Tier B** when you need per-request span waterfalls, then turn it off again if you want zero OTLP export cost.

---

## Tier A — Metrics (recommended baseline)

### Render environment variables

Set these on **rag-document-analysis-backend** in the Render dashboard (Environment):

| Variable | Value | Notes |
|----------|-------|-------|
| `METRICS_ENABLED` | `true` | Registers `GET /metrics` and HTTP timing middleware at startup |
| `METRICS_TOKEN` | *(generate a long random secret)* | Scrapers must send `Authorization: Bearer <token>` or `/metrics` returns 401 |
| `RAG_SIMILARITY_ALERT_THRESHOLD` | `0.35` *(optional)* | Increments `rag_retrieval_low_quality_total` before the hard 0.5 relevance gate |

Then **restart** the service so `/metrics` is registered.

### Verify

```bash
curl -s "https://rag-document-analysis-backend.onrender.com/metrics" \
  -H "Authorization: Bearer YOUR_METRICS_TOKEN" | head
```

You should see Prometheus text including `http_requests_total`, `rag_phase_seconds`, etc.

### Where to view metrics

**Option 1 — Grafana Cloud (prod-native)**

1. Create a [Grafana Cloud](https://grafana.com/products/cloud/) stack (free tier is enough to start).
2. In Grafana Cloud → **Connections** → **Add new connection** → **Hosted Prometheus metrics** (Mimir), note the **remote write / scrape** instructions.
3. Add a scrape job for your Render URL, e.g.:

   ```yaml
   - job_name: verbiage-prod
     scheme: https
     metrics_path: /metrics
     scrape_interval: 30s
     static_configs:
       - targets: ["rag-document-analysis-backend.onrender.com"]
     authorization:
       type: Bearer
       credentials: YOUR_METRICS_TOKEN   # or use credentials_file in agent config
   ```

   Use Grafana Cloud Agent, Alloy, or Prometheus remote-write — whichever your stack provides. Give the job a distinct name (`verbiage-prod`) so the dashboard **Environment** dropdown can filter prod vs local.

4. Import [observability/grafana/dashboards/verbiage.json](../observability/grafana/dashboards/verbiage.json) into Grafana Cloud.

**Option 2 — Scrape prod from your laptop**

Follow [observability/README.md § Scrape Render production](../observability/README.md#scrape-render-production-from-your-machine): local Docker Prometheus pulls `https://rag-document-analysis-backend.onrender.com/metrics` with the Bearer token. Good for ad-hoc debugging without standing up Grafana Cloud.

### What metrics tell you in an incident

| Symptom | Metrics to check |
|---------|------------------|
| Slow answers | `http_request_duration_seconds` (POST `/ask`, `/ask/stream`), `rag_phase_seconds` by phase |
| Wrong refusals | `rag_no_context_response_total`, `rag_retrieval_top_similarity`, low-quality counter |
| Upstream failures | `upstream_timeouts_total`, `upstream_fallback_total` |
| Retrieval broken | `rag_retrieval_empty_total`, `rag_stream_retrieval_failed_total` |

Metrics are **aggregates** — they show that p95 LLM latency spiked, not *which* request was slow. That is what Tier B is for.

---

## Tier B — Traces (on-demand debugging)

Tracing is **off by default** (`OTEL_ENABLED` unset). When disabled, the app pays zero OTLP export cost and **does not retain spans** for later.

### Render environment variables

Add or set on restart:

| Variable | Example (Grafana Cloud) | Notes |
|----------|-------------------------|-------|
| `OTEL_ENABLED` | `true` | Required — read once at import; must restart |
| `OTEL_SERVICE_NAME` | `verbiage-prod` | Distinguish prod from local `verbiage` in Tempo |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://otlp-gateway-prod-us-central-0.grafana.net/otlp` | **Not** `localhost` — must be reachable from Render |

For **Grafana Cloud OTLP**:

1. Grafana Cloud → **Connections** → **OpenTelemetry (OTLP)**.
2. Copy the **HTTP** endpoint (host only, no `/v1/traces` suffix — the app appends that).
3. If the gateway requires basic auth, set standard OTel env vars your SDK supports, e.g.:

   ```bash
   OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64(instance_id:api_token)>
   ```

   (Grafana Cloud docs show the exact header value for your stack.)

4. Restart Render after all `OTEL_*` vars are set.

**Local dev** uses the Docker collector:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

That URL is **not** valid from Render — the collector runs on your machine.

### Verify traces

1. Hit `/ask` or `/ask/stream` on prod (or run a load test).
2. Grafana Cloud → **Explore** → **Tempo** (or self-hosted Tempo locally).
3. Search: `{resource.service.name="verbiage-prod"}` — see [otel-architecture.md § TraceQL](otel-architecture.md#useful-grafana-tempo-queries-traceql).

Expected waterfall: `POST /ask` → `rag.embed` → httpx child → `rag.retrieve` → `rag.llm` → httpx child.

### Turn tracing off again

Set `OTEL_ENABLED` to empty or `false`, restart. No code change.

---

## Incident playbook

**Something is broken in prod right now**

1. **Check Render** — deploy logs, CPU/memory, recent deploys, `/health` and `/health/deep`.
2. **If Tier A is on** — open Grafana, check HTTP 5xx rate, `rag_phase_seconds`, refusal counters for the incident window.
3. **If Tier A is off** — set `METRICS_ENABLED=true`, `METRICS_TOKEN`, restart. Metrics appear **from restart forward** only; you cannot backfill the incident window.
4. **Need one request explained** — enable Tier B (`OTEL_ENABLED=true` + OTLP endpoint), restart, reproduce the failure (or wait for traffic), search Tempo. Traces exist **only after** tracing was initialized.
5. **Reproduce locally** — copy prod `.env` patterns, enable OTEL, run `observability/docker compose up -d`, replay the question. [`make eval` does not produce HTTP traces](otel-architecture.md) — use the UI or `/ask/stream`.

**No git push required** for steps 3–4 — only Render env vars + restart.

---

## Quick reference — Render dashboard checklist

### Minimum prod (metrics only)

```
METRICS_ENABLED=true
METRICS_TOKEN=<long-random-secret>
```

→ Restart service → configure Grafana Cloud or local Prometheus scrape → import dashboard.

### Incident debug (metrics + traces)

```
METRICS_ENABLED=true
METRICS_TOKEN=<long-random-secret>
OTEL_ENABLED=true
OTEL_SERVICE_NAME=verbiage-prod
OTEL_EXPORTER_OTLP_ENDPOINT=https://<your-grafana-cloud-otlp-host>
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <...>   # if required by your backend
```

→ Restart → reproduce → Explore in Tempo → disable `OTEL_ENABLED` when done.

---

## FAQ

**Do I need to redeploy from git?**  
No. Restart the same deployed image after env changes.

**Will `--reload` locally pick up `.env` changes for OTEL?**  
No. Tracing initializes at import time; restart uvicorn after changing any `OTEL_*` var ([otel-architecture.md](otel-architecture.md)).

**Can I see traces for requests that already failed?**  
No. Spans are exported in real time; there is no retroactive trace store when `OTEL_ENABLED` was off.

**Is `/metrics` public?**  
Only if you skip `METRICS_TOKEN`. Always set a token on prod.

**Demo service (`verbiage-demo`)?**  
Same vars apply; use `OTEL_SERVICE_NAME=verbiage-demo` and a separate Prometheus `job_name` if you scrape both.

---

## Alert notifications (Grafana Cloud)

The **Profile → Email** field in Grafana is your user account, not the alert destination. For prod email notifications:

1. **Alerting → Contact points → New contact point → Email** — enter your real address.
2. **Alerting → Notification policies** — ensure firing alerts route to that contact point (Grafana Cloud includes email by default).
3. **Alerting → Alert rules** — create rules against your Mimir/Prometheus datasource.

Example rules (same PromQL as `observability/grafana/provisioning/alerting/alert_rules.yaml`; adjust `job` if your scrape job is not `verbiage-prod`):

| Alert | PromQL (instant) | For | Threshold |
|-------|------------------|-----|-----------|
| Scrape down | `up{job="verbiage-prod"}` | 2m | `< 1` |
| 5xx spike | `sum(rate(http_requests_total{job="verbiage-prod",status_class="5xx"}[5m]))` | 5m | `> 0.01` |
| Upstream timeout | `sum(increase(upstream_timeouts_total{job="verbiage-prod"}[15m]))` | 0m | `> 0` |
| Low-quality retrieval | `sum(rate(rag_retrieval_low_quality_total{job="verbiage-prod"}[5m]))` | 10m | `> 0.1` |
| /ask p95 slow | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="verbiage-prod",route=~"/ask.*",method="POST"}[5m])) by (le))` | 10m | `> 120` |
| Stream retrieve fail | `sum(increase(rag_stream_retrieval_failed_total{job="verbiage-prod"}[15m]))` | 0m | `> 0` |

Set **`RAG_SIMILARITY_ALERT_THRESHOLD=0.35`** on Render so the low-quality counter increments before the hard relevance gate.

For the **local Docker stack**, edit `observability/grafana/provisioning/alerting/alert_resources.yaml` (contact point `addresses`), copy `observability/.env.example` → `observability/.env`, set `GF_SMTP_*`, and restart Grafana — rules are provisioned automatically. See [observability/README.md § Alerting](../observability/README.md#alerting-email-notifications).
