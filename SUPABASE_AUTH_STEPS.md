# Supabase Auth: Steps to Secure Verbiage

After applying the code changes, follow these steps in the **Supabase Dashboard** so the app can authenticate users and scope documents per user.

---

## 1. Get your project credentials

1. Open [Supabase Dashboard](https://supabase.com/dashboard) and select your project (or create one).
2. Go to **Project Settings** (gear icon) → **API**.
3. Copy and note:
   - **Project URL** (e.g. `https://xxxx.supabase.co`) → use as `SUPABASE_URL`.
   - **anon public** key (under "Project API keys") → use as `SUPABASE_ANON_KEY`.
   - **JWT Secret** (under "JWT Settings") → use as `SUPABASE_JWT_SECRET`.  
     **Important:** The JWT Secret is used only on the server to verify tokens; never expose it in the frontend.

---

## 2. Set environment variables

In your app’s `.env` (or wherever you configure the Verbiage backend), set:

```env
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-from-dashboard
```

Restart the Verbiage server after changing these.

---

## 3. (Optional) Add `user_id` column if you manage schema in Supabase

If you created the `documents` table via Supabase (e.g. from an earlier migration) and it doesn’t have `user_id` yet:

1. In the dashboard, go to **SQL Editor**.
2. Run:

```sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
```

If you only use the app’s built-in `create_db()` (e.g. on first run), it will add `user_id` automatically; this step is only for DBs you manage in Supabase.

---

## 4. Enable Email auth (or another provider)

1. In the dashboard, go to **Authentication** → **Providers**.
2. Ensure **Email** is enabled if you use email/password sign-in (default in the Verbiage UI).
3. Optionally configure **Confirm email** under **Authentication** → **Providers** → **Email** (e.g. disable for development).

---

## 5. Password reset (redirect URLs)

The Verbiage UI sends password recovery emails via Supabase (`resetPasswordForEmail` with `redirectTo` set to your app origin + `/`). Supabase only redirects to URLs you allow.

1. In the dashboard, go to **Authentication** → **URL Configuration**.
2. Set **Site URL** to the primary URL where users open the app (production: `https://rag-document-analysis-backend.onrender.com`, or `http://localhost:8000` for local dev).
3. Under **Redirect URLs**, add every origin (and wildcard if you use the dashboard’s pattern support) where users might land after clicking the email link, for example:
   - `http://localhost:8000/**` (adjust port if needed)
   - `https://rag-document-analysis-backend.onrender.com/**`
4. If reset emails never arrive, check **Authentication** → **Logs**, spam folders, and (if needed) **custom SMTP** under project settings.

---

## 6. Create a test user (optional)

1. Go to **Authentication** → **Users**.
2. Click **Add user** → **Create new user**.
3. Enter email and password and create the user. Use this to sign in from the Verbiage UI.

---

## 7. Verify

1. Start the Verbiage app and open the web UI.
2. You should see the sign-in panel if Supabase is configured.
3. Sign up or sign in with the test user.
4. After sign-in you should see the main app (Ingest / Ask / Documents). Ingest and Ask use your user id; documents are scoped per user.
5. Optional: use **Forgot password?**, open the email link, set a new password, and confirm you can sign in with it.

---

## Summary

| Step | Where | What |
|------|--------|------|
| 1 | Project Settings → API | Copy Project URL, anon key, JWT Secret |
| 2 | App `.env` | Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` |
| 3 | SQL Editor (optional) | Add `user_id` to `documents` if needed |
| 4 | Authentication → Providers | Enable Email (or other) auth |
| 5 | Authentication → URL Configuration | Site URL + Redirect URLs for password reset |
| 6 | Authentication → Users | Create test user (optional) |
| 7 | App UI | Sign in and use Ingest / Ask / Documents |

If the frontend shows “Supabase not configured”, the backend is not returning URL/anon key from **GET /config** — confirm the two env vars are set and the server was restarted.
