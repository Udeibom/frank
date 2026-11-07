from fastapi import APIRouter, HTTPException, BackgroundTasks

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
from app.services.llm.prompts import BEAT_ROOM_SYSTEM, build_beat_room_messages
from app.services.jobs.beat_runner import (
    run_full_beat_job,
    run_edit_section_job,
    run_add_stem_job,
    run_mute_stem_job,
)
from app.db import jobs as jobs_db
from app.db import beat as beat_db
from app.db import projects as projects_db

router = APIRouter(prefix="/projects/{project_id}/beat", tags=["beat"])

_ALLOWED_ACTIONS = {
    "generate_full_beat",
    "edit_section",
    "add_stem",
    "mute_stem",
    "restore_version",
    "set_section_label",
}


@router.post("/generate", response_model=JobResponse)
async def generate_beat(
    project_id: str, body: GenerateBeatRequest, background: BackgroundTasks
) -> JobResponse:
    """Start full beat generation as a background job."""
    job = await jobs_db.create_job(project_id, job_type="generate_beat")
    background.add_task(run_full_beat_job, job["id"], project_id, body.fingerprint)
    return JobResponse(job_id=job["id"])


@router.post("/generate-section", response_model=JobResponse)
async def generate_section(
    project_id: str, body: EditSectionRequest, background: BackgroundTasks
) -> JobResponse:
    """Re-render a single section (as a new version) in the background."""
    job = await jobs_db.create_job(project_id, job_type="edit_section")
    background.add_task(
        run_edit_section_job,
        job["id"],
        project_id,
        body.section_index,
        body.instruction,
    )
    return JobResponse(job_id=job["id"])


@router.post("/add-stem", response_model=JobResponse)
async def add_stem(
    project_id: str, body: AddStemRequest, background: BackgroundTasks
) -> JobResponse:
    """Add a layer to one or all sections (as a new version) in the background."""
    job = await jobs_db.create_job(project_id, job_type="add_stem")
    background.add_task(
        run_add_stem_job,
        job["id"],
        project_id,
        body.stem_type,
        body.section_index,
    )
    return JobResponse(job_id=job["id"])


@router.post("/mute-stem", response_model=JobResponse)
async def mute_stem(
    project_id: str, body: MuteStemRequest, background: BackgroundTasks
) -> JobResponse:
    """Remove a layer from one or all sections (as a new version)."""
    job = await jobs_db.create_job(project_id, job_type="mute_stem")
    background.add_task(
        run_mute_stem_job, job["id"], project_id, body.stem_type, body.section_index
    )
    return JobResponse(job_id=job["id"])


@router.post("/conversation", response_model=BeatConversationResponse)
async def beat_conversation(
    project_id: str, body: BeatConversationRequest
) -> BeatConversationResponse:
    """Beat Room conversation — turns reactions into beat edits."""
    history = [{"role": m.role, "content": m.content} for m in body.history]
    messages = build_beat_room_messages(body.beat_state, history, body.message)

    try:
        result = chat_structured(BEAT_ROOM_SYSTEM, messages)
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
    return BeatConversationResponse(
        message=result.get("message", ""), actions=actions
    )


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
