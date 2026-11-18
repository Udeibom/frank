-- Sing It (spec 06). Additive and repeatable.
-- vocal_takes: a derived version (tuned, lined up, beat taken out, harmony) is its own row linked to the take it
-- came from, so nothing is overwritten and every version can be chosen. Harmony is marked in the data
-- (requirement 6.3), backfilled from the old "Harmony" label prefix.
-- user_settings: the device delay measured by the timing check (requirement 3.1).
-- guide_renders: the guide for a beat version is made once and reused.
-- Rollback: ALTER TABLE vocal_takes DROP COLUMN IF EXISTS is_harmony, DROP COLUMN IF EXISTS parent_take_id,
--   DROP COLUMN IF EXISTS kind, DROP COLUMN IF EXISTS params, DROP COLUMN IF EXISTS facts;
--   DROP TABLE IF EXISTS user_settings; DROP TABLE IF EXISTS guide_renders;
ALTER TABLE vocal_takes ADD COLUMN IF NOT EXISTS is_harmony BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE vocal_takes ADD COLUMN IF NOT EXISTS parent_take_id UUID REFERENCES vocal_takes(id);
ALTER TABLE vocal_takes ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'take';
ALTER TABLE vocal_takes ADD COLUMN IF NOT EXISTS params JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE vocal_takes ADD COLUMN IF NOT EXISTS facts JSONB NOT NULL DEFAULT '{}'::jsonb;
UPDATE vocal_takes SET is_harmony = true, kind = 'harmony' WHERE label ILIKE 'harmony%' AND is_harmony = false;
CREATE INDEX IF NOT EXISTS idx_vocal_takes_parent ON vocal_takes (parent_take_id);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id        UUID PRIMARY KEY,
    input_delay_ms REAL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS user_settings_owner ON user_settings;
CREATE POLICY user_settings_owner ON user_settings USING (user_id = auth.uid());

CREATE TABLE IF NOT EXISTS guide_renders (
    beat_version_id UUID PRIMARY KEY REFERENCES beat_versions(id) ON DELETE CASCADE,
    audio_url       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE guide_renders ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS guide_renders_owner ON guide_renders;
CREATE POLICY guide_renders_owner ON guide_renders
    USING (EXISTS (SELECT 1 FROM beat_versions b JOIN projects p ON p.id = b.project_id
                   WHERE b.id = beat_version_id AND p.user_id = auth.uid()));
