from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
import httpx

from app.models.voice import (
    VocalTakeResponse,
    UploadTakeResponse,
    CorrectPitchRequest,
    CompRequest,
    HarmonyRequest,
    SetActiveVocalRequest,
    JobResponse,
    VoiceConversationRequest,
    VoiceConversationResponse,
)
from app.models.conversation import ConversationAction
from app.services.llm.groq_client import chat_structured
from app.services.llm.prompts import VOICE_ROOM_SYSTEM, build_voice_room_messages
from app.services.audio.convert import to_wav
from app.services.storage.files import upload_audio
from app.services.jobs.voice_runner import (
    run_pitch_analysis_job,
    run_correction_job,
    run_comp_job,
    run_harmony_job,
)
from app.db import jobs as jobs_db
from app.db import voice as voice_db
from app.db import projects as projects_db
from app.db import feel as feel_db

router = APIRouter(prefix="/projects/{project_id}/voice", tags=["voice"])


def _take_to_response(take: dict) -> VocalTakeResponse:
    return VocalTakeResponse(
        id=take["id"],
        project_id=take["project_id"],
        audio_url=take["audio_url"],
        processed_url=take.get("processed_url"),
        pitch_data=take.get("pitch_data"),
        label=take.get("label"),
        created_at=str(take["created_at"]),
    )


@router.get("/takes", response_model=list[VocalTakeResponse])
async def list_takes(project_id: str) -> list[VocalTakeResponse]:
    takes = await voice_db.list_takes(project_id)
    return [_take_to_response(t) for t in takes]


@router.post("/takes", response_model=UploadTakeResponse)
async def upload_take(
    project_id: str, background: BackgroundTasks, file: UploadFile = File(...)
) -> UploadTakeResponse:
    """
    Upload a vocal take: convert to WAV, store it, and kick off pitch analysis
    as a background job (pyin is too slow to run inline).
    """
    raw = await file.read()
    ext = "webm"
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
    wav = to_wav(raw, input_ext=ext)

    audio_url = upload_audio("vocals", wav, extension="wav", name_prefix="take")

    count = voice_db.count_takes_sync(project_id)
    take = await voice_db.create_take(
        project_id, audio_url, label=f"Take {count + 1}"
    )

    # A freshly recorded take becomes the active vocal, so the rest of the song
    # (Beat preview, Mix assembly) immediately knows a vocal exists. Recording
    # is an intentional act, so making the newest take current matches what the
    # user expects. They can switch to another take later.
    await projects_db.update_project_active_state(
        project_id, {"active_vocal_id": take["id"]}
    )

    # Pitch analysis runs in the background
    job = await jobs_db.create_job(project_id, job_type="pitch_analysis")
    background.add_task(run_pitch_analysis_job, job["id"], take["id"], wav)

    return UploadTakeResponse(
        take=_take_to_response(take), analysis_job_id=job["id"]
    )


@router.delete("/takes/{take_id}")
async def delete_take(project_id: str, take_id: str) -> dict:
    """Soft-delete a take (audio kept — creative work is never destroyed)."""
    await voice_db.soft_delete_take(take_id)
    return {"status": "ok"}


@router.post("/takes/{take_id}/correct", response_model=JobResponse)
async def correct_pitch(
    project_id: str,
    take_id: str,
    body: CorrectPitchRequest,
    background: BackgroundTasks,
) -> JobResponse:
    """Apply pitch correction to a take as a background job."""
    take = await voice_db.get_take(take_id)
    if not take:
        raise HTTPException(status_code=404, detail="Take not found")

    job = await jobs_db.create_job(project_id, job_type="pitch_correction")
    background.add_task(
        run_correction_job, job["id"], project_id, take_id, take["audio_url"], body.mode
    )
    return JobResponse(job_id=job["id"])


@router.post("/comp", response_model=JobResponse)
async def generate_comp(
    project_id: str, body: CompRequest, background: BackgroundTasks
) -> JobResponse:
    """Build a vocal comp from several takes as a background job."""
    if len(body.take_ids) < 2:
        raise HTTPException(
            status_code=400, detail="Comping needs at least two takes."
        )
    take_refs: list[tuple[str, str]] = []
    for tid in body.take_ids:
        take = await voice_db.get_take(tid)
        if take:
            take_refs.append((tid, take["audio_url"]))

    job = await jobs_db.create_job(project_id, job_type="vocal_comp")
    background.add_task(run_comp_job, job["id"], project_id, take_refs)
    return JobResponse(job_id=job["id"])


@router.post("/harmony", response_model=JobResponse)
async def generate_harmony(
    project_id: str, body: HarmonyRequest, background: BackgroundTasks
) -> JobResponse:
    """Generate a harmony layer from a take as a background job."""
    take = await voice_db.get_take(body.take_id)
    if not take:
        raise HTTPException(status_code=404, detail="Take not found")

    # Use the song's mode (if a fingerprint exists) so the harmony fits the key
    mode: str | None = None
    fp = await feel_db.get_latest_fingerprint(project_id)
    if fp and isinstance(fp.get("fingerprint"), dict):
        mode = fp["fingerprint"].get("mode")

    job = await jobs_db.create_job(project_id, job_type="harmony")
    background.add_task(
        run_harmony_job,
        job["id"],
        project_id,
        body.take_id,
        take["audio_url"],
        body.type,
        mode,
    )
    return JobResponse(job_id=job["id"])


@router.post("/active")
async def set_active_vocal(
    project_id: str, body: SetActiveVocalRequest
) -> dict:
    """Set which vocal (a take or a comp) is the active one for the song."""
    key = "active_comp_id" if body.vocal_type == "comp" else "active_vocal_id"
    await projects_db.update_project_active_state(project_id, {key: body.vocal_id})
    return {"status": "ok", key: body.vocal_id}


@router.post("/conversation", response_model=VoiceConversationResponse)
async def voice_conversation(
    project_id: str, body: VoiceConversationRequest
) -> VoiceConversationResponse:
    """Voice Room conversation — the patient vocal producer."""
    take_count = len(await voice_db.list_takes(project_id))
    history = [{"role": m.role, "content": m.content} for m in body.history]
    messages = build_voice_room_messages(take_count, history, body.message)

    try:
        result = chat_structured(VOICE_ROOM_SYSTEM, messages)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Frank stepped away for a second — try again?"
        ) from exc

    allowed = {"correct_pitch", "build_comp", "add_harmony"}
    actions = [
        ConversationAction(type=a["type"], params=a.get("params", {}))
        for a in result.get("actions", [])
        if isinstance(a, dict) and a.get("type") in allowed
    ]
    return VoiceConversationResponse(
        message=result.get("message", ""), actions=actions
    )
