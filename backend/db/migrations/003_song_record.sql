-- 003_song_record.sql
-- Song Record (song-record spec 01): facets with lineage, a decisions log, and a project phase.
--
-- Only ADDS tables and one defaulted column. Existing projects keep working; their new facets
-- are simply empty. Version and decision rows are append-only: the backend never updates or
-- deletes them. RLS is enabled with no policies, same as 002 (the backend uses the service role
-- and enforces ownership in app/auth.py).
--
-- Rollback:
--   DROP TABLE song_decisions; DROP TABLE song_facet_active; DROP TABLE song_facet_versions;
--   ALTER TABLE project_active_state DROP COLUMN phase;

CREATE TABLE IF NOT EXISTS song_facet_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    facet       TEXT NOT NULL CHECK (facet IN
                  ('intent','feeling','melody','structure','references','identity_brief')),
    content     JSONB NOT NULL DEFAULT '{}'::jsonb,
    parent_id   UUID REFERENCES song_facet_versions(id),
    operation   TEXT NOT NULL,
    op_params   JSONB NOT NULL DEFAULT '{}'::jsonb,
    author      TEXT NOT NULL,
    label       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_song_facet_versions_lane
    ON song_facet_versions (project_id, facet, created_at);

CREATE TABLE IF NOT EXISTS song_facet_active (
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    facet       TEXT NOT NULL,
    version_id  UUID NOT NULL REFERENCES song_facet_versions(id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, facet)
);

CREATE TABLE IF NOT EXISTS song_decisions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    summary       TEXT NOT NULL,
    rationale     TEXT,
    proposed_by   TEXT NOT NULL DEFAULT 'frank',
    options       JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence      JSONB NOT NULL DEFAULT '[]'::jsonb,
    chosen_option TEXT,
    user_reaction TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_song_decisions_project
    ON song_decisions (project_id, created_at DESC);

ALTER TABLE project_active_state
    ADD COLUMN IF NOT EXISTS phase TEXT NOT NULL DEFAULT 'creating'
        CHECK (phase IN ('creating','refining'));

ALTER TABLE public.song_facet_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.song_facet_active   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.song_decisions      ENABLE ROW LEVEL SECURITY;
