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

```bash
cd verbiage
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set DATABASE_URL and any overrides
uvicorn app.main:app --reload
```

- **Dev:** `--reload` watches for code changes.
- **Server:** e.g. `uvicorn app.main:app --host 0.0.0.0 --port 8000` (or behind a reverse proxy / process manager).

Default: **http://localhost:8000**. Root serves the web UI; API is under the same host.

---

## Verify

1. **Health:** `curl -s http://localhost:8000/health` → `{"healthy": true}`.
2. **Ingest:** `curl -s -X POST http://localhost:8000/ingest -H "Content-Type: application/json" -d '{"text": "Test report content.", "title": "Test"}'`. You can also upload a PDF via the web UI (Ingest tab) or **POST /ingest/file** (multipart: `file`, optional `doc_id`, `title`, `source`, `chunk_size`, `chunk_overlap`).
3. **List:** `curl -s http://localhost:8000/documents` → list including the new doc.
4. **Ask:** `curl -s -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Summarize the test report."}'`.

More examples: [setup_and_testing.md](setup_and_testing.md).

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
