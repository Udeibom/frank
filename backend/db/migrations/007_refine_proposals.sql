-- Refine loop (spec 08, requirements 2.1 and 3.1). Additive and repeatable.
-- One row per "something feels wrong": what the person said, what the Listener found, the two or three directions
-- offered (each with its typed actions and, once heard, its preview), and which one they chose.
-- Rollback: DROP TABLE IF EXISTS refine_proposals;
CREATE TABLE IF NOT EXISTS refine_proposals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    concern     TEXT,
    findings    JSONB NOT NULL DEFAULT '{}'::jsonb,
    experiment  BOOLEAN NOT NULL DEFAULT false,
    directions  JSONB NOT NULL DEFAULT '[]'::jsonb,
    based_on    JSONB NOT NULL DEFAULT '{}'::jsonb,   -- version ids the directions were built on (beat, mix)
    chosen      INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_refine_proposals_project ON refine_proposals (project_id, created_at DESC);

ALTER TABLE refine_proposals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS refine_proposals_owner ON refine_proposals;
CREATE POLICY refine_proposals_owner ON refine_proposals
    USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND p.user_id = auth.uid()));
