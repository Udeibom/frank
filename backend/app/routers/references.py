"""
Songs the person points at (frankenstein spec 14, requirement 6).

- POST /references/upload     their own file (they confirm they may use it); analysed in memory, never stored
- GET  /references/jamendo    search Creative Commons music by feeling
- POST /references/jamendo    use one Jamendo track
- POST /references/named      "Nights by Frank Ocean": looked up and researched into feeling words only
- GET  /references            what Frank heard in each
The name of a song or artist is kept for the person to see, never put in a prompt (founder's rule).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.db import jobs as jobs_db
from app.db.client import get_supabase
from app.models.feel import JobResponse
from app.services.jobs import reference_runner

log = logging.getLogger("frank.references")
router = APIRouter(prefix="/projects/{project_id}/references", tags=["references"])

MAX_UPLOAD = 50 * 1024 * 1024
AUDIO_EXT = {"mp3", "wav", "m4a", "aac", "ogg", "oga", "opus", "flac", "webm"}


@router.get("")
async def list_references(project_id: str) -> dict:
    rows = (get_supabase().table("song_references").select("*").eq("project_id", project_id)
            .order("created_at", desc=True).limit(20).execute().data) or []
    return {"references": rows}


@router.post("/upload", response_model=JobResponse)
async def upload_reference(project_id: str, background: BackgroundTasks, file: UploadFile = File(...),
                           rights_confirmed: bool = Form(False)) -> JobResponse:
    if not rights_confirmed:
        raise HTTPException(status_code=400, detail="Only use a song you're allowed to use, like one you own or made. Tick the box to say so.")
    ext = (file.filename or "song.mp3").rsplit(".", 1)[-1].lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(status_code=415, detail="That doesn't look like a song file. An mp3 or wav works best.")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="That file is too big for me. A song under 50 MB works.")
    title = (file.filename or "Your song").rsplit(".", 1)[0][:120]
    job = await jobs_db.create_job(project_id, "reference")
    background.add_task(reference_runner.run_reference_job, job["id"], project_id, "upload", data, ext,
                        {"title": title, "artist": None, "license": "used with your permission", "attribution": None})
    return JobResponse(job_id=job["id"])


@router.get("/jamendo")
async def search_jamendo(project_id: str, q: str) -> dict:
    from app.services.reference import jamendo

    if not jamendo.available():
        return {"tracks": [], "message": "Picking from free music isn't switched on yet."}
    try:
        return {"tracks": await asyncio.to_thread(jamendo.search, q)}
    except Exception:  # noqa: BLE001
        return {"tracks": [], "message": "I couldn't reach the free music library just now. Want to try again?"}


class JamendoPick(BaseModel):
    track_id: str = Field(min_length=1, max_length=20)


@router.post("/jamendo", response_model=JobResponse)
async def use_jamendo(project_id: str, body: JamendoPick, background: BackgroundTasks) -> JobResponse:
    from app.services.reference import jamendo

    if not jamendo.available():
        raise HTTPException(status_code=503, detail="Picking from free music isn't switched on yet.")
    track = await asyncio.to_thread(jamendo.get, body.track_id)
    if not track:
        raise HTTPException(status_code=404, detail="I couldn't find that song any more.")
    job = await jobs_db.create_job(project_id, "reference")
    background.add_task(reference_runner.run_reference_job, job["id"], project_id, "jamendo", None, "mp3",
                        {"title": track["title"], "artist": track["artist"], "license": track["license"],
                         "attribution": track["attribution"], "external_id": track["id"], "track": track})
    return JobResponse(job_id=job["id"])


class NamedReference(BaseModel):
    text: str = Field(min_length=2, max_length=200)


@router.post("/named", response_model=JobResponse)
async def named_reference(project_id: str, body: NamedReference, background: BackgroundTasks) -> JobResponse:
    job = await jobs_db.create_job(project_id, "reference")
    background.add_task(reference_runner.run_named_job, job["id"], project_id, body.text)
    return JobResponse(job_id=job["id"])


@router.post("/{reference_id}/forget")
async def forget_reference(project_id: str, reference_id: str) -> dict:
    get_supabase().table("song_references").update({"active": False}).eq("id", reference_id).eq("project_id", project_id).execute()
    return {"ok": True}
