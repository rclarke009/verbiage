-- Drive-backed claim photos: reference by drive_file_id, background vision analysis.

ALTER TABLE report_claim_images
    ALTER COLUMN storage_path DROP NOT NULL;

ALTER TABLE report_claim_images
    ADD COLUMN IF NOT EXISTS drive_file_id TEXT,
    ADD COLUMN IF NOT EXISTS source_url TEXT,
    ADD COLUMN IF NOT EXISTS analysis_status TEXT NOT NULL DEFAULT 'pending';

CREATE UNIQUE INDEX IF NOT EXISTS idx_report_claim_images_drive_unique
    ON report_claim_images (claim_id, drive_file_id)
    WHERE drive_file_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_report_claim_images_analysis
    ON report_claim_images (claim_id, analysis_status);
