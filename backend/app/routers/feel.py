from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from typing import Optional
import asyncio

from app.models.feel import (
    FeelConversationRequest,
    FeelConversationResponse,
    GenerateTextureRequest,
    SaveFingerprintRequest,
    FingerprintResponse,
    HumAnalysisResponse,
    JobResponse,
)
from app.models.conversation import ConversationAction
from app.services.llm.groq_client import chat_structured
from app.services.llm.prompts import FEEL_LAB_SYSTEM, build_feel_lab_messages
from app.services.audio.convert import to_wav
from app.services.generation.hum import analyze_hum
from app.services.storage.files import upload_audio
from app.services.jobs.runner import run_texture_job
from app.db import jobs as jobs_db
from app.db import feel as feel_db
from app.db import projects as projects_db

router = APIRouter(prefix="/projects/{project_id}/feel", tags=["feel"])

# Feel Lab allows exactly these two action types
_ALLOWED_ACTIONS = {"generate_texture", "approve_direction"}


@router.post("/conversation", response_model=FeelConversationResponse)
async def feel_conversation(
    project_id: str, body: FeelConversationRequest
) -> FeelConversationResponse:
    """Feel Lab conversation — discovers the song's feeling, builds the fingerprint."""
    history = [{"role": m.role, "content": m.content} for m in body.history]
    messages = build_feel_lab_messages(body.fingerprint, history, body.message)

    try:
        result = chat_structured(FEEL_LAB_SYSTEM, messages)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Frank lost the thread for a second — say that again?",
        ) from exc

    actions = [
        ConversationAction(type=a["type"], params=a.get("params", {}))
        for a in result.get("actions", [])
        if isinstance(a, dict) and a.get("type") in _ALLOWED_ACTIONS
    ]

    return FeelConversationResponse(
        message=result.get("message", ""),
        fingerprint_update=result.get("fingerprint_update", {}) or {},
        actions=actions,
    )


@router.post("/texture", response_model=JobResponse)
async def generate_texture(
    project_id: str, body: GenerateTextureRequest, background: BackgroundTasks
) -> JobResponse:
    """
    Start texture generation as a background job. Returns a job_id immediately;
    the frontend polls /jobs/{job_id}/status. Rendering is CPU-bound, so it must
    never run inline in this handler.
    """
    job = await jobs_db.create_job(project_id, job_type="generate_texture")
    background.add_task(
        run_texture_job, job["id"], project_id, body.fingerprint, body.fingerprint_id
    )
    return JobResponse(job_id=job["id"])


@router.post("/hum", response_model=HumAnalysisResponse)
async def analyze_hum_route(
    project_id: str, file: UploadFile = File(...)
) -> HumAnalysisResponse:
    """
    Analyze a hum. Hums are short, so analysis is fast enough to run inline.
    Converts to WAV, stores the hum (reusable later), and returns fingerprint hints.
    """
    raw = await file.read()
    ext = "webm"
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()

    wav = await asyncio.to_thread(to_wav, raw, input_ext=ext)

    # Store the hum audio (reusable by the Beat Room / as a melodic reference)
    audio_url = upload_audio("hums", wav, extension="wav")

    # Analysis is CPU-bound but short; run off the event loop to stay responsive.
    try:
        analysis = await asyncio.to_thread(analyze_hum, wav)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Couldn't quite catch that hum — want to try again?",
        ) from exc

    return HumAnalysisResponse(analysis=analysis, audio_url=audio_url)


@router.get("/fingerprint", response_model=Optional[FingerprintResponse])
async def get_fingerprint(project_id: str) -> Optional[FingerprintResponse]:
    """
    Return the latest fingerprint for a project, or null if none exists.
    Used on Feel Lab entry to support return visits (greet with what was
    established last time instead of starting over).
    """
    latest = await feel_db.get_latest_fingerprint(project_id)
    if not latest:
        return None
    return FingerprintResponse(
        id=latest["id"],
        project_id=latest["project_id"],
        fingerprint=latest["fingerprint"],
        conversation_summary=latest.get("conversation_summary"),
        created_at=str(latest["created_at"]),
    )


@router.post("/fingerprint", response_model=FingerprintResponse)
async def save_fingerprint(
    project_id: str, body: SaveFingerprintRequest
) -> FingerprintResponse:
    """Persist the fingerprint and mark it active for the project."""
    saved = await feel_db.save_fingerprint(
        project_id, body.fingerprint, body.conversation_summary
    )
    await projects_db.update_project_active_state(
        project_id, {"active_fingerprint_id": saved["id"]}
    )
    return FingerprintResponse(
        id=saved["id"],
        project_id=saved["project_id"],
        fingerprint=saved["fingerprint"],
        conversation_summary=saved.get("conversation_summary"),
        created_at=str(saved["created_at"]),
    )
