"""
Refine loop routes (spec 08). Mounted under the project ownership check.

POST /projects/{id}/refine                          listen + propose (job)
GET  /projects/{id}/refine/latest                   the newest proposal, for a reload
POST /projects/{id}/refine/{proposal}/preview/{n}   hear one direction (job; writes no version)
POST /projects/{id}/refine/{proposal}/choose/{n}    make it real: a new version, active, and a decision
POST /projects/{id}/refine/{proposal}/disagree      "that's not it": the person is right, the mismatch is kept
POST /projects/{id}/versions/resolve                "give me the second version back"
PATCH /projects/{id}/versions/{layer}/{version}     rename a version
"""
from __future__ import annotations
from app.services.jobs import dispatch

import asyncio
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.db import beat as beat_db
from app.db import jobs as jobs_db
from app.db import mix as mix_db
from app.db import projects as projects_db
from app.db import refine as refine_db
from app.db import song as song_db
from app.models.feel import JobResponse
from app.services.jobs.refine_runner import load_basis, run_preview_job, run_propose_job
from app.services.refine import resolve as resolver
from app.services.refine.models import Direction
from app.services.team import conversation_store as convo

router = APIRouter(prefix="/projects/{project_id}", tags=["refine"])

Layer = Literal["beat", "mix"]


class RefineRequest(BaseModel):
    concern: Optional[str] = Field(default=None, max_length=300)
    room: Literal["beat", "mix", "voice"] = "beat"


class ChooseResponse(BaseModel):
    job_id: str
    kind: str
    message: str


class DisagreeRequest(BaseModel):
    said: str = Field(min_length=1, max_length=300)


class ResolveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    layer: Layer = "beat"
    apply: bool = True


class RenameRequest(BaseModel):
    label: str = Field(min_length=1, max_length=80)


async def _proposal(project_id: str, proposal_id: str) -> dict:
    row = await asyncio.to_thread(refine_db.get_proposal, proposal_id)
    if not row or row["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="I can't find that idea any more. Ask me again?")
    return row


@router.post("/refine", response_model=JobResponse)
async def refine(project_id: str, body: RefineRequest, background: BackgroundTasks) -> JobResponse:
    job = await jobs_db.create_job(project_id, job_type="refine")
    await dispatch.start(background, job, run_propose_job, project_id, body.concern)
    return JobResponse(job_id=job["id"])


@router.get("/refine/latest")
async def latest(project_id: str) -> dict[str, Any]:
    rows = await asyncio.to_thread(refine_db.latest_proposals, project_id, 1)
    return {"proposal": rows[0] if rows else None}


@router.post("/refine/{proposal_id}/preview/{n}", response_model=JobResponse)
async def preview(project_id: str, proposal_id: str, n: int, background: BackgroundTasks) -> JobResponse:
    await _proposal(project_id, proposal_id)
    job = await jobs_db.create_job(project_id, job_type="refine_preview")
    await dispatch.start(background, job, run_preview_job, project_id, proposal_id, n)
    return JobResponse(job_id=job["id"])


def _decision(row: dict, n: int) -> dict:
    """What was offered, why, and what the person chose (requirement 3.1)."""
    directions = row.get("directions") or []
    chosen = directions[n]
    findings = (row.get("findings") or {}).get("findings") or []
    concern = row.get("concern") or "making it better"
    return {
        "summary": (f"Tried one change at a time for “{concern}” and chose “{chosen['title']}”" if row.get("experiment")
                    else f"For “{concern}”, chose “{chosen['title']}”"),
        "rationale": chosen.get("plain"),
        "proposed_by": "producer",
        "options": [{"title": d["title"], "plain": d["plain"], "kind": d["kind"], "actions": d["actions"],
                     "experiment": bool(row.get("experiment"))} for d in directions],
        "evidence": [{"id": f.get("id"), "plain": f.get("plain"), "measurements": f.get("evidence", [])} for f in findings],
        "chosen_option": chosen["title"],
    }


@router.post("/refine/{proposal_id}/choose/{n}", response_model=ChooseResponse)
async def choose(project_id: str, proposal_id: str, n: int, background: BackgroundTasks) -> ChooseResponse:
    from app.routers.mix import apply_actions
    from app.services.jobs.beat_runner import run_operations_job
    from app.services.jobs.mix_runner import run_mix_job

    row = await _proposal(project_id, proposal_id)
    directions = row.get("directions") or []
    if not 0 <= n < len(directions):
        raise HTTPException(status_code=404, detail="That idea isn't on the list.")
    d = Direction(**directions[n])
    basis = await load_basis(project_id)
    if d.kind == "beat":
        if basis["beat_id"] != (row.get("based_on") or {}).get("beat"):
            raise HTTPException(status_code=409, detail="The song has changed since I suggested these. Ask me again and I'll listen fresh.")
        job = await jobs_db.create_job(project_id, job_type="beat_operations")
        await dispatch.start(background, job, run_operations_job, project_id, d.actions)
    else:
        params, _ = apply_actions(basis["mix_params"] or {}, d.actions)
        job = await jobs_db.create_job(project_id, job_type="mix_render")
        await dispatch.start(background, job, run_mix_job, project_id, params, "preview")
    await song_db.insert_decision(project_id, _decision(row, n))
    await asyncio.to_thread(refine_db.set_chosen, proposal_id, n)
    from app.services.taste.signals import record_choice

    await record_choice(project_id, directions[n], [s.name for s in basis["sections"]], bool(row.get("experiment")))
    from app.services.team.identity import refresh_soon

    refresh_soon(project_id)
    message = f"I'm putting “{d.title}” into the song now. Your earlier version stays. Have a listen when it's ready: how does that feel?"
    room = "beat" if d.kind == "beat" else "mix"
    await convo.record(project_id, room, f"Use “{d.title}”", message, [{"type": "refine_choose", "params": {"proposal": proposal_id, "n": n}}])
    return ChooseResponse(job_id=job["id"], kind=d.kind, message=message)


# Words that measure one way but mean different things to different people (requirement 1.3).
MEANINGS = {
    "bigger": "louder, fuller (more going on), or higher",
    "big": "louder, fuller (more going on), or higher",
    "smaller": "quieter, emptier, or lower",
    "heavy": "too slow or too crowded",
    "flat": "it stays in one place, or the singing sounds off",
    "muddy": "the low part is too thick, or everything blurs together",
    "boring": "it repeats too much, or it never builds",
    "busy": "too many parts at once, or one part playing too many notes",
    "thin": "it needs more low end, or more parts",
    "off": "the timing, the notes, or the feeling",
}


def meaning_question(said: str) -> str:
    words = [w.strip(".,!?'\"").lower() for w in said.split()]
    for w in words:
        if w in MEANINGS:
            return f"You're right, your ears decide. When you say “{w}”, do you mean {MEANINGS[w]}?"
    return "You're right, your ears decide. What would feel closer to you?"


@router.post("/refine/{proposal_id}/disagree")
async def disagree(project_id: str, proposal_id: str, body: DisagreeRequest) -> dict[str, str]:
    row = await _proposal(project_id, proposal_id)
    measured = [f.get("plain") for f in ((row.get("findings") or {}).get("findings") or [])]
    await song_db.insert_decision(project_id, {
        "summary": "What I measured didn't match what the person heard",
        "rationale": "The person's ears win; the measurement is kept only as a note.",
        "proposed_by": "listener",
        "evidence": [{"measured": m} for m in measured],
        "user_reaction": body.said,
        "options": [{"kind": "mismatch", "concern": row.get("concern")}],
    })
    from app.services.taste.signals import record_mismatch

    await record_mismatch(project_id, [m for m in measured if m], body.said)
    return {"message": meaning_question(body.said)}


async def _versions(project_id: str, layer: Layer) -> tuple[list[dict], Optional[str]]:
    state = await projects_db.get_project_active_state(project_id) or {}
    if layer == "beat":
        return await beat_db.list_beat_versions(project_id), state.get("active_beat_version_id")
    rows = await mix_db.list_mix_versions(project_id)
    return [{**r, "params": {"changes": [r.get("label") or ""]}} for r in rows], state.get("active_mix_id")


async def go_back(project_id: str, text: str, layer: Layer, apply: bool = True) -> dict[str, Any]:
    """Resolve a plain reference to an earlier version; when it is clear, make it active (a branch, not a delete)."""
    versions, active = await _versions(project_id, layer)
    decisions = [d.model_dump() for d in await song_db.list_decisions(project_id)]
    r = resolver.resolve(text, versions, decisions, active)
    if r.version:
        if apply:
            key = "active_beat_version_id" if layer == "beat" else "active_mix_id"
            await projects_db.update_project_active_state(project_id, {key: r.version["id"]})
        label = r.version.get("label") or "that version"
        return {"status": "resolved", "version": resolver.as_plain(r.version),
                "message": f"I've put {label} back. Everything after it is still kept, so nothing is lost."}
    if r.candidates:
        names = " or ".join(f"“{c.get('label')}”" for c in r.candidates)
        return {"status": "ask", "candidates": [resolver.as_plain(c) for c in r.candidates],
                "message": f"I'm not sure which one you mean: {names}. Have a listen to both and tell me."}
    return {"status": "none", "message": "I couldn't tell which version you mean. You can pick it from the list of versions."}


@router.post("/versions/resolve")
async def resolve_version(project_id: str, body: ResolveRequest) -> dict[str, Any]:
    return await go_back(project_id, body.text, body.layer, body.apply)


@router.patch("/versions/{layer}/{version_id}")
async def rename_version(project_id: str, layer: Layer, version_id: str, body: RenameRequest) -> dict[str, Any]:
    getter = beat_db.get_beat_version if layer == "beat" else mix_db.get_mix_version
    try:
        v = await getter(version_id)
    except Exception:  # noqa: BLE001  .single() raises when the row is missing
        v = None
    if not v or v.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="I can't find that version.")
    if layer == "beat":
        await beat_db.update_beat_version_label(version_id, body.label.strip())
    else:
        await mix_db.update_mix_version_label(version_id, body.label.strip())
    return {"id": version_id, "label": body.label.strip()}
