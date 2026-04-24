-- Closed signup: emails allowed to register (lowercase). Server checks this table; RLS blocks API access.
CREATE TABLE IF NOT EXISTS signup_allowlist (
    email TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    note TEXT
);

ALTER TABLE signup_allowlist ENABLE ROW LEVEL SECURITY;
