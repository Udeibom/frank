"""Listener route (listener spec 03). Mounted under the project ownership check. Read-only."""
from __future__ import annotations
from app.services.jobs import dispatch

from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.db import jobs as jobs_db
from app.models.feel import JobResponse
from app.services.jobs.listen_runner import run_listen_job

router = APIRouter(prefix="/projects/{project_id}/listen", tags=["listener"])


class ListenRequest(BaseModel):
    scope: Optional[list[str]] = Field(default=None, max_length=12)   # section names, e.g. ["chorus"]
    concern: Optional[str] = Field(default=None, max_length=300)      # what the person said felt wrong


@router.post("", response_model=JobResponse)
async def listen(project_id: str, body: ListenRequest, background: BackgroundTasks) -> JobResponse:
    """Start listening. Poll /jobs/{id}/status: result holds `measurements` and `findings`."""
    job = await jobs_db.create_job(project_id, job_type="listen")
    await dispatch.start(background, job, run_listen_job, project_id, body.scope, body.concern)
    return JobResponse(job_id=job["id"])
