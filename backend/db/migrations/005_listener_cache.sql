-- Listener measurement cache (listener spec 03, req 5.1). Additive and repeatable.
-- Rollback: DROP TABLE IF EXISTS listener_cache;
CREATE TABLE IF NOT EXISTS listener_cache (
    audio_version_id TEXT PRIMARY KEY,
    kind             TEXT NOT NULL DEFAULT 'report',
    report           JSONB NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE listener_cache ENABLE ROW LEVEL SECURITY;
