# Verbiage: SQLite → Supabase (Postgres + pgvector)

Historical notes from migrating Verbiage to Supabase Postgres + pgvector. **This migration is complete** — production uses `DATABASE_URL` against Supabase; vector search runs in-database via pgvector. Use this file as background, not a to-do list.

## Outcome

- **Schema:** `documents`, `chunks`, `embeddings` with `embedding vector(...)` (not JSON), HNSW for cosine distance.
- **App:** FastAPI connects with `DATABASE_URL` (psycopg2 pool). Ingest, list, ask, and delete go through the Postgres DB layer; retrieval uses in-DB similarity (`<=>`), not a Python 5k-cap loop.
- **Config:** `DATABASE_URL` in `.env` / `app/config.py`. See [supabase/README.md](supabase/README.md) for schema apply steps and [setup.md](setup.md) for local/prod env.

## Connection string

The URI is **not** the project URL (`https://xxxx.supabase.co`). Use **Project Settings → Database → Connection string (URI)** (`postgresql://…`). Prefer the pooler for short-lived app connections.

For server-side RAG, a direct Postgres connection matches the existing `conn`-per-request style. The JS Supabase client is optional (REST/Realtime), not required for the Python API path.

## What changed vs the old SQLite path

| Before (SQLite) | After (Supabase) |
| --- | --- |
| `vector_json` TEXT + in-Python scoring | `embedding vector(N)` + `ORDER BY embedding <=> query` |
| File path / `sqlite3.connect` | `DATABASE_URL` + connection pool |
| Soft 5k embedding load cap | DB returns top-k only |

Auth, Drive ingest, hybrid retrieval, and Report Writer were built on top of this Postgres foundation after the migration.

## Related

- Schema: [supabase/migrations/](supabase/migrations/) and [supabase/README.md](supabase/README.md)
- Auth setup: [SUPABASE_AUTH_STEPS.md](SUPABASE_AUTH_STEPS.md)
- Ops: [setup.md](setup.md), [setup_and_testing.md](setup_and_testing.md)
