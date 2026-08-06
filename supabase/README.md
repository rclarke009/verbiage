# Verbiage — Supabase schema

Database schema on Supabase: pgvector + `documents`, `chunks`, `embeddings`.

## Setup

1. **Create a Supabase project** at [supabase.com](https://supabase.com) → New project.  
   Save: **Project URL**, **Database password**, and **anon** / **service_role** keys from Project Settings → API.

2. **Apply the schema** in the Supabase **SQL Editor**:
   - Open your project → **SQL Editor** → New query.
   - Paste the contents of `migrations/20250302000000_phase1_schema.sql`.
   - Run it.

   Or with the [Supabase CLI](https://supabase.com/docs/guides/cli) after `supabase link`:

   ```bash
   supabase db push
   ```

3. **Postgres connection string** for the FastAPI app:  
   Project Settings → **Database** → Connection string (URI). Prefer the **pooler** URI (port 6543) for short-lived connections. Set `DATABASE_URL` in `.env` (see root [README.md](../README.md) and [setup.md](../setup.md)).

That enables pgvector plus tables and indexes (including HNSW for vector search).
