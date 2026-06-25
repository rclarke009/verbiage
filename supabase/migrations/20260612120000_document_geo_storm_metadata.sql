-- Document geo/storm metadata for structured Ask nearby-storm queries.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS storm_id TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS storm_name TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS storm_date_iso TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_documents_storm_id ON documents(storm_id);
CREATE INDEX IF NOT EXISTS idx_documents_storm_geo ON documents(storm_id, latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
