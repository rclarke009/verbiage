-- Report Writer: claims, section revisions, generation runs, images.

CREATE TABLE IF NOT EXISTS report_claims (
    claim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    property_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    field_notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_claims_user_updated
    ON report_claims(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS report_generation_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES report_claims(claim_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    thread_id TEXT NOT NULL,
    langgraph_checkpoint_id TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_report_generation_runs_claim
    ON report_generation_runs(claim_id, started_at DESC);

CREATE TABLE IF NOT EXISTS report_claim_section_revisions (
    revision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES report_claims(claim_id) ON DELETE CASCADE,
    section_key TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    origin TEXT NOT NULL DEFAULT 'generation',
    generation_run_id UUID REFERENCES report_generation_runs(run_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_section_revisions_claim
    ON report_claim_section_revisions(claim_id, section_key, created_at DESC);

CREATE TABLE IF NOT EXISTS report_claim_sections (
    claim_id UUID NOT NULL REFERENCES report_claims(claim_id) ON DELETE CASCADE,
    section_key TEXT NOT NULL,
    current_revision_id UUID NOT NULL REFERENCES report_claim_section_revisions(revision_id) ON DELETE CASCADE,
    PRIMARY KEY (claim_id, section_key)
);

CREATE TABLE IF NOT EXISTS report_claim_sources (
    revision_id UUID NOT NULL REFERENCES report_claim_section_revisions(revision_id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    score DOUBLE PRECISION,
    snippet TEXT,
    PRIMARY KEY (revision_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS report_claim_images (
    image_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES report_claims(claim_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    vision_analysis JSONB,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_claim_images_claim
    ON report_claim_images(claim_id, sort_order);

ALTER TABLE report_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_generation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_claim_section_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_claim_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_claim_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_claim_images ENABLE ROW LEVEL SECURITY;
