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


# ── a second master, matched to a song they picked (frankenstein spec 14, requirement 6.4) ───────────────

from typing import Optional  # noqa: E402

from fastapi import File, Form, UploadFile  # noqa: E402


@router.post("/match", response_model=JobResponse)
async def match_to_reference(project_id: str, background: BackgroundTasks, mix_version_id: str = Form(...),
                             file: Optional[UploadFile] = File(None), jamendo_track_id: Optional[str] = Form(None),
                             rights_confirmed: bool = Form(False)) -> JobResponse:
    """Finish the song so it sits as loud, bright and wide as a song they picked. Frank's own finish is kept."""
    from app.services.jobs.export_runner import run_matched_job

    if file is not None:
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Only use a song you're allowed to use. Tick the box to say so.")
        data = await file.read(50 * 1024 * 1024 + 1)
        if len(data) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="That file is too big for me. A song under 50 MB works.")
        ext = (file.filename or "song.mp3").rsplit(".", 1)[-1].lower()
    elif jamendo_track_id:
        import asyncio

        from app.services.reference import jamendo

        if not jamendo.available():
            raise HTTPException(status_code=503, detail="Picking from free music isn't switched on yet.")
        track = await asyncio.to_thread(jamendo.get, jamendo_track_id)
        if not track:
            raise HTTPException(status_code=404, detail="I couldn't find that song any more.")
        data, ext = await asyncio.to_thread(jamendo.fetch_audio, track), "mp3"
    else:
        raise HTTPException(status_code=400, detail="Pick a song to match first.")
    job = await jobs_db.create_job(project_id, job_type="export_matched")
    background.add_task(run_matched_job, job["id"], project_id, mix_version_id, data, ext)
    return JobResponse(job_id=job["id"])
