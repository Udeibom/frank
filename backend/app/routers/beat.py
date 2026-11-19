from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.models.beat import (
    GenerateBeatRequest,
    EditSectionRequest,
    AddStemRequest,
    MuteStemRequest,
    BeatConversationRequest,
    BeatConversationResponse,
    SetActiveBeatRequest,
    UpdateSectionRequest,
    BeatVersionResponse,
    JobResponse,
)
from app.models.conversation import ConversationAction
from app.services.llm.groq_client import chat_structured
from app.services.song.record import system_with_brief
from app.services.team import conversation_store as convo
from app.services.llm.prompts import BEAT_ROOM_SYSTEM, build_beat_room_messages
from app.services.jobs.beat_runner import run_full_beat_job, run_operations_job
from app.services.generation import ops as ops_mod
from app.services.jobs.mix_runner import run_vocal_preview_job
from app.db import jobs as jobs_db
from app.db import beat as beat_db
from app.db import projects as projects_db
from app.db import voice as voice_db

router = APIRouter(prefix="/projects/{project_id}/beat", tags=["beat"])

_ALLOWED_ACTIONS = {
    "generate_full_beat",
    "beat_operations",
    "restore_version",
    "set_section_label",
    "refine",
}


@router.post("/generate", response_model=JobResponse)
async def generate_beat(
    project_id: str, body: GenerateBeatRequest, background: BackgroundTasks
) -> JobResponse:
    """Start full beat generation as a background job."""
    job = await jobs_db.create_job(project_id, job_type="generate_beat")
    background.add_task(run_full_beat_job, job["id"], project_id, body.fingerprint)
    return JobResponse(job_id=job["id"])


class OperationsRequest(BaseModel):
    operations: list[dict[str, Any]] = Field(min_length=1, max_length=8)


async def _start_operations(project_id: str, operations: list[dict], background: BackgroundTasks) -> JobResponse:
    """Validate first (a bad change is refused at once, in plain words), then render in the background."""
    try:
        ops_mod.parse(operations)
    except ops_mod.OpError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job = await jobs_db.create_job(project_id, job_type="beat_operations")
    background.add_task(run_operations_job, job["id"], project_id, operations)
    return JobResponse(job_id=job["id"])


@router.post("/operations", response_model=JobResponse)
async def beat_operations(project_id: str, body: OperationsRequest, background: BackgroundTasks) -> JobResponse:
    """Apply typed edit operations to the active beat as a new version (song-engine spec 04, requirement 5.3)."""
    return await _start_operations(project_id, body.operations, background)


@router.post("/generate-section", response_model=JobResponse)
async def generate_section(project_id: str, body: EditSectionRequest, background: BackgroundTasks) -> JobResponse:
    """Older clients: "start this section fresh" is a new idea for every part of that section."""
    return await _start_operations(project_id, [{"op": "try_another", "section": body.section_index}], background)


@router.post("/add-stem", response_model=JobResponse)
async def add_stem(project_id: str, body: AddStemRequest, background: BackgroundTasks) -> JobResponse:
    """Older clients: add a part to one or all sections."""
    return await _start_operations(project_id, [{"op": "add_part", "part": body.stem_type, "section": body.section_index}], background)


@router.post("/mute-stem", response_model=JobResponse)
async def mute_stem(project_id: str, body: MuteStemRequest, background: BackgroundTasks) -> JobResponse:
    """Older clients: take a part out of one or all sections."""
    return await _start_operations(project_id, [{"op": "remove_part", "part": body.stem_type, "section": body.section_index}], background)


async def _version_reply(project_id: str, room: str, message: str) -> dict | None:
    """
    "Give me the second version back" is resolved here against the real versions, labels, dates and decisions
    (refine-loop requirement 5.2), not left to the model. Clear: the action puts it back. Unclear: both to hear.
    """
    from app.routers.refine import go_back
    from app.services.refine.resolve import is_about_versions

    if not is_about_versions(message):
        return None
    out = await go_back(project_id, message, room, apply=False)  # type: ignore[arg-type]
    if out["status"] == "none":
        return None
    if out["status"] == "resolved":
        kind = "restore_version" if room == "beat" else "restore_mix_version"
        actions = [ConversationAction(type=kind, params={"version_id": out["version"]["id"]})]
    else:
        actions = [ConversationAction(type="compare_versions", params={"layer": room, "candidates": out["candidates"]})]
    reply = await convo.enforce_reply(project_id, room, out["message"])
    await convo.record(project_id, room, message, reply, [a.model_dump() for a in actions])
    return {"message": reply, "actions": actions}


@router.post("/conversation", response_model=BeatConversationResponse)
async def beat_conversation(
    project_id: str, body: BeatConversationRequest
) -> BeatConversationResponse:
    """Beat Room conversation: turns reactions into typed beat edits."""
    history = [{"role": m.role, "content": m.content} for m in body.history]
    if not history:   # after a reload the page has nothing; the stored conversation is the memory
        history = convo.recent_messages(await convo.history(project_id, "beat"))
    early = await _version_reply(project_id, "beat", body.message)
    if early:
        return BeatConversationResponse(**early)
    messages = build_beat_room_messages(body.beat_state, history, body.message)
    system = await convo.with_earlier(project_id, "beat", await system_with_brief(project_id, BEAT_ROOM_SYSTEM, "beat_maker"))
    try:
        result = chat_structured(system, messages)
        from app.services.team.identity import handle_reply

        await handle_reply(project_id, result, body.message, "beat")   # a named artist becomes a feeling (spec 10)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Frank zoned out for a second — say that again?",
        ) from exc
    actions = [
        ConversationAction(type=a["type"], params=a.get("params", {}))
        for a in result.get("actions", [])
        if isinstance(a, dict) and a.get("type") in _ALLOWED_ACTIONS
    ]
    from app.services.refine.resolve import wants_refine

    if wants_refine(body.message) and not any(a.type == "refine" for a in actions):
        # they can't say what is wrong: Frank listens instead of guessing (spec 08, requirement 1.1)
        actions = [ConversationAction(type="refine", params={"concern": body.message[:300]})]
        result["message"] = "I'll listen to the song properly and come back with a few ideas you can hear before choosing."
    # Protect the intention (spec 07, requirement 3.1): a change that fights the feeling they described is said
    # once, with three directions; their answer (or asking again) builds it.
    from app.services.team import intention

    asked_ops = [o for a in actions if a.type == "beat_operations" for o in (a.params.get("operations") or [])]
    say_instead, run_instead = await intention.check(project_id, body.message, asked_ops, list(body.beat_state.get("sections") or []))
    if say_instead:
        actions = [a for a in actions if a.type != "beat_operations"]
        result["message"] = say_instead
    elif run_instead:
        actions = [a for a in actions if a.type != "beat_operations"] + [
            ConversationAction(type="beat_operations", params={"operations": run_instead})]
        result["message"] = "Doing that now. Have a listen when it's ready and tell me how it feels."
    result["message"] = await convo.enforce_reply(project_id, "beat", result.get("message", ""))
    await convo.record(project_id, "beat", body.message, result.get("message", ""), [a.model_dump() for a in actions])
    return BeatConversationResponse(message=result.get("message", ""), actions=actions)


@router.post("/preview-with-vocal", response_model=JobResponse)
async def preview_with_vocal(
    project_id: str, background: BackgroundTasks
) -> JobResponse:
    """
    "Hear it with my vocal" — a quick preview mix of the active beat and the
    active vocal, so the user can judge whether the beat fits their voice. This
    reuses the mix renderer but is a throwaway: it does NOT create a mix version
    or move active_mix_id (voice-to-export-flow requirement 4).
    Only available when a vocal take exists.
    """
    takes = await voice_db.list_takes(project_id)
    has_vocal = any(
        not (t.get("is_harmony") or (t.get("label") or "").lower().startswith("harmony")) for t in takes
    )
    if not has_vocal:
        raise HTTPException(
            status_code=400,
            detail="Record a vocal first, then you can hear it over the beat.",
        )

    # A vocal-forward preview so the voice is clearly audible over the beat
    preview_params = {
        "vocal_gain_db": 1.0,
        "beat_gain_db": -7.0,
        "harmony_enabled": False,
        "vocal_effects": [],
        "beat_effects": [],
        "section_gain_db": {},
    }
    job = await jobs_db.create_job(project_id, job_type="vocal_preview")
    background.add_task(run_vocal_preview_job, job["id"], project_id, preview_params)
    return JobResponse(job_id=job["id"])


@router.get("/versions", response_model=list[BeatVersionResponse])
async def list_beat_versions(project_id: str) -> list[BeatVersionResponse]:
    versions = await beat_db.list_beat_versions(project_id)
    return [
        BeatVersionResponse(
            id=v["id"],
            project_id=v["project_id"],
            render_url=v.get("render_url"),
            label=v.get("label"),
            params=v.get("params") or {},
            created_at=str(v["created_at"]),
        )
        for v in versions
    ]


@router.post("/versions/active")
async def set_active_beat_version(
    project_id: str, body: SetActiveBeatRequest
) -> dict:
    try:
        v = await beat_db.get_beat_version(body.beat_version_id)
    except Exception:  # noqa: BLE001  .single() raises when nothing matches
        v = None
    if not v or v.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="I can't find that version of the beat.")
    await projects_db.update_project_active_state(
        project_id, {"active_beat_version_id": body.beat_version_id}
    )
    return {"status": "ok", "active_beat_version_id": body.beat_version_id}


@router.patch("/sections/{section_index}")
async def update_section(
    project_id: str, section_index: int, body: UpdateSectionRequest
) -> dict:
    """
    Rename a section. This is label-only metadata — the audio doesn't change,
    so it's a safe in-place update of the active version's params.

    Note on reordering: changing section ORDER changes what the audio should
    sound like, so it can't be a metadata-only edit (it would desync the stored
    render from params). Reorder is therefore handled as a re-render that
    produces a new version — not here. (Tracked as a Spec 04 follow-up.)
    """
    if body.label is None:
        return {"status": "ok"}  # nothing to do

    state = await projects_db.get_project_active_state(project_id)
    version_id = state.get("active_beat_version_id") if state else None
    if not version_id:
        raise HTTPException(status_code=404, detail="No active beat")

    version = await beat_db.get_beat_version(version_id)
    params = version.get("params") or {}
    sections = params.get("sections", [])

    for s in sections:
        if s["index"] == section_index:
            s["label"] = body.label
            break

    params["sections"] = sections
    from app.db.client import get_supabase

    get_supabase().table("beat_versions").update({"params": params}).eq(
        "id", version_id
    ).execute()
    return {"status": "ok"}
