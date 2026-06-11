# Render: optional `rag-ingest-worker` (separate Background Worker)

**Default:** photo vision runs **in-process** on the web service (`INGEST_WORKER_ENABLED=1` in [`render.yaml`](../render.yaml)). No extra Render service or ~$7/mo charge.

Use a **separate worker** only if the web service OOM-restarts during large photo batches (98+ images) and you want the API to stay up while vision runs elsewhere.

## When to add a worker

| Service | Command | `INGEST_WORKER_ENABLED` | Processes jobs? |
|---------|---------|-------------------------|-----------------|
| `rag-document-analysis-backend` (web) | uvicorn | `0` | No — enqueues only |
| `rag-ingest-worker` (worker) | `python -m app.worker_main` | `1` | Yes |

If using a separate worker: set web to `INGEST_WORKER_ENABLED=0` and create the worker below. Keep `RERANK_ENABLED=0` on small instances.

---

## Step 1 — Split ingest off the web service

On **`rag-document-analysis-backend`**:

- `RERANK_ENABLED` = `0`
- `INGEST_WORKER_ENABLED` = **`0`** (worker handles jobs)

---

## Step 2 — Create the worker service

### Blueprint sync (recommended)

1. Render Dashboard → **Blueprints** → your blueprint → **Sync**.
2. Approve creation of **`rag-ingest-worker`**.
3. When prompted for `sync: false` secrets, use the **same values** as the web service (see table below).

### Manual create

1. **New +** → **Background Worker**.
2. Same repo, branch, and **Dockerfile** as web.
3. **Docker Command:** `python -m app.worker_main`
4. Copy env vars from the web service (Environment → copy values).
5. Ensure `INGEST_WORKER_ENABLED=1` (blueprint sets this automatically).

---

## Step 3 — Required worker env vars

Copy these from **`rag-document-analysis-backend`** → Environment:

| Variable | Required for |
|----------|----------------|
| `DATABASE_URL` | Job queue + claim images (Postgres) |
| `OPENAI_API_KEY` | Photo vision analysis |
| `GOOGLE_CLIENT_ID` | Drive photo download |
| `GOOGLE_CLIENT_SECRET` | Drive photo download |
| `GOOGLE_REFRESH_TOKEN` | Drive photo download |
| `GOOGLE_REDIRECT_URI` | Drive photo download |
| `INGEST_WORKER_ENABLED` | Must be `1` |

**Not needed on the worker:** `SUPABASE_*`, `PUBLIC_APP_URL`, `SIGNUP_INVITE_CODE`, `RERANK_ENABLED`, `HF_*` (web/auth/RAG only).

Optional: `STALE_JOB_MINUTES` (default `15`) — how long a job can sit in `running` before auto-reclaim after a crash.

---

## Step 4 — Verify

### Local (optional)

From repo root with `.env` populated:

```bash
.venv/bin/python scripts/check_worker_env.py
INGEST_WORKER_ENABLED=1 .venv/bin/python -m app.worker_main
```

Ctrl+C to stop. You should see `Ingest worker started` in logs.

### On Render

Open **`rag-ingest-worker`** → **Logs**. A healthy start looks like:

```text
Standalone ingest worker running (no web/reranker/report-writer)
Ingest worker started
```

If startup fails, common messages:

| Log | Fix |
|-----|-----|
| `DATABASE_URL must be set` | Add `DATABASE_URL` on worker |
| `Worker missing required env: ...` | Copy missing vars from web |
| `INGEST_WORKER_ENABLED=0; worker exiting` | Set `INGEST_WORKER_ENABLED=1` |
| Database connection errors | Same `DATABASE_URL` as web; unpause Supabase if paused |

### End-to-end

1. Open Report Writer → your claim.
2. Click **Retry stuck photos** (or **Confirm & start analysis**).
3. Worker logs should show vision jobs processing; banner counts should increase.

---

## Step 5 — Unstick existing claims

If analysis was stuck before the worker existed:

1. **Retry stuck photos** in the UI, or
2. Run the SQL in [setup.md — Stuck photo analysis](../setup.md#stuck-photo-analysis), then retry once.

---

## Cost

Two Render services bill separately (web + worker). Pausing or deleting the worker stops all background photo/Drive ingest jobs; the site will still load but jobs stay `pending`.
