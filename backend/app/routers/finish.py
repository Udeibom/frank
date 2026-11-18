"""
Finishing routes (finish-and-intent spec 11). Mounted under the project ownership check.

GET  /projects/{id}/finish/intent        the person's words and the question to ask before the first export
POST /projects/{id}/finish/intent        "Yes, that's it" / "Not yet" (+ what they'd say)
POST /projects/{id}/finish/surprise      build Frank's one idea (job), once per song
GET  /projects/{id}/finish/surprise      whether it was offered already
POST /projects/{id}/finish/parts         separate the beat into its parts for mixing (job)
POST /projects/{id}/finish/parts.zip     "Download separate parts" (job; the result holds the zip's link)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.db import jobs as jobs_db
from app.db import projects as projects_db
from app.models.feel import JobResponse
from app.services.finish import intent as intent_svc
from app.services.finish import surprise as surprise_svc
from app.services.finish.parts_zip import run_parts_zip_job

router = APIRouter(prefix="/projects/{project_id}/finish", tags=["finish"])


class IntentAnswer(BaseModel):
    yes: bool
    said: Optional[str] = Field(default=None, max_length=300)


@router.get("/intent")
async def get_intent(project_id: str) -> dict:
    return await intent_svc.state(project_id)


@router.post("/intent")
async def answer_intent(project_id: str, body: IntentAnswer) -> dict:
    return await intent_svc.answer(project_id, body.yes, body.said)


@router.get("/identity")
async def identity_view(project_id: str) -> dict:
    """What makes this song theirs, in plain words (creative-director spec 10, requirement 1.2)."""
    from app.services.song import record as song_record

    content = await song_record.active_facet(project_id, "identity_brief") or {}
    return {"identity": content or None}


@router.post("/identity")
async def identity_refresh(project_id: str) -> dict:
    from app.services.team.identity import refresh

    content = await refresh(project_id, force=True)
    return {"identity": content}


@router.get("/surprise")
async def surprise_state(project_id: str) -> dict:
    return {"offered": await surprise_svc.offered_before(project_id)}


@router.post("/surprise", response_model=JobResponse)
async def make_surprise(project_id: str, background: BackgroundTasks) -> JobResponse:
    if await surprise_svc.offered_before(project_id):
        raise HTTPException(status_code=409, detail="I've already shown you my one idea for this song.")
    job = await jobs_db.create_job(project_id, job_type="surprise")
    background.add_task(surprise_svc.run_surprise_job, job["id"], project_id)
    return JobResponse(job_id=job["id"])


@router.get("/parts")
async def list_parts(project_id: str) -> dict:
    """The parts the music plays (plain names on the page) and whether they are separated already."""
    import asyncio

    from app.routers.mix import _song_shape
    from app.services.jobs.beat_runner import cached_parts

    state = await projects_db.get_project_active_state(project_id) or {}
    shape = await _song_shape(project_id)
    bvid = state.get("active_beat_version_id")
    ready = bool(bvid) and bool(await asyncio.to_thread(cached_parts, project_id, bvid))
    return {"parts": shape.get("parts", []), "sections": shape.get("sections", []), "ready": ready}


@router.post("/surprise/skip")
async def skip_surprise(project_id: str) -> dict:
    """"No thanks": the one offer is used up, so Frank never asks again for this song."""
    from app.db import song as song_db

    if not await surprise_svc.offered_before(project_id):
        await song_db.insert_decision(project_id, {"summary": "Skipped Frank's surprise idea", "proposed_by": "frank",
                                                   "options": [{"kind": "surprise", "skipped": True}], "chosen_option": "skip"})
    return {"status": "ok"}


@router.post("/parts", response_model=JobResponse)
async def make_parts(project_id: str, background: BackgroundTasks) -> JobResponse:
    from app.services.jobs.beat_runner import run_parts_job

    state = await projects_db.get_project_active_state(project_id) or {}
    if not state.get("active_beat_version_id"):
        raise HTTPException(status_code=409, detail="There's no beat to separate yet.")
    job = await jobs_db.create_job(project_id, job_type="beat_parts")
    background.add_task(run_parts_job, job["id"], project_id, state["active_beat_version_id"])
    return JobResponse(job_id=job["id"])


@router.post("/parts.zip", response_model=JobResponse)
async def parts_zip(project_id: str, background: BackgroundTasks) -> JobResponse:
    job = await jobs_db.create_job(project_id, job_type="parts_zip")
    background.add_task(run_parts_zip_job, job["id"], project_id)
    return JobResponse(job_id=job["id"])
