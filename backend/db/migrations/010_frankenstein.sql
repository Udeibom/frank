-- 010: Frankenstein (spec 14). Additive and repeatable.
-- Sound memory (pgvector), references, provenance (credits), word timings on takes, live job updates.
-- Rollback: DROP TABLE sound_embeddings, song_references, provenance;
--           ALTER TABLE vocal_takes DROP COLUMN words; ALTER PUBLICATION supabase_realtime DROP TABLE async_jobs;
--           DROP POLICY async_jobs_owner_read ON async_jobs; (the vector extension can stay)

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- What things sound like, as CLAP vectors (512 numbers), so memory can match by sound.
CREATE TABLE IF NOT EXISTS sound_embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID,
    project_id  UUID REFERENCES projects(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('texture', 'part', 'beat', 'mix', 'reference', 'taste', 'words')),
    ref_id      TEXT NOT NULL,
    model       TEXT NOT NULL,
    embedding   extensions.vector(512) NOT NULL,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sound_embeddings_ref ON sound_embeddings (kind, ref_id, model);
CREATE INDEX IF NOT EXISTS idx_sound_embeddings_user ON sound_embeddings (user_id, kind);
CREATE INDEX IF NOT EXISTS idx_sound_embeddings_project ON sound_embeddings (project_id, kind);

-- Nearest sounds for one user (or one song), by cosine distance.
CREATE OR REPLACE FUNCTION match_sounds(query extensions.vector(512), for_user UUID, for_kinds TEXT[], for_project UUID DEFAULT NULL, how_many INT DEFAULT 5)
RETURNS TABLE (id UUID, kind TEXT, ref_id TEXT, project_id UUID, meta JSONB, similarity REAL)
LANGUAGE sql STABLE AS $$
    SELECT e.id, e.kind, e.ref_id, e.project_id, e.meta, (1 - (e.embedding OPERATOR(extensions.<=>) query))::real
    FROM sound_embeddings e
    WHERE e.user_id = for_user AND e.kind = ANY(for_kinds) AND (for_project IS NULL OR e.project_id = for_project)
    ORDER BY e.embedding OPERATOR(extensions.<=>) query
    LIMIT how_many
$$;

-- A song the person points at. Uploaded audio is never stored: only what Frank heard in it.
CREATE TABLE IF NOT EXISTS song_references (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source      TEXT NOT NULL CHECK (source IN ('upload', 'jamendo', 'named')),
    title       TEXT,
    artist      TEXT,
    license     TEXT,
    attribution TEXT,
    external_id TEXT,
    analysis    JSONB NOT NULL DEFAULT '{}'::jsonb,
    active      BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_song_references_project ON song_references (project_id, created_at DESC);

-- Where each piece of help came from, in plain words: the change line and the credits page.
CREATE TABLE IF NOT EXISTS provenance (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    layer       TEXT NOT NULL,
    version_id  TEXT,
    organ       TEXT NOT NULL,
    plain       TEXT NOT NULL,
    attribution TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_provenance_project ON provenance (project_id, created_at);

-- When each sung word happens in a take.
ALTER TABLE vocal_takes ADD COLUMN IF NOT EXISTS words JSONB;

ALTER TABLE sound_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE song_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE provenance ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sound_embeddings_owner ON sound_embeddings;
CREATE POLICY sound_embeddings_owner ON sound_embeddings USING (user_id = auth.uid());
DROP POLICY IF EXISTS song_references_owner ON song_references;
CREATE POLICY song_references_owner ON song_references
    USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND p.user_id = auth.uid()));
DROP POLICY IF EXISTS provenance_owner ON provenance;
CREATE POLICY provenance_owner ON provenance
    USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND p.user_id = auth.uid()));

-- Live job updates: the browser may read (only) its own jobs through Realtime.
DROP POLICY IF EXISTS async_jobs_owner_read ON async_jobs;
CREATE POLICY async_jobs_owner_read ON async_jobs FOR SELECT
    USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND p.user_id = auth.uid()));
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication_tables WHERE pubname = 'supabase_realtime' AND tablename = 'async_jobs') THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE async_jobs;
    END IF;
END $$;
