"""
Database access for async jobs.

Long audio operations (texture/beat generation, mixing, mastering) run in the
background. A job row tracks status so the frontend can poll. This keeps request
handlers fast and avoids Render free-tier request timeouts.

Every job must end as complete or failed (job-reliability spec): mark_failed
retries, and fail_if_stale / fail_jobs_active_before resolve jobs whose worker
died before it could say so.
"""

from datetime import datetime
from typing import Optional, Any
from app.db.client import get_supabase
from app.services.jobs.staleness import ACTIVE_STATUSES, with_retries


async def create_job(project_id: str, job_type: str) -> dict:
    """Create a pending job and return it."""
    supabase = get_supabase()
    result = (
        supabase.table("async_jobs")
        .insert({"project_id": project_id, "job_type": job_type, "status": "pending"})
        .execute()
    )
    return result.data[0]


async def mark_processing(job_id: str) -> None:
    supabase = get_supabase()
    supabase.table("async_jobs").update({"status": "processing"}).eq(
        "id", job_id
    ).execute()


async def mark_complete(job_id: str, result: dict[str, Any]) -> None:
    supabase = get_supabase()
    supabase.table("async_jobs").update(
        {"status": "complete", "result": result}
    ).eq("id", job_id).execute()


async def mark_failed(job_id: str, error: str) -> None:
    """Record a failure, retrying through brief network blips. If every attempt
    fails, the stale-job check resolves the job later."""

    async def _write() -> None:
        get_supabase().table("async_jobs").update(
            {"status": "failed", "error": error}
        ).eq("id", job_id).execute()

    await with_retries(_write)


async def fail_if_stale(job_id: str, error: str, changed_before: datetime) -> bool:
    """Mark ONE job failed only if it is still active and unchanged since
    `changed_before`. Returns True if this call changed it. A job that completed
    meanwhile no longer matches, so it is never clobbered."""
    result = (
        get_supabase()
        .table("async_jobs")
        .update({"status": "failed", "error": error})
        .eq("id", job_id)
        .in_("status", list(ACTIVE_STATUSES))
        .lt("updated_at", changed_before.isoformat())
        .execute()
    )
    return bool(result.data)


async def fail_jobs_active_before(error: str, changed_before: datetime) -> int:
    """Startup sweep: mark failed every job still active that last changed
    before `changed_before`. Returns how many were changed."""
    result = (
        get_supabase()
        .table("async_jobs")
        .update({"status": "failed", "error": error})
        .in_("status", list(ACTIVE_STATUSES))
        .lt("updated_at", changed_before.isoformat())
        .execute()
    )
    return len(result.data or [])


async def get_job(job_id: str) -> Optional[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("async_jobs").select("*").eq("id", job_id).single().execute()
    )
    return result.data
