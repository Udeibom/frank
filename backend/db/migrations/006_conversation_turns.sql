-- Stored conversations (team-conversation spec 07, requirement 7). Additive and repeatable.
-- Every exchange in every room is kept per project, so a reload or another device shows it, and older turns are
-- summarised after 20 exchanges. Rollback: DROP TABLE IF EXISTS conversation_summaries; DROP TABLE IF EXISTS conversation_turns;
CREATE TABLE IF NOT EXISTS conversation_turns (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    room        TEXT NOT NULL CHECK (room IN ('idea', 'feel', 'beat', 'voice', 'mix', 'export')),
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    actions     JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conversation_turns_room ON conversation_turns (project_id, room, created_at);

CREATE TABLE IF NOT EXISTS conversation_summaries (
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    room        TEXT NOT NULL,
    summary     TEXT NOT NULL,
    turns_covered INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, room)
);

ALTER TABLE conversation_turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_summaries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS conversation_turns_owner ON conversation_turns;
CREATE POLICY conversation_turns_owner ON conversation_turns
    USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND p.user_id = auth.uid()));
DROP POLICY IF EXISTS conversation_summaries_owner ON conversation_summaries;
CREATE POLICY conversation_summaries_owner ON conversation_summaries
    USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND p.user_id = auth.uid()));
