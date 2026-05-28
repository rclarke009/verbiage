-- Async ingest job queue: batches group user actions; jobs are one document each.

CREATE TABLE IF NOT EXISTS ingest_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total INT NOT NULL DEFAULT 0,
    pending INT NOT NULL DEFAULT 0,
    running INT NOT NULL DEFAULT 0,
    succeeded INT NOT NULL DEFAULT 0,
    failed INT NOT NULL DEFAULT 0,
    skipped INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES ingest_batches(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    kind TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    result JSONB,
    error TEXT,
    attempts INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status_created ON ingest_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_batch ON ingest_jobs(batch_id);
