# Demo deployment operator runbook

Public Ask-only demo on a **second Render web service** with a **separate Supabase project** and the synthetic eval corpus (`tests/eval/corpus/`). Production is unchanged when prod env vars stay as they are today.

## Render terminology

This is **not** a second Render account. It is a **second web service** in the same workspace:

```text
Your Render workspace (same billing account)
├── rag-document-analysis-backend   ← prod (Standard, existing URL)
└── verbiage-demo                     ← demo (Starter, new URL)
```

| Piece | Prod | Demo |
|-------|------|------|
| Render web service | `rag-document-analysis-backend` | `verbiage-demo` |
| Instance | Standard (2 GB) | Starter (~512 MB) |
| Supabase project | Existing | **New** project |
| Database | Real reports | Synthetic eval corpus only |
| Env | Full prod config | `DEMO_MODE=1`, no `GOOGLE_*` |

**Shared:** GitHub repo, Docker image (both redeploy on push).

**Not shared:** Database, auth users, secrets, URL.

## Production impact

No intentional prod change when `DEMO_MODE` is **unset** on `rag-document-analysis-backend`. Pushing this code redeploys prod as usual; demo behavior is env-gated.

**Blueprint sync caution:** approve the new `verbiage-demo` service only; do **not** add demo env vars to prod.

---

## Step A — Create demo Supabase project

1. [Supabase Dashboard](https://supabase.com/dashboard) → **New project** (e.g. `verbiage-demo`).
2. **Project Settings → API**: copy `SUPABASE_URL`, anon key, JWT secret, service role key.
3. **Authentication → Providers**: Email enabled; **disable** “Allow new users to sign up” (signup goes through the app backend).
4. **Authentication → URL Configuration** (after you know the Render URL):
   - Site URL: `https://verbiage-demo.onrender.com` (or your custom domain)
   - Redirect URLs: `https://verbiage-demo.onrender.com/**`

---

## Step B — Add demo web service on Render

**Option 1 — Blueprint sync (recommended after merge):**

1. Dashboard → **Blueprints** → sync blueprint.
2. Approve new service **`verbiage-demo`**.
3. Confirm instance type **Starter** (~$7/mo, always-on).

**Option 2 — Manual:**

1. **New +** → **Web Service** → same repo, branch, Dockerfile as prod.
2. Name: `verbiage-demo`
3. Health check: `/health/ready`
4. Instance: **Starter**

---

## Step C — Demo environment variables

Render → **verbiage-demo** → **Environment**:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Demo Supabase Postgres URI (Session mode, port 5432) |
| `SUPABASE_URL` | Demo project URL |
| `SUPABASE_ANON_KEY` | Demo anon key |
| `SUPABASE_JWT_SECRET` | Demo JWT secret |
| `SUPABASE_SERVICE_ROLE_KEY` | Demo service role |
| `OPENAI_API_KEY` | Your key (set billing alerts in OpenAI) |
| `PUBLIC_APP_URL` | `https://<demo-host>.onrender.com` |

Non-secret defaults (from [`render.yaml`](../render.yaml) or set manually):

- `DEMO_MODE=1`
- `DEMO_ANONYMOUS=1` (skip sign-in; Search uses IP-based rate limits)
- `DEMO_OPEN_SIGNUP=0` (optional; only if you want account signup instead)
- `DEMO_ASK_LIMIT=10`
- `DEMO_ASK_WINDOW_SECONDS=3600`
- `DEMO_SIGNUP_LIMIT=5`
- `RERANK_ENABLED=0`
- `INGEST_WORKER_ENABLED=0`
- `LLM_TOKEN_LIMIT=5`

**Do not set on demo:** `GOOGLE_*`, `SIGNUP_INVITE_CODE`.

---

## Step D — Seed synthetic corpus (once)

From your laptop with demo `DATABASE_URL`:

```bash
cd verbiage
python scripts/seed_demo_db.py
```

Or from Render **Shell** on `verbiage-demo` after first deploy.

Seeds 7 fictional reports from `tests/eval/corpus/` — no real client data.

---

## Step E — Verify

1. Open demo URL → Search tab loads immediately (no sign-in when `DEMO_ANONYMOUS=1`).
2. **Search**: ask *“What roof damage was found at 1060 Alton Road in Port Charlotte?”* → grounded answer + citations.
3. **Report Writer** / **Documents** / **Drive** → upsell message, no API data.
4. Ask 11 times within an hour → rate-limit message on the 11th.
5. Confirm prod URL still works (no `DEMO_MODE` on prod service).

---

## Demo behavior summary

| Feature | Demo |
|---------|------|
| Sign in | Skipped when `DEMO_ANONYMOUS=1` |
| Search (`/ask`) | 10 requests per visitor IP per hour |
| Other tabs | Visible; show “available in full version” gate |
| Backend | 403 on ingest, documents, drive, report-writer |
| Data | Synthetic eval corpus only |

---

## Cost estimate

| Item | Monthly |
|------|---------|
| Demo Starter | ~$7 |
| Demo Supabase | Free tier (may pause when idle — open dashboard before demos) |
| OpenAI on demo | Cents (capped per user) |

Prod Standard (~$25) is unchanged.
