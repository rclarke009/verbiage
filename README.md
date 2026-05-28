# TrueAI — RAG report library

FastAPI + React app for ingesting storm-damage (and similar) reports, embedding them in **Postgres with pgvector**, and answering questions with retrieved context and an LLM.

Originally built to generate suggested verbiage from prior case documentation. **Production:** [Render dashboard](https://dashboard.render.com/web/srv-d6m79eftskes73dnndb0) · live app linked from [overview.md](overview.md).

---

## What it does

- **Ingest** — PDF upload, pasted text, or Google Docs (read-only Drive export)
- **Index** — Paragraph-first chunking; canonical `full_text` stored for reindex without re-upload
- **Ask** — Semantic retrieval + LLM answers with cited sources and report links
- **Manage** — Shared document library (all signed-in users); list, filter, delete
- **Drive workflow** — Team inbox via **`GOOGLE_DRIVE_DEFAULT_FOLDER_ID`**; list folder with **Indexed / Not indexed / Stale** status; paste another folder URL to override

Embeddings and LLM: **OpenAI** when `OPENAI_API_KEY` is set, otherwise **Ollama**. Auth: **Supabase JWT** on protected routes.

---

## Quick start

**Detailed setup:** [setup.md](setup.md) · **Testing & curl:** [setup_and_testing.md](setup_and_testing.md)

### Docker

```bash
cd verbiage
cp .env.example .env
# Set OPENAI_API_KEY and/or configure Ollama; DATABASE_URL is set by Compose
docker-compose up --build
```

Open **http://localhost:8000/** for the built SPA. Stop with `docker-compose down`.

### Local dev (API + Vite hot reload)

Two terminals — API on `:8000`, Vite on `:5173` (proxies API). See [setup.md](setup.md#local-development-vite--uvicorn-hot-reload-spa).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DATABASE_URL required
uvicorn app.main:app --reload
```

---

## Web UI (SPA)

After sign-in:

| Tab | Purpose |
|-----|---------|
| **Ask** | Chat over the shared library with source citations |
| **Documents** | Index table, PDF upload, search, delete |
| **Google Drive** | Team inbox (env default); status badges; paste another folder to override; ingest selected docs |

---

## API highlights

Interactive docs: **http://localhost:8000/docs** when the server is running.

| Route | Notes |
|-------|--------|
| `GET /health` | Liveness (process up) |
| `GET /health/ready` | Readiness (Postgres) — use for Render/LB health checks |
| `GET /documents` | Shared library listing |
| `POST /documents/{doc_id}/reindex` | Re-chunk/re-embed from stored `full_text` |
| `GET /drive/files` | Drive folder list + `index_status` / `summary` |
| `POST /ingest/google-drive` | Export and ingest Google Docs |
| `POST /ask`, `POST /ask/stream` | RAG Q&A |

Most routes require `Authorization: Bearer <Supabase access token>`.

---

## Architecture

1. Document uploaded, pasted, or exported from Drive  
2. Text extracted → `full_text` saved → chunked (paragraph-first default) → embedded  
3. Vectors stored in pgvector; retrieval filtered by active embedding model  
4. User question → top-k chunks → LLM response with citations  

Implementation notes (chunking, reindex, data sources): [code-notes.md](code-notes.md).

---

## Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Python |
| UI | React, Vite, TanStack Query |
| Database | PostgreSQL + pgvector (Supabase in production) |
| Auth | Supabase JWT |
| Embeddings / LLM | OpenAI or Ollama |
| Drive | Google Drive API (read-only OAuth) |

---

## Health & ops

- Set load-balancer health check to **`/health/ready`**, not `/health`.
- Optional **`GET /health/deep`** probes DB + embed (avoid high-frequency polling — may call OpenAI).
- Optional Prometheus **`GET /metrics`** — see [setup.md](setup.md#prometheus-metrics-optional).
