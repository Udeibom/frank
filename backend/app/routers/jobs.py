from fastapi import APIRouter, HTTPException
from app.models.feel import JobStatusResponse
from app.db import jobs as jobs_db

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Poll a background job's status. The frontend calls this every couple of
    seconds after starting a generation job, until status is complete/failed.
    """
    job = await jobs_db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job["id"],
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
    )
