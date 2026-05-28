-- Canonical document text + indexing metadata for re-chunk/re-embed without re-upload.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS full_text TEXT NOT NULL DEFAULT '';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_filename TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunking_config JSONB;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_model TEXT;

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS section_label TEXT;
