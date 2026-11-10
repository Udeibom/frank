from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError
from app.auth import get_current_user_id, owns_project
from app.models.feel import JobStatusResponse
from app.db import jobs as jobs_db
from app.db import projects as projects_db

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str, user_id: str = Depends(get_current_user_id)
) -> JobStatusResponse:
    """
    Poll a background job's status. The frontend calls this every couple of
    seconds after starting a generation job, until status is complete/failed.
    A job is visible only to the owner of its project; anything else is 404.
    """
    try:
        job = await jobs_db.get_job(job_id)
    except APIError:
        job = None  # not found, or not a valid id
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        project = await projects_db.get_project(project_id=job["project_id"])
    except APIError:
        project = None
    if not owns_project(project, user_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job["id"],
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
    )
