# Verbiage — Setup and Testing

## Prerequisites: OpenAI or Ollama

When **OPENAI_API_KEY** is set in `.env`, the app uses **OpenAI** for embeddings (`text-embedding-3-small`, 768 dim) and for the LLM (e.g. `gpt-4o-mini`). Optional: set `EMBED_FALLBACK_TO_LOCAL` or `LLM_FALLBACK_TO_LOCAL` to true to use Ollama when OpenAI fails.

When **OPENAI_API_KEY** is not set, the app uses **Ollama** only. Default config expects:

- **LLM:** `llama3.1:8b` at `http://localhost:11434`
- **Embeddings:** `nomic-embed-text` at the same base URL

### Start Ollama and pull models (Ollama-only or fallback)

```bash
# Start the Ollama server (if not already running as a service)
ollama serve
```

In another terminal, pull the models so the API can load them when using Ollama:

```bash
# LLM used by POST /ask when using Ollama (see app/config.py: LLM_MODEL)
ollama pull llama3.1:8b

# Embedding model used for ingest and ask when using Ollama (EMBED_MODEL)
ollama pull nomic-embed-text
```

Optional: run the LLM interactively (also pulls if needed):

```bash
ollama run llama3.1:8b
```

---

## App setup

Use a **`venv`** in the repo (required on PEP 668 “externally managed” Python installs; see **`setup.md`** troubleshooting if `pip install` is blocked globally).

```bash
cd verbiage
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`. **Required:** set `DATABASE_URL` to your Postgres connection URI (e.g. from Supabase: Project Settings → Database → Connection string; see `supabase_migration.md`). The app will not start without it. For OpenAI: set `OPENAI_API_KEY`. For Ollama-only: leave the key unset and set `LLM_BASE_URL` / `EMBED_BASE_URL` if not using defaults.

Start the API:

```bash
uvicorn app.main:app --reload
```

Default: `http://localhost:8000`. The same server can serve the **built** SPA at the root (from `static/`). For **local UI development with hot reload**, prefer **Vite + uvicorn** — see **[setup.md](setup.md)** (*Local development: Vite + uvicorn (hot-reload SPA)*; two terminals, then open the port Vite prints, usually **5173**).

---

## Automated checks on commit / push (git hooks)

Repo-tracked hooks in **`.githooks/`** run the test gates for you so a broken commit can't slip through. **Enable them once per clone** — this writes to *this* repo's `.git/config` only, and is **not** committed, so every fresh clone (or new machine) needs it again:

```bash
git config core.hooksPath .githooks
```

Confirm it took:

```bash
git config core.hooksPath   # should print: .githooks
```

What runs:

- **`pre-commit`** (on `git commit`) — backend `pytest -q`, plus frontend `npm run lint` + `npm run typecheck` + `npm test` (Vitest) **only when the commit touches `frontend/`**.
- **`pre-push`** (on `git push`) — `make eval` (the fast faithfulness gate). If Docker isn't running it **skips** rather than blocking the push; set `VERBIAGE_REQUIRE_EVAL=1` to make a missing Docker **fail** the push instead.

Bypass either for a single command with `--no-verify` (`git commit --no-verify`, `git push --no-verify`).

**Undo / revert to your global (or default) hooks:**

```bash
git config --unset core.hooksPath
```

> Setting `core.hooksPath` for this repo overrides any global hooks path you have configured, for this repo only — other repos keep using your global hooks.

---

## Unit tests (pytest)

After **`pip install -r requirements.txt`** inside the project **`venv`**, run tests from the **repository root** with **`PYTHONPATH=.`** so the **`app`** package resolves:

```bash
cd verbiage
source .venv/bin/activate   # Windows: .venv\Scripts\activate
PYTHONPATH=. pytest tests/ -q
```

- **`tests/test_metrics.py`** — Prometheus middleware and RAG metric helpers (no database).
- **`tests/test_drive_index_status.py`** — Drive folder `index_status` computation (indexed / stale / not_indexed).
- **`tests/test_retrieval.py`** — RRF fusion, `auto` routing, and the cosine relevance gate (monkeypatched, no DB).
- **`tests/test_reranker.py`** — cross-encoder reranking: the `Reranker` (lazy load stubbed, no model download), the `_rerank_chunks` adapter, and `_retrieve_for_ask` pool-widening + the gate-runs-before-rerank invariant.
- **`tests/test_llm_client.py`** — LLM temperature plumbing: the configured `LLM_TEMPERATURE` default and explicit overrides reach the OpenAI/Ollama request payload (HTTP mocked).
- **`tests/test_ask_stream.py`** — SSE wire contract for **`POST /ask/stream`**: a prepare/retrieval failure emits an `event: error` frame (`retrieval_failed`), and the no-context path emits a token refusal + empty `sources` frame without calling the LLM. These are the exact frames the SPA's `useReportSearch` hook parses. `TestClient` is used without a context manager so the app lifespan (and its real DB) never starts; `with_db_conn_retry` is patched, so no database is required.
- Other **`tests/*.py`** — lightweight unit tests (no full API startup unless noted).
- **`tests/eval/`** — faithfulness eval suite; excluded from `pytest tests/` unless `VERBIAGE_EVAL=1` is set. See **Faithfulness eval (opt-in)** below.

Operational scraping and env vars for **`/metrics`** are described in **[setup.md](setup.md)** (*Prometheus metrics (optional)*).

---

## Frontend tests (Vitest)

The SPA has a [Vitest](https://vitest.dev/) suite that runs in **jsdom** (no browser, no backend, no network). Install deps once (`npm install` inside `frontend/`), then from the **`frontend/`** directory:

```bash
cd frontend
npm test          # run once (CI-style; what `vitest run` does)
npm run test:watch # re-run on change while developing
```

- **`src/hooks/useReportSearch.test.ts`** — the `/ask/stream` SSE client. `fetch` is mocked to return a `ReadableStream`, so the tests assert the hook's stream parsing and error handling directly:
  - tokens and `sources` frames accumulate into the result (happy path);
  - an **`event: error`** frame (e.g. `retrieval_failed`) surfaces a readable message instead of being silently dropped;
  - a non-OK response with an empty body and empty `statusText` (as over HTTP/2) renders `Error: HTTP 502`, not a bare `Error:`;
  - an event whose type and data arrive in separate network reads still parses (the `currentEvent`-across-chunks case).

These pair with the backend **`tests/test_ask_stream.py`** above so both sides of the SSE contract are pinned: if the backend renames an event or the frontend stops handling one, a test fails instead of the UI silently showing a blank error.

The build typechecks exclude test files (`tsconfig.app.json`), so `npm run build` is unaffected.

---

## Faithfulness eval (opt-in)

A regression harness that checks, after every retrieval/prompt tweak, whether **every claim in an answer is supported by the context that was actually retrieved**. It runs the real pipeline (`auto` routing → RRF → grounded prompt → LLM) against a frozen corpus seeded into a throwaway pgvector container, then judges each answer's claims. The whole suite is opt-in via `VERBIAGE_EVAL=1`, so a normal `pytest tests/` run stays fast and offline.

### Prerequisites

- **Docker** running (the eval DB comes up on host port **5433** via `docker-compose.eval.yml`; make sure nothing else uses 5433).
- An **LLM + embedding backend** — same options as above: set `OPENAI_API_KEY` in `.env` (uses `text-embedding-3-small` + `gpt-4o-mini`), or run **Ollama** with `nomic-embed-text` and `llama3.1:8b` pulled.
- Deps installed (`pip install -r requirements.txt`). The fast judge downloads `cross-encoder/nli-deberta-v3-base` (~400 MB) from Hugging Face on the **first** run, so that run needs network even on the Ollama path.

### First run (warms the embedding cache)

```bash
make eval        # fast gate: local NLI judge, intended for every tweak
```

This brings the ephemeral DB up (`--wait`), seeds `tests/eval/corpus/`, runs `pytest -m eval_fast tests/eval -s`, prints a per-question scoreboard, and tears the DB down. On the first run, `tests/eval/embeddings_cache.json` is empty, so the corpus chunks and gold questions are embedded once via the live backend and written into that file.

**Commit the warmed cache** so future runs are deterministic and offline (embedding calls disappear; only generation still hits the LLM):

```bash
git add tests/eval/embeddings_cache.json
git commit -m "Warm eval embeddings cache"
```

### Routine use

```bash
make eval            # fast NLI gate (run after every tweak)
make eval-full       # deep gate: OpenAI LLM-as-judge (needs OPENAI_API_KEY)
make eval-warm-cache # re-embed + rewrite the cache after changing corpus/chunking/model
make eval-down       # manually stop + remove the eval DB (data is ephemeral; nothing is lost)
```

Each `make eval*` target tears the DB down automatically when it finishes (even on failure). `eval-up` is also self-healing: it runs `down -v --remove-orphans` before starting, so a leftover container from an interrupted previous run is cleared automatically. Use `make eval-down` only if you brought the DB up manually or cancelled a run mid-flight (Ctrl-C before teardown).

Gold questions (including deliberately **unanswerable** ones that must trigger a refusal) live in `tests/eval/gold_questions.yaml`. The bar lives in `tests/eval/test_faithfulness.py`: `FAST_MIN_FAITHFULNESS` and the `NliJudge` threshold — loosen these if sentence-level NLI proves too strict on legitimately-grounded paraphrase.

### Notes / gotchas

- Caching removes the **embedding** network dependency only; **generation calls the LLM every run** (that's what's being tested), so a backend must always be reachable.
- `make eval` manages its own env (`VERBIAGE_EVAL=1`, `EVAL_DATABASE_URL`), so no `PYTHONPATH=.` prefix is needed unlike the unit tests above.
- Port 5433 busy → `up --wait` hangs; free it or change the host port in `docker-compose.eval.yml`.
- A failure tagged as a retriever miss (missing `must_mention` terms) points at retrieval, not generation — see the assertion messages in `tests/eval/test_faithfulness.py`.
- **Container name conflict** (`the container name "/verbiage_eval_db" is already in use`): a previous run was cancelled before teardown and left the container running. `eval-up` now self-heals on the next `make eval`, but if a stale container predates that change (so `make eval-down` only removes the network), force-remove it directly:

```bash
docker rm -f verbiage_eval_db   # ephemeral DB; safe to remove
make eval                       # then re-run
```

---

## Web UI

You can open the UI in two ways:

1. **Production-style / Docker:** **`http://localhost:8000/`** — loads the SPA built into `static/`.
2. **Development:** Vite (**`npm run dev`** in `frontend/`) with API on **`:8000`** — proxies API routes; detailed steps in **`setup.md`** (§ *Local development: Vite + uvicorn*).

Protected API routes (**`/ingest`**, **`/documents`**, **`/ask`**, **`/drive/*`**, …) expect **`Authorization: Bearer <Supabase access token>`**. The SPA signs in via Supabase; curl snippets below omit that header unless noted — pass a token after sign-in, or use public routes (**`/health`**, **`/health/ready`**, **`/config`**). For production load balancers (e.g. Render), set the health check path to **`/health/ready`** (Postgres `SELECT 1`), not **`/health`** (process liveness only).

**Shared library:** All signed-in users see and search the same ingested document corpus (list, ask, ingest, delete). Auth gates access; there is no per-user document partition.

### Tabs (React SPA — TrueAI)

Sign in, then use the header tabs:

- **Ask** — Chat-style Q&A over the shared library. Answers include cited source chunks with links to the original report when `source_url` is known (e.g. Google Docs).
- **Documents** — Full index of ingested reports: title, source, chunk count, embedding model, link to original, filter search, PDF upload dropzone, and delete. Calls **`GET /documents`**.
- **Google Drive** — List ingestable files in a folder (Google Docs, PDF, Word `.docx`; optional folder ID), see **index status** per file (Indexed / Not indexed / Stale), auto-select files that need ingest, then run **Ingest**. Max **50 MB** per file download. Uses **`GET /drive/files`** and **`POST /ingest/google-drive`**.

Optional **Photo analysis (preview)** tab appears when **`VITE_FEATURE_VISION=true`** in the frontend env.

### Quick test flow

1. Open the app (production **`http://localhost:8000/`** or dev **`http://127.0.0.1:5173/`** with Vite — see [setup.md](setup.md)).
2. Sign in with Supabase.
3. **Documents** — upload a PDF or note an existing row in the table.
4. **Ask** — ask a question related to that content; expand source citations.
5. **Google Drive** (if OAuth is configured) — paste a folder ID, **List files**, confirm status badges, **Ingest** selected rows, re-list to refresh counts.

---

## curl commands

Base URL assumed: `http://localhost:8000`. Use `-s` for quieter output.

### Health check

```bash
curl -s "http://localhost:8000/health"
curl -s "http://localhost:8000/health/ready"
# Optional deep probe (DB + embed; may call OpenAI if OPENAI_API_KEY is set):
# curl -s "http://localhost:8000/health/deep"
```

### List documents (GET)

Returns all documents in the shared library. Each item includes at least: `doc_id`, `title`, `source`, `created_at`, `num_chunks`, optional `snippet` (first chunk preview), plus `source_url`, `source_filename`, `source_modified_at`, `embedding_model`, and `chunking_config` when stored.

```bash
curl -s "http://localhost:8000/documents"
```

### Reindex document (POST)

Re-chunk and re-embed from stored **`full_text`** without re-uploading the PDF or re-exporting Drive. Optional JSON body overrides **`chunking_options`** (strategy, chunk_size, chunk_overlap).

```bash
curl -s -X POST "http://localhost:8000/documents/runbook-1/reindex" \
  -H "Content-Type: application/json" \
  -d '{"chunking_options": {"strategy": "paragraph", "chunk_size": 1200, "chunk_overlap": 150}}'
```

Empty body uses default chunking. Returns the same shape as ingest (`doc_id`, `num_chunks`, `embedding_model`, …). Fails with **404** if the doc is missing or **400** if `full_text` was never stored (re-ingest from source instead).

### Ingest (POST)

Requires a JSON body with at least `text`. Optional: `doc_id`, `title`, `source`, `chunking_options`.

```bash
curl -s -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{"text": "Your document content here. Latency alerts trigger when response time exceeds 500ms for 3 consecutive checks.", "title": "Runbook", "doc_id": "runbook-1"}'
```

Minimal (server generates `doc_id`):

```bash
curl -s -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{"text": "Short document to ingest."}'
```

### Ingest PDF (POST /ingest/file)

Accepts multipart form data: required `file` (PDF), optional `doc_id`, `title`, `source`, `chunk_size`, `chunk_overlap`. Text is extracted from the PDF, then chunked and embedded like **POST /ingest**.

```bash
curl -s -X POST "http://localhost:8000/ingest/file" \
  -F "file=@/path/to/report.pdf" \
  -F "title=Report 2024" \
  -F "source=uploaded_pdf"
```

### Ask (POST)

Requires a JSON body with `question`. Optional: `top_k`, `doc_id`, `use_rag`.

After ingesting the test playbook (e.g. content from `payload.json` with `doc_id` `edge-rel-playbook-v1`), these questions verify RAG:

```bash
# Answerable from the playbook: Preflight Validator checks are listed in section 4
curl -s -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the Preflight Validator check?"}'
```

```bash
# Answerable from the playbook: latency alert condition is stated in section 7
curl -s -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What conditions trigger a latency alert?"}'
```

With options (e.g. restrict to one document):

```bash
curl -s -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the Preflight Validator check?", "top_k": 5, "doc_id": "edge-rel-playbook-v1"}'
```

**Note:** `GET /ask?question=...` is not supported; the endpoint expects **POST** with a JSON body.

---

## Google Drive ingest (read-only)

You can ingest **Google Docs, PDFs, and Word (.docx)** from Drive by authorizing once with OAuth, then calling **POST /ingest/google-drive**. The app only requests read-only access (`drive.readonly`). Each file download is capped at **50 MB**. Image-only PDFs fail extraction (same as PDF upload).

### 1. Google Cloud project and OAuth client

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or pick an existing one) and enable **Google Drive API** (APIs & Services → Library → search “Google Drive API” → Enable).
3. Create OAuth credentials: **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
4. If prompted, configure the **OAuth consent screen** (e.g. External, add your email as test user).
5. For **Application type** choose **Web application**.
6. Under **Authorized redirect URIs** add:  
   `http://localhost:8000/auth/google/callback`  
   (or the same URL with your host/port if you run the app elsewhere).
7. Copy the **Client ID** and **Client secret**.

### 2. Set env and run one-time OAuth

In your `.env` (or environment), set:

```bash
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
```

Optional: if the app is not on port 8000, set the callback URL to match what you registered:

```bash
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

Start the app (`uvicorn app.main:app --reload`), then in a browser open:

**http://localhost:8000/auth/google**

Sign in with the Google account that has access to the Drive files you want to ingest. After you approve, you are redirected to a page that shows a line like:

```bash
GOOGLE_REFRESH_TOKEN="1//0abc..."
```

Add that line to your `.env` (or set the env variable), then restart the app.

### Team ingest inbox (recommended)

Set the shared **ready-for-TrueAI** folder so operators are not copying folder ids every time:

```bash
# Folder id or full URL — also set on Render in production
GOOGLE_DRIVE_DEFAULT_FOLDER_ID=1HUgl4ryKyijBOP4_nJkJCCT3mvLdKPih
# Optional: human-readable path shown in the Drive tab for the team inbox
GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL=Shared drives / Team / Ready for AI Ingest
```

- **`GET /config`** returns `google_drive_default_folder_id` (parsed id) and `google_drive_default_folder_label` for the SPA.
- **`GET /drive/folder`** resolves the active folder path (env label for default inbox; Drive API breadcrumb for overrides).
- **`GET /drive/files`** and **`POST /ingest/google-drive`** use this folder when `folder_id` is omitted (unless `file_ids` is set).
- The **Google Drive** tab pre-fills the inbox, shows the active folder path, **auto-lists** on open, accepts a pasted folder URL to override, and offers **Reset to team inbox**.

**Folder access:** The Google account that completed **`/auth/google`** (stored in `GOOGLE_REFRESH_TOKEN`) must be able to open the inbox folder. If a manager owns the folder, they must **share** it with that account (Viewer is enough for read-only ingest).

To find a folder id: open the folder in [Google Drive](https://drive.google.com) and copy the URL — the id is the segment after `/folders/`.

### 3. List Drive folder with index status

**GET /drive/files** lists ingestable file metadata (Google Docs, PDF, DOCX; no download). Query params (optional):

- **`folder_id`** — only files in this Drive folder.
- **`file_ids`** — comma-separated file IDs (if set, `folder_id` is ignored).

Each file includes **`index_status`**: `not_indexed`, `indexed`, or `stale`. **Stale** means the doc is in the index but Drive **`modifiedTime`** is newer than **`source_modified_at`** from the last ingest (content may have changed). The response also includes **`summary`** counts (`total`, `indexed`, `not_indexed`, `stale`) and **`num_chunks`** when the file is indexed or stale.

The **Google Drive** tab in the SPA uses this endpoint: status badges, summary banner, auto-select of **not indexed** and **stale** rows, and re-list after ingest.

```bash
curl -s "http://localhost:8000/drive/files?folder_id=YOUR_DRIVE_FOLDER_ID"
```

Example response shape (abbreviated):

```json
{
  "files": [
    {
      "id": "abc123",
      "name": "Roof Report 2024",
      "mimeType": "application/vnd.google-apps.document",
      "modifiedTime": "2024-06-01T12:00:00.000Z",
      "index_status": "indexed",
      "num_chunks": 42
    }
  ],
  "summary": { "total": 1, "indexed": 1, "not_indexed": 0, "stale": 0 }
}
```

**Note:** Ingesting a **stale** doc still hits duplicate detection today (same Drive file id → skipped). Re-sync from Drive after content changes is a planned follow-up; use **reindex** when only chunking/embedding strategy changes, not when Drive text changed.

### 4. Ingest from Drive

**POST /ingest/google-drive** enqueues background jobs to fetch and ingest ingestable Drive files (chunk + embed + store). Request body (all optional):

- **folder_id** — only list files in this Drive folder.
- **file_ids** — only these file IDs. If set, `folder_id` is ignored.

If both are omitted, the app uses **`GOOGLE_DRIVE_DEFAULT_FOLDER_ID`** when set, otherwise lists from the root of the authenticated user’s Drive.

Example (ingest all ingestable files in a folder):

```bash
curl -s -X POST "http://localhost:8000/ingest/google-drive" \
  -H "Content-Type: application/json" \
  -d '{"folder_id": "YOUR_DRIVE_FOLDER_ID"}'
```

Example (ingest specific Docs by ID):

```bash
curl -s -X POST "http://localhost:8000/ingest/google-drive" \
  -H "Content-Type: application/json" \
  -d '{"file_ids": ["id1", "id2"]}'
```

Response shape: `{"ingested": N, "skipped": M, "errors": [...], "doc_ids": [...]}`. Duplicate `doc_id` (same file already ingested) is counted as skipped; other failures are listed in `errors`.

---

## Google Drive troubleshooting (server refresh token)

The app uses **one** Google account for Drive: credentials live on the server (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`). The signed-in Supabase user does **not** supply their own Google token.

1. **Redirect URI must match exactly**  
   In Google Cloud Console → APIs & Services → Credentials → your OAuth client → **Authorized redirect URIs**, the URI must match where the app runs, including scheme, host, port, and path. Examples:
   - Local: `http://localhost:8000/auth/google/callback`
   - Production: `https://your-domain.com/auth/google/callback`  
   If you deploy to a new host, add that callback URL, redeploy, then run **`GET /auth/google`** again on that host to mint a new refresh token (or use the same client with the new URI added).

2. **`GOOGLE_REDIRECT_URI` env**  
   If the app is not on the default port or path, set `GOOGLE_REDIRECT_URI` to the same value you registered in Google Cloud. It must match the redirect URI used during the OAuth step.

3. **Drive API and consent screen**  
   Enable **Google Drive API** for the project. On the OAuth consent screen, add test users if the app is in testing mode.

4. **After pasting `GOOGLE_REFRESH_TOKEN`**  
   Restart the API process so it picks up the new env var. On **Render** (or similar), set `GOOGLE_REFRESH_TOKEN` (and client id/secret) in the service **Environment** tab and trigger a redeploy if needed.

5. **`GET /drive/test` (with a valid Supabase session)**  
   Returns `{ "ok": true }` if the refresh token works. If it fails, read the JSON `detail` string (often “credentials not configured”, invalid_grant, or revoked token).

6. **New refresh token**  
   If the token was revoked or the OAuth client changed, visit **`/auth/google`** again while logged into the correct Google account and replace `GOOGLE_REFRESH_TOKEN` in env.

---

## Similar titles (advisory duplicate check)

**`GET /documents/similar-titles?proposed=<name>&limit=5&min_ratio=0.82`** (requires `Authorization: Bearer <Supabase access token>`) returns existing documents whose titles are fuzzily similar to `proposed`. The web UI uses this before ingesting queued PDFs or selected Drive files so you can skip near-duplicates.


### Async Google Drive ingest

`POST /ingest/google-drive` returns **202 Accepted** with `{ "batch_id", "total", "job_ids" }` and enqueues one background job per ingestable file. Poll progress:

```bash
curl -s "$API/ingest/batches/<batch_id>" -H "Authorization: Bearer $TOKEN"
```

Batch `status` is `pending` → `running` → `completed` (or `failed` if every job failed). Counters: `pending`, `running`, `succeeded`, `failed`, `skipped`. Stale Drive docs are re-indexed in the worker; up-to-date docs are skipped.

Disable the in-process worker with `INGEST_WORKER_ENABLED=0` (jobs remain queued until re-enabled).

