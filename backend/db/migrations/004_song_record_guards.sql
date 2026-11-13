-- 004_song_record_guards.sql
-- Makes the Song Record's rules true in the database itself, not only in the code
-- (found by the Integration Tester and Code Reviewer agents, Nov 12).
--
-- 1. One root per facet. Two parallel first writes used to leave a facet with two roots
--    (the second write did not see the first). Now the database refuses the second root and the
--    backend retries it as a child of the first.
-- 2. Rows are never edited. Facet versions and decisions are append-only; an UPDATE is refused.
--    (Deleting is still allowed so that removing a whole project cascades, as before.)
--
-- Rollback:
--   DROP INDEX IF EXISTS one_root_per_facet;
--   DROP TRIGGER IF EXISTS song_facet_versions_no_update ON song_facet_versions;
--   DROP TRIGGER IF EXISTS song_decisions_no_update ON song_decisions;
--   DROP FUNCTION IF EXISTS refuse_update();

CREATE UNIQUE INDEX IF NOT EXISTS one_root_per_facet
    ON song_facet_versions (project_id, facet)
    WHERE parent_id IS NULL;

CREATE OR REPLACE FUNCTION refuse_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'rows in % are append-only and cannot be updated', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS song_facet_versions_no_update ON song_facet_versions;
CREATE TRIGGER song_facet_versions_no_update
    BEFORE UPDATE ON song_facet_versions
    FOR EACH ROW EXECUTE FUNCTION refuse_update();

DROP TRIGGER IF EXISTS song_decisions_no_update ON song_decisions;
CREATE TRIGGER song_decisions_no_update
    BEFORE UPDATE ON song_decisions
    FOR EACH ROW EXECUTE FUNCTION refuse_update();
