ALTER TABLE async_jobs ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS idx_async_jobs_active_idem
    ON async_jobs (project_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND status IN ('pending', 'processing');

ALTER TABLE refine_proposals ADD COLUMN IF NOT EXISTS basis_key text;
ALTER TABLE refine_proposals ADD COLUMN IF NOT EXISTS idempotency_key text;
ALTER TABLE refine_proposals ADD COLUMN IF NOT EXISTS chosen_job_id text;
CREATE INDEX IF NOT EXISTS idx_refine_proposals_idem
    ON refine_proposals (project_id, idempotency_key, created_at DESC);
