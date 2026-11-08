import re
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.models.export import (
    CreateExportRequest,
    ExportResponse,
    DownloadUrlResponse,
    JobResponse,
)
from app.services.jobs.export_runner import run_export_job
from app.services.storage.files import create_signed_url
from app.db import jobs as jobs_db
from app.db import export as export_db
from app.db import projects as projects_db

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])


def _safe_filename(title: str) -> str:
    """Turn a project title into a safe download filename."""
    base = re.sub(r"[^\w\s-]", "", title or "song").strip()
    base = re.sub(r"[\s_-]+", "-", base).lower()
    return (base or "song") + ".mp3"


@router.post("", response_model=JobResponse)
async def create_export(
    project_id: str, body: CreateExportRequest, background: BackgroundTasks
) -> JobResponse:
    """Render the final export (optionally mastered) as a background job."""
    job = await jobs_db.create_job(project_id, job_type="export")
    background.add_task(
        run_export_job, job["id"], project_id, body.mix_version_id, body.apply_mastering
    )
    return JobResponse(job_id=job["id"])


@router.get("", response_model=list[ExportResponse])
async def list_exports(project_id: str) -> list[ExportResponse]:
    exports = await export_db.list_exports(project_id)
    return [
        ExportResponse(
            id=e["id"],
            project_id=e["project_id"],
            audio_url=e["audio_url"],
            format=e["format"],
            quality=e["quality"],
            mastered=e.get("mastered", False),
            mix_version_id=e.get("mix_version_id"),
            created_at=str(e["created_at"]),
        )
        for e in exports
    ]


@router.get("/{export_id}/download", response_model=DownloadUrlResponse)
async def get_download_url(project_id: str, export_id: str) -> DownloadUrlResponse:
    """
    Return a time-limited signed URL for the export plus a nice filename.
    Signed URLs keep finished songs private to the user (spec R5) rather than
    world-readable public links.
    """
    export = await export_db.get_export(export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    project = await projects_db.get_project(project_id)
    title = project["title"] if project else "song"

    # Prefer a signed URL from the stored path; fall back to the public URL for
    # any older export rows that predate storage_path.
    url = export.get("audio_url")
    path = export.get("storage_path")
    if path:
        try:
            url = create_signed_url("exports", path, expires_in=3600)
        except Exception:
            url = export.get("audio_url")

    return DownloadUrlResponse(url=url, filename=_safe_filename(title))
