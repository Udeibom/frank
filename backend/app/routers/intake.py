"""Intake routes (start-from-any-input spec 02). Mounted under the project ownership check."""

from __future__ import annotations

import re

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError

from app.db import jobs as jobs_db
from app.db import song as song_db
from app.models.feel import JobResponse
from app.models.song import FacetVersionResponse, MelodySketch
from app.services.intake.hints import fingerprint_hints
from app.services.jobs.intake_runner import run_hum_intake_job
from app.services.song import store
from app.services.song.versions import VersionError

router = APIRouter(prefix="/projects/{project_id}/intake", tags=["intake"])

# A minute of hum is well under a megabyte in a browser's format and around 10 MB as raw phone audio.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_EXTENSION = re.compile(r"[a-z0-9]{1,5}")


class ConfirmMelodyResponse(BaseModel):
    version: FacetVersionResponse
    fingerprint_hints: dict


def safe_extension(filename: str | None) -> str:
    """The extension only labels a temp file; anything odd becomes 'webm' (the browser default)."""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if _EXTENSION.fullmatch(ext):
            return ext
    return "webm"


async def _read_limited(file: UploadFile) -> bytes:
    """Read the upload but stop as soon as it is too big, instead of holding all of it first."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="That recording is too big for me. Could you try a shorter one?")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/hum", response_model=JobResponse)
async def start_hum_intake(
    project_id: str, background: BackgroundTasks, file: UploadFile = File(...)
) -> JobResponse:
    """Turn a hum into a tune. Returns a job id; the tune waits for the person's yes before it is used."""
    raw = await _read_limited(file)
    if not raw:
        raise HTTPException(status_code=400, detail="I didn't get any sound from that recording. Could you try once more?")
    job = await jobs_db.create_job(project_id, job_type="hum_intake")
    background.add_task(run_hum_intake_job, job["id"], project_id, raw, safe_extension(file.filename))
    return JobResponse(job_id=job["id"])


async def _find_melody(project_id: str, version_id: str):
    versions = await song_db.list_versions(project_id, "melody")
    found = next((v for v in versions if v.id == version_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail="I can't find that tune any more.")
    return found


@router.post("/melody/{version_id}/confirm", response_model=ConfirmMelodyResponse)
async def confirm_melody(project_id: str, version_id: str) -> ConfirmMelodyResponse:
    """The person said "yes, that's my tune". Only now does it become the song's tune."""
    found = await _find_melody(project_id, version_id)
    # Check the content is a real tune BEFORE writing anything, so a bad version cannot leave a
    # half-saved step behind.
    try:
        sketch = MelodySketch(**{**found.content, "confirmed": True})
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="That tune can't be saved right now.") from exc

    # Saying yes twice is the same as saying it once.
    if found.content.get("confirmed"):
        await store.activate_facet_version(project_id, "melody", found.id)
        return ConfirmMelodyResponse(
            version=FacetVersionResponse(**found.model_dump(), is_active=True),
            fingerprint_hints=fingerprint_hints(sketch, sketch.source_audio),
        )

    try:
        confirmed = await store.write_facet(
            project_id,
            "melody",
            sketch.model_dump(mode="json"),
            author="user",
            operation="confirm_melody",
            parent_id=found.id,
            op_params={"confirmed_version_id": found.id},
            label="Confirmed tune",
            activate=True,
        )
    except VersionError as exc:
        raise HTTPException(status_code=400, detail="That tune can't be saved right now.") from exc
    return ConfirmMelodyResponse(
        version=FacetVersionResponse(**confirmed.model_dump(), is_active=True),
        fingerprint_hints=fingerprint_hints(sketch, sketch.source_audio),
    )


@router.post("/melody/{version_id}/reject")
async def reject_melody(project_id: str, version_id: str) -> dict:
    """The person said it is not their tune. Remember that, and leave the song's tune untouched."""
    found = await _find_melody(project_id, version_id)
    await song_db.insert_decision(
        project_id,
        {
            "summary": "Frank's version of the hummed tune",
            "proposed_by": "frank",
            "options": [{"version_id": found.id}],
            "chosen_option": None,
            "user_reaction": "rejected: not their tune",
        },
    )
    return {"ok": True}
