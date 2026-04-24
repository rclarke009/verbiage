-- Optional: source file last-modified time (Unix seconds) for ingest comparison UX.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_modified_at BIGINT;
