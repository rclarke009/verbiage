-- Lexical (full-text) search support for hybrid retrieval.
-- Generated tsvector keeps itself in sync with chunks.content (no ingest code change).

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv ON chunks USING GIN (content_tsv);