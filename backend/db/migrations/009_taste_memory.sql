-- Taste memory (spec 09). Additive and repeatable. Taste belongs to the user, not a project, and is private.
-- taste_signals: one piece of evidence ("chose thinner verses in this song").
-- taste_preferences: a preference stated only after repeated evidence, or said directly by the person.
-- Forgetting DELETES rows (requirement 4.2). Rollback: DROP TABLE IF EXISTS taste_preferences; DROP TABLE IF EXISTS taste_signals;
CREATE TABLE IF NOT EXISTS taste_signals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    project_id  UUID REFERENCES projects(id) ON DELETE SET NULL,
    specialist  TEXT NOT NULL,
    topic       TEXT NOT NULL,
    direction   SMALLINT NOT NULL CHECK (direction IN (-1, 1)),
    statement   TEXT NOT NULL,
    source      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_taste_signals_user_topic ON taste_signals (user_id, topic, created_at);

CREATE TABLE IF NOT EXISTS taste_preferences (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL,
    specialist     TEXT NOT NULL,
    topic          TEXT NOT NULL,
    direction      SMALLINT NOT NULL CHECK (direction IN (-1, 1)),
    statement      TEXT NOT NULL,
    strength       REAL NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired', 'user_stated')),
    edited_by_user BOOLEAN NOT NULL DEFAULT false,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_taste_preferences_user ON taste_preferences (user_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_taste_learned ON taste_preferences (user_id, topic) WHERE status <> 'user_stated';

ALTER TABLE taste_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE taste_preferences ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS taste_signals_owner ON taste_signals;
CREATE POLICY taste_signals_owner ON taste_signals USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
DROP POLICY IF EXISTS taste_preferences_owner ON taste_preferences;
CREATE POLICY taste_preferences_owner ON taste_preferences USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
