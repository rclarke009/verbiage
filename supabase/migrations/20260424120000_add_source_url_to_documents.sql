-- Optional link to the full report (Drive URL, SharePoint, etc.)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_url TEXT;
