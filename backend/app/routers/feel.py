from app.services.jobs import dispatch
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
    TextureResponse,
    TextureWaveformResponse,
)
from app.models.conversation import ConversationAction
from app.services.llm.groq_client import chat_structured
from app.services.song.record import system_with_brief
from app.services.team import conversation_store as convo
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
    if not history:   # after a reload the page has nothing; the stored conversation is the memory
        history = convo.recent_messages(await convo.history(project_id, "feel"))
    messages = build_feel_lab_messages(body.fingerprint, history, body.message)

    system = await convo.with_earlier(project_id, "feel", await system_with_brief(project_id, FEEL_LAB_SYSTEM, "producer"))
    try:
        result = chat_structured(system, messages)
        from app.services.team.identity import handle_reply

        await handle_reply(project_id, result, body.message, "feel")   # a named artist becomes a feeling (spec 10)
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

    update = result.get("fingerprint_update", {}) or {}
    from app.services.generation import texture as texture_svc

    if texture_svc.wants_different(body.message):
        # "Try something different" really is different (core-path spec 15, 4.1): another sound family, the other
        # side of the energy, another way of moving, and a new direction is played.
        update = {**update, **texture_svc.contrast({**(body.fingerprint or {}), **update})}
        if not any(a.type == "generate_texture" for a in actions):
            actions.append(ConversationAction(type="generate_texture", params={}))
    result["fingerprint_update"] = update
    result["message"] = await convo.enforce_reply(project_id, "feel", result.get("message", ""))
    await convo.record(project_id, "feel", body.message, result.get("message", ""), [a.model_dump() for a in actions])
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
    await dispatch.start(background, job, run_texture_job, project_id, body.fingerprint, body.fingerprint_id
    )
    return JobResponse(job_id=job["id"])


@router.get("/textures", response_model=list[TextureResponse])
async def list_textures(project_id: str) -> list[TextureResponse]:
    """Every direction Frank has played for this song, oldest first, so the Feeling room can show them again."""
    rows = await feel_db.list_textures(project_id)
    return [
        TextureResponse(
            id=r["id"], audio_url=r["audio_url"], approved=bool(r.get("approved")), created_at=str(r["created_at"])
        )
        for r in rows
    ]


@router.get("/textures/{texture_id}/waveform", response_model=TextureWaveformResponse)
async def texture_waveform(project_id: str, texture_id: str) -> TextureWaveformResponse:
    """The shape of one texture's sound (the browser never analyses audio, so it asks)."""
    from app.services.audio import shape

    row = await feel_db.get_texture(project_id, texture_id)
    if not row:
        raise HTTPException(status_code=404, detail="That sound isn't part of this song.")
    points = await asyncio.to_thread(shape.shape_of_texture, texture_id, row["audio_url"])
    return TextureWaveformResponse(texture_id=texture_id, waveform=points)


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
    from app.services.taste.signals import record_texture

    await record_texture(project_id, body.fingerprint or {}, approved=True)     # "yes, that direction" (spec 09)
    return FingerprintResponse(
        id=saved["id"],
        project_id=saved["project_id"],
        fingerprint=saved["fingerprint"],
        conversation_summary=saved.get("conversation_summary"),
        created_at=str(saved["created_at"]),
    )



# ── directions ranked by the person's own words (frankenstein spec 14, requirement 2.1) ─────────────────────

async def _remember_liked_sound(project_id: str, texture_id: Optional[str]) -> None:
    """The texture they said yes to is kept as taste-by-sound, for their next songs. Best-effort."""
    if not texture_id:
        return
    try:
        from app.services.memory import sounds
        from app.services.taste.store import owner_of

        v = await asyncio.to_thread(sounds.embedding_of, "texture", texture_id)
        if v:
            owner = await asyncio.to_thread(owner_of, project_id)
            await asyncio.to_thread(sounds.remember, "taste", f"texture:{texture_id}", v, owner, project_id, {"texture_id": texture_id})
    except Exception:  # noqa: BLE001
        pass


@router.get("/ranked")
async def ranked_directions(project_id: str) -> dict:
    """Which directions sound closest to the person's words (and to sounds they liked before). Empty when the
    ears are asleep or nothing has been heard yet; the room then keeps its own order."""
    from app.db.client import get_supabase
    from app.services.memory import sounds
    from app.services.song import record as song_record
    from app.services.taste.store import owner_of

    rows = await asyncio.to_thread(lambda: get_supabase().table("sound_embeddings").select("ref_id,embedding")
                                   .eq("project_id", project_id).eq("kind", "texture").execute().data or [])
    if not rows:
        return {"ranked": [], "words": []}
    feeling = await song_record.active_facet(project_id, "feeling") or {}
    intent = await song_record.active_facet(project_id, "intent") or {}
    words = [str(w) for w in feeling.get("words", []) + feeling.get("loved_qualities", [])][:10]
    if intent.get("text"):
        words.append(str(intent["text"])[:200])
    owner = await asyncio.to_thread(owner_of, project_id)
    liked_rows = await asyncio.to_thread(lambda: get_supabase().table("sound_embeddings").select("embedding")
                                         .eq("user_id", owner).eq("kind", "taste").order("created_at", desc=True)
                                         .limit(10).execute().data or []) if owner else []
    parse = lambda raw: [float(x) for x in raw.strip("[]").split(",")] if isinstance(raw, str) else list(raw)  # noqa: E731
    items = [(r["ref_id"], parse(r["embedding"])) for r in rows]
    liked = [parse(r["embedding"]) for r in liked_rows] or None
    ranked = await asyncio.to_thread(sounds.rank_by_words, words, items, liked)
    return {"ranked": [{"texture_id": t, "score": s} for t, s in ranked], "words": words,
            "note": "Directions that sound closest to what you've said come first." if words else None}
