# Verbiage — Setup (deployment)

How to get the app running: environment, database, Ollama, and run commands. For detailed testing and curl examples, see [setup_and_testing.md](setup_and_testing.md).

---

## Requirements

- **Python** 3.9+
- **Postgres** 15+ with [pgvector](https://github.com/pgvector/pgvector) (or use [Supabase](https://supabase.com), which includes it)
- **Ollama** (for default LLM and embeddings), or your own embedding/LLM endpoints

---

## Environment variables

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | **Yes** | Postgres connection URI. App will not start without it. |
| `OPENAI_API_KEY` | No | When set, use OpenAI for embeddings and LLM. When unset, use Ollama only. |
| `EMBED_FALLBACK_TO_LOCAL` | No | If true, use Ollama for embeddings when OpenAI fails (default: false). |
| `LLM_FALLBACK_TO_LOCAL` | No | If true, use Ollama for LLM when OpenAI fails (default: false). |
| `EMBED_BASE_URL`, `EMBED_MODEL` | No | Used for Ollama embeddings (default: `http://localhost:11434`, `nomic-embed-text`). |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_OPENAI_MODEL` | No | Ollama base/model; OpenAI model (default: `gpt-4o-mini`). See `.env.example`. |
| `LLM_TIMEOUT_SECONDS`, `LLM_RATE_LIMIT_SECONDS`, etc. | No | See `.env.example` and `app/config.py`. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_REDIRECT_URI` | No | Only for Google Drive ingest. |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Required for SPA + auth API | Returned (public fields only) via **GET /config** for the React app; required for login. |
| `SUPABASE_JWT_SECRET` | Required for protected routes | Server verifies JWT access tokens (`Authorization: Bearer`). Without this, authenticated endpoints return **503**. Keep secret server-side only. |
| `SUPABASE_SERVICE_ROLE_KEY` | No | Needed for **POST /auth/signup** when using the managed sign-up flow; never expose to the browser. |
| `CORS_ORIGINS` | No | Comma-separated origins for split deployments (browser → API from another origin). **Not needed** when using the **Vite dev proxy** (`npm run dev` → same-origin requests to `:5173` that proxy to `:8000`). |
| `METRICS_ENABLED` | No | When `true` / `1` / `yes`, registers **`GET /metrics`** (Prometheus text format) and enables HTTP timing/counters in middleware. Restart the API after changing this. |
| `METRICS_TOKEN` | No | If set, scrapes must send **`Authorization: Bearer <METRICS_TOKEN>`** or `/metrics` returns 401. |
| `RAG_SIMILARITY_ALERT_THRESHOLD` | No | Optional float (e.g. `0.35`). When set, increments **`rag_retrieval_low_quality_total`** when retrieval returns chunks but top‑1 cosine similarity is below this value. |

**Note:** There is no SQLite fallback. `DATABASE_URL` must be set to a valid Postgres URI. Default: OpenAI when `OPENAI_API_KEY` is set; otherwise Ollama.

---

## Database

1. **Create a Postgres database** (or a Supabase project).
2. **Enable pgvector** (Supabase has it by default):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. **Apply the schema** either by:
   - Running the migration in `supabase/migrations/20250302000000_phase1_schema.sql` (Supabase SQL Editor or `supabase db push`), or
   - Starting the app once: it runs `create_db(conn)` on startup and creates tables/indexes if they don’t exist.

For Supabase, use a pooler connection string from **Project Settings → Database → Connection string (URI)**. Do not use the project URL (`https://xxx.supabase.co`); use the Postgres URI that starts with `postgresql://`. The app automatically adds `sslmode=require` for Supabase pooler URLs and disables prepared statements for **transaction mode** (port 6543). Prefer **Session mode** (port **5432**) for this app: in the dashboard click **Connect** and choose **Session mode**—it supports prepared statements and is recommended for persistent backends. If you see "server closed the connection unexpectedly", try Session mode (5432), ensure the project is not **paused** (open it in the dashboard), and check the password in the URI.

Details: [supabase_migration.md](supabase_migration.md).

---

## OpenAI or Ollama

- **OpenAI (default when key is set):** Set `OPENAI_API_KEY` in `.env`. Embeddings use `text-embedding-3-small` (768 dimensions); LLM uses `LLM_OPENAI_MODEL` (default `gpt-4o-mini`). Optional: set `EMBED_FALLBACK_TO_LOCAL` or `LLM_FALLBACK_TO_LOCAL` to true to use Ollama when OpenAI fails.
- **Ollama-only:** Leave `OPENAI_API_KEY` unset. Install and start [Ollama](https://ollama.ai), then pull the models:
  ```bash
  ollama pull nomic-embed-text
  ollama pull llama3.1:8b
  ```
  Defaults in `.env` point to `http://localhost:11434`. If Ollama runs elsewhere, set `EMBED_BASE_URL` and `LLM_BASE_URL`.

---

## Install and run

On macOS with **Homebrew Python**, installs are often **externally managed (PEP 668)** — use the project **`venv`** below rather than `pip install` globally.

```bash
cd verbiage
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set DATABASE_URL and any overrides
uvicorn app.main:app --reload
```

If you **`git clone`** or **`mv`** the repo to a **new folder**, recreate the venv: **`rm -rf .venv`** then **`python3 -m venv .venv`** again. An old venv keeps **shebang paths** to the previous location; **`uvicorn` failing with exit 127 / “bad interpreter”** usually means `.venv` is stale — delete and recreate it in **this** checkout.

- **Dev:** `--reload` watches for code changes.
- **Server:** e.g. `uvicorn app.main:app --host 0.0.0.0 --port 8000` (or behind a reverse proxy / process manager).

Default: **http://localhost:8000**. Root serves the **built** SPA (from `static/`) after `npm run build:static` in `frontend/` (or Docker); API routes are under the same host.

### Local development: Vite + uvicorn (hot-reload SPA)

Use **two terminals** so the UI can hot-reload while the FastAPI process handles `/config`, auth, and API routes:

**Terminal A — API (repo root)**

```bash
cd verbiage
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal B — Vite**

```bash
cd verbiage/frontend
npm install   # once
npm run dev
```

Open the URL Vite prints (usually **http://127.0.0.1:5173/**). The dev server **proxies** API paths (`/config`, `/ingest`, `/ask`, `/documents`, etc.) to **http://127.0.0.1:8000** ([`frontend/vite.config.ts`](frontend/vite.config.ts)); override proxy target with **`VITE_PROXY_API`** if the API listens elsewhere.

Leave **`VITE_API_ORIGIN` unset** in dev so the SPA uses relative URLs behind the proxy. For a hosted UI pointing at a **separate API origin**, set **`VITE_API_ORIGIN`** to that base URL (and configure **`CORS_ORIGINS`** on the server).

See **[`frontend/.env.example`](frontend/.env.example)** for optional frontend env vars (`build:static`, `VITE_FEATURE_VISION`, etc.).

---

## Verify

1. **Health:** `curl -s http://localhost:8000/health` → `{"healthy": true}` (**no auth**).
2. **`/config`:** `curl -s http://localhost:8000/config` → public Supabase anon fields for the SPA (**no auth**).
3. **Protected API** (**`/ingest`**, **`/documents`**, **`/ask`**): require **`Authorization: Bearer <Supabase JWT>`** once auth is configured. Use the SPA, or acquire a token and pass the header — see **`setup_and_testing.md`** curl examples (**adjust for auth**).

You can also upload a PDF via the SPA (**Documents** tab) or **POST /ingest/file** (multipart: `file`, optional `doc_id`, `title`, `source`, `chunk_size`, `chunk_overlap`).

Further curl examples (**may need Bearer**): [setup_and_testing.md](setup_and_testing.md).

---

## Prometheus metrics (optional)

The app exposes [Prometheus](https://prometheus.io/) metrics via **`prometheus-client`** (see **`app/monitoring/`**).

1. **Enable:** Set **`METRICS_ENABLED=true`** in `.env` and **restart** the API so **`GET /metrics`** is registered.
2. **Scrape locally:**  
   `curl -s http://localhost:8000/metrics`  
   With auth:  
   `curl -s http://localhost:8000/metrics -H "Authorization: Bearer YOUR_METRICS_TOKEN"`
3. **What you get:** HTTP latency and status classes (`http_request_duration_seconds`, `http_requests_total`); RAG pipeline phases and retrieval similarity histograms (`rag_phase_seconds`, `rag_retrieval_*`); empty retrieval / no-context counters; stream-only retrieval failures (`rag_stream_retrieval_failed_total`); upstream timeouts and OpenAI→Ollama fallbacks (`upstream_timeouts_total`, `upstream_fallback_total`). Metric names and behavior are documented in comments in **`app/monitoring/metrics.py`**.
4. **Tests:** From the repo root with the venv active, run **`PYTHONPATH=. pytest tests/test_metrics.py -q`** (see [setup_and_testing.md](setup_and_testing.md#unit-tests-pytest)).

---

## Google Drive ingest (optional)

To ingest Google Docs from Drive:

1. Create OAuth credentials in Google Cloud Console (Web application, redirect URI `http://localhost:8000/auth/google/callback`).
2. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.
3. Open `http://localhost:8000/auth/google` in a browser, complete OAuth, and add the shown `GOOGLE_REFRESH_TOKEN` to `.env`.
4. Call `POST /ingest/google-drive` with optional `folder_id` or `file_ids`.

Full steps: [setup_and_testing.md](setup_and_testing.md#google-drive-ingest-read-only).

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| **`uvicorn: bad interpreter` / exit code 127** | Recreate **`rm -rf .venv && python3 -m venv .venv`** in this checkout; old venv points at wrong `python`. |
| `DATABASE_URL must be set` | Set `DATABASE_URL` in `.env` to your Postgres URI. |
| pgvector / `vector` type errors | Ensure the `vector` extension is enabled and schema (tables + HNSW index) is applied. |
| Ollama connection refused | Start Ollama; confirm `EMBED_BASE_URL` and `LLM_BASE_URL` match (e.g. `http://localhost:11434`). |
| 503 on ingest or ask | Check embedding/LLM URLs and that models are pulled (`ollama list`). |
| Supabase: "server closed the connection unexpectedly" on port 5432 | (1) Use **port 6543** (transaction mode) in `DATABASE_URL`; the app supports it. (2) **Unpause** the project in Supabase dashboard (free tier pauses when idle). (3) Or use the **Direct** connection URI from Project Settings → Database (host `db.PROJECT_REF.supabase.co`, user `postgres`) instead of the pooler. |

### Connecting with psql (Supabase)

- **Wrong:** `psql DATABASE_URL=postgresql://...` — this only sets the env var; psql still connects to the default (local) database.
- **Right:** Pass the URI to psql and require SSL:
  ```bash
  psql "postgresql://postgres.PROJECT_REF:YOUR_PASSWORD@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
  ```
  Or set the variable and use it (SSL required for Supabase):
  ```bash
  export DATABASE_URL="postgresql://postgres.PROJECT_REF:PASSWORD@HOST:5432/postgres?sslmode=require"
  psql "$DATABASE_URL"
  ```
- **Test from the app:** From project root, `python scripts/test_db_connection.py` — uses `.env` and prints the real connection error if it fails.
