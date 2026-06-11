-- Support user-initiated cancellation of ingest batches (Drive ingest, photo vision).

ALTER TABLE ingest_batches
    ADD COLUMN IF NOT EXISTS cancelled INT NOT NULL DEFAULT 0;
