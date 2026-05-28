-- Shared document library: clear per-user ownership metadata (queries no longer filter by user_id).
UPDATE documents SET user_id = NULL WHERE user_id IS NOT NULL;
