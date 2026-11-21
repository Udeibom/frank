-- 011: monthly budgets for outside services with small free allowances, and a shared cache of song research
-- (frankenstein spec 14). Additive and safe to re-run.
-- Rollback: DROP FUNCTION use_service(text, integer); DROP TABLE service_usage, research_cache;

CREATE TABLE IF NOT EXISTS service_usage (
    service text NOT NULL,
    month   text NOT NULL,                 -- 'YYYY-MM' (UTC)
    used    integer NOT NULL DEFAULT 0,
    PRIMARY KEY (service, month)
);

-- One row per song researched, shared by every user: the same song is never paid for twice.
CREATE TABLE IF NOT EXISTS research_cache (
    song_key   text PRIMARY KEY,           -- normalised "title|artist"
    result     jsonb,                      -- null when nothing useful was found (still cached)
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE service_usage ENABLE ROW LEVEL SECURITY;   -- server only (service role); no policies for users
ALTER TABLE research_cache ENABLE ROW LEVEL SECURITY;

-- Spend `amount` of this month's allowance if it fits under `cap`, atomically. True when spent.
CREATE OR REPLACE FUNCTION use_service(p_service text, p_cap integer, p_amount integer DEFAULT 1)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    m text := to_char(now() AT TIME ZONE 'utc', 'YYYY-MM');
    n integer;
BEGIN
    INSERT INTO service_usage (service, month, used) VALUES (p_service, m, 0)
    ON CONFLICT (service, month) DO NOTHING;
    UPDATE service_usage SET used = used + p_amount
     WHERE service = p_service AND month = m AND used + p_amount <= p_cap
    RETURNING used INTO n;
    RETURN n IS NOT NULL;
END;
$$;

REVOKE ALL ON FUNCTION use_service(text, integer, integer) FROM PUBLIC, anon, authenticated;
