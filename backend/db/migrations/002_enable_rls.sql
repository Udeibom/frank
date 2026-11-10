-- 002_enable_rls.sql
-- Turn on Row Level Security for every application table.
--
-- Frank's browser never queries these tables directly: all data goes through the
-- FastAPI backend, which connects with the service role and therefore bypasses
-- RLS. So we enable RLS and add NO policies, which closes the `anon` and
-- `authenticated` roles completely. A leaked public (anon) key then exposes
-- nothing. Ownership is enforced in the backend (app/auth.py).
--
-- Rollback (if ever needed): ALTER TABLE <name> DISABLE ROW LEVEL SECURITY;

ALTER TABLE public.projects             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_active_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lyrics_versions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feel_fingerprints    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.texture_samples      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.beat_versions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.beat_stems           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vocal_takes          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vocal_comps          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mix_versions         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exports              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.async_jobs           ENABLE ROW LEVEL SECURITY;
