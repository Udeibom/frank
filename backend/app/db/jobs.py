"""
Database access for async jobs.

Long audio operations (texture/beat generation, mixing, mastering) run in the
background. A job row tracks status so the frontend can poll. This keeps request
handlers fast and avoids Render free-tier request timeouts.
"""

from typing import Optional, Any
from app.db.client import get_supabase


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
    supabase = get_supabase()
    supabase.table("async_jobs").update(
        {"status": "failed", "error": error}
    ).eq("id", job_id).execute()


async def get_job(job_id: str) -> Optional[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("async_jobs").select("*").eq("id", job_id).single().execute()
    )
    return result.data
