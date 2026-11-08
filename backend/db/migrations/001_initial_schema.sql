-- Frank — Initial Database Schema
-- Run this in your Supabase SQL editor to set up all tables.
-- Supabase already has the uuid-ossp and pgcrypto extensions enabled.

-- ─────────────────────────────────────────────
-- PROJECTS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    title       TEXT NOT NULL DEFAULT 'Untitled Song',
    status      TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'in_progress', 'exported')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────
-- PROJECT ACTIVE STATE
-- One row per project — tracks which version is "live" in each layer
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS project_active_state (
    project_id              UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    active_lyrics_id        UUID,
    active_fingerprint_id   UUID,
    active_beat_version_id  UUID,
    active_vocal_id         UUID,
    active_comp_id          UUID,
    active_mix_id           UUID,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER project_active_state_updated_at
    BEFORE UPDATE ON project_active_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────
-- LYRICS VERSIONS
-- Every save is a new version. Nothing is overwritten.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lyrics_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content     TEXT NOT NULL DEFAULT '',
    label       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lyrics_versions_project ON lyrics_versions(project_id, created_at DESC);

-- ─────────────────────────────────────────────
-- FEEL FINGERPRINTS
-- Each fingerprint is a snapshot of the musical identity at a point in time
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feel_fingerprints (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    fingerprint             JSONB NOT NULL DEFAULT '{}',
    conversation_summary    TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_feel_fingerprints_project ON feel_fingerprints(project_id, created_at DESC);

-- ─────────────────────────────────────────────
-- TEXTURE SAMPLES
-- Short atmospheric audio clips generated during Feel Lab
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS texture_samples (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    fingerprint_id  UUID REFERENCES feel_fingerprints(id) ON DELETE SET NULL,
    audio_url       TEXT NOT NULL,
    cache_key       TEXT,
    approved        BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_texture_samples_cache
    ON texture_samples(project_id, cache_key);

-- ─────────────────────────────────────────────
-- BEAT VERSIONS
-- Each beat version is a fully rendered instrumental
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS beat_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    render_url  TEXT,
    label       TEXT,
    params      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_beat_versions_project ON beat_versions(project_id, created_at DESC);

-- ─────────────────────────────────────────────
-- BEAT STEMS
-- Individual instrument layers within a beat, per section
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS beat_stems (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    beat_version_id  UUID REFERENCES beat_versions(id) ON DELETE CASCADE,
    stem_type        TEXT NOT NULL,
    section          TEXT,
    audio_url        TEXT NOT NULL,
    version_of       UUID REFERENCES beat_stems(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- VOCAL TAKES
-- Every recorded vocal take, raw and processed versions
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vocal_takes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    audio_url       TEXT NOT NULL,
    processed_url   TEXT,
    pitch_data      JSONB,
    label           TEXT,
    deleted         BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_vocal_takes_project ON vocal_takes(project_id, created_at DESC);

-- ─────────────────────────────────────────────
-- VOCAL COMPS
-- Assembled best-of from multiple takes
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vocal_comps (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    audio_url   TEXT NOT NULL,
    segments    JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- MIX VERSIONS
-- Each mix render with its parameters snapshot
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mix_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    render_url  TEXT,
    label       TEXT,
    mix_params  JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mix_versions_project ON mix_versions(project_id, created_at DESC);

-- ─────────────────────────────────────────────
-- EXPORTS
-- Final deliverable MP3s
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    mix_version_id  UUID REFERENCES mix_versions(id) ON DELETE SET NULL,
    storage_path    TEXT,
    audio_url       TEXT NOT NULL,
    format          TEXT NOT NULL DEFAULT 'mp3',
    quality         TEXT NOT NULL DEFAULT '320k',
    mastered        BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- ASYNC JOBS
-- Tracks background processing jobs (beat gen, pitch correction, mixing, etc.)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS async_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_type    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'complete', 'failed')),
    result      JSONB,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER async_jobs_updated_at
    BEFORE UPDATE ON async_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE INDEX idx_async_jobs_project_status ON async_jobs(project_id, status);

-- ─────────────────────────────────────────────
-- FOREIGN KEY CONSTRAINTS FOR ACTIVE STATE
-- Added after all tables exist
-- ─────────────────────────────────────────────
ALTER TABLE project_active_state
    ADD CONSTRAINT fk_active_lyrics
        FOREIGN KEY (active_lyrics_id) REFERENCES lyrics_versions(id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_active_fingerprint
        FOREIGN KEY (active_fingerprint_id) REFERENCES feel_fingerprints(id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_active_beat_version
        FOREIGN KEY (active_beat_version_id) REFERENCES beat_versions(id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_active_vocal
        FOREIGN KEY (active_vocal_id) REFERENCES vocal_takes(id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_active_comp
        FOREIGN KEY (active_comp_id) REFERENCES vocal_comps(id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_active_mix
        FOREIGN KEY (active_mix_id) REFERENCES mix_versions(id) ON DELETE SET NULL;
