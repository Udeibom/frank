-- 012: jobs a separate worker can claim (core-path spec 15, requirement 1). Additive and safe to re-run.
-- Rollback: DROP FUNCTION claim_job(text); DROP FUNCTION worker_beat(text, jsonb); DROP TABLE worker_heartbeats;
--           ALTER TABLE async_jobs DROP COLUMN payload, DROP COLUMN claimed_by, DROP COLUMN claimed_at;

ALTER TABLE async_jobs ADD COLUMN IF NOT EXISTS payload    jsonb;        -- {"runner", "args", "region"}
ALTER TABLE async_jobs ADD COLUMN IF NOT EXISTS claimed_by text;
ALTER TABLE async_jobs ADD COLUMN IF NOT EXISTS claimed_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_async_jobs_queue ON async_jobs (created_at) WHERE status = 'pending' AND payload IS NOT NULL;

CREATE TABLE IF NOT EXISTS worker_heartbeats (
    worker   text PRIMARY KEY,
    beat_at  timestamptz NOT NULL DEFAULT now(),
    info     jsonb
);
ALTER TABLE worker_heartbeats ENABLE ROW LEVEL SECURITY;    -- server only (service role)

CREATE OR REPLACE FUNCTION worker_beat(p_worker text, p_info jsonb DEFAULT NULL)
RETURNS void LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    INSERT INTO worker_heartbeats (worker, beat_at, info) VALUES (p_worker, now(), p_info)
    ON CONFLICT (worker) DO UPDATE SET beat_at = now(), info = COALESCE(EXCLUDED.info, worker_heartbeats.info);
$$;

-- The oldest waiting job with a payload, taken by exactly one worker.
CREATE OR REPLACE FUNCTION claim_job(p_worker text)
RETURNS SETOF async_jobs LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    UPDATE async_jobs SET status = 'processing', claimed_by = p_worker, claimed_at = now()
     WHERE id = (SELECT id FROM async_jobs
                  WHERE status = 'pending' AND payload IS NOT NULL
                  ORDER BY created_at
                  FOR UPDATE SKIP LOCKED
                  LIMIT 1)
    RETURNING *;
$$;

REVOKE ALL ON FUNCTION worker_beat(text, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION claim_job(text) FROM PUBLIC, anon, authenticated;

-- Staged inputs for queued jobs (uploads the worker reads). Private; removed by the worker after use.
INSERT INTO storage.buckets (id, name, public) VALUES ('job-inputs', 'job-inputs', false)
ON CONFLICT (id) DO NOTHING;
