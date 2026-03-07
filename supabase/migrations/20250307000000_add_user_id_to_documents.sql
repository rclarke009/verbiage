-- Add user_id to documents for Supabase Auth (per-user documents).
-- Run in Supabase Dashboard → SQL Editor if you manage schema there.
-- The app's create_db() also adds this column on startup for new/empty DBs.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
