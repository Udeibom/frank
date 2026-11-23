from app.services.jobs import dispatch
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.auth import get_current_user_id
from app.models.voice import (
    AlignRequest,
    VocalTakeResponse,
    UploadTakeResponse,
    CorrectPitchRequest,
    CompRequest,
    HarmonyRequest,
    SetActiveVocalRequest,
    SwapRequest,
    JobResponse,
    VoiceConversationRequest,
    VoiceConversationResponse,
)
from app.models.conversation import ConversationAction
from app.services.llm.groq_client import chat_structured
from app.services.song.record import system_with_brief
from app.services.team import conversation_store as convo
from app.services.llm.prompts import VOICE_ROOM_SYSTEM, build_voice_room_messages
from app.services.audio.convert import to_wav
from app.services.storage.files import upload_audio
from app.services.jobs import voice_runner as vr
from app.db import jobs as jobs_db
from app.db import voice as voice_db
from app.db import projects as projects_db

router = APIRouter(prefix="/projects/{project_id}/voice", tags=["voice"])

MAX_UPLOAD = 50 * 1024 * 1024


def _take_to_response(take: dict) -> VocalTakeResponse:
    return VocalTakeResponse(
        id=take["id"],
        project_id=take["project_id"],
        audio_url=take["audio_url"],
        processed_url=take.get("processed_url"),
        pitch_data=take.get("pitch_data"),
        label=take.get("label"),
        created_at=str(take["created_at"]),
        kind=take.get("kind") or "take",
        parent_take_id=take.get("parent_take_id"),
        is_harmony=bool(take.get("is_harmony")),
        params=take.get("params") or {},
        facts=take.get("facts") or {},
        words=take.get("words"),
    )


async def _owned_take(project_id: str, take_id: str) -> dict:
    """A take of THIS song (a take id from another song is treated as missing)."""
    try:
        take = await voice_db.get_take(take_id)
    except Exception:  # noqa: BLE001  .single() raises when nothing matches
        take = None
    if not take or take.get("project_id") != project_id or take.get("deleted"):
        raise HTTPException(status_code=404, detail="I can't find that take.")
    return take


async def _job(project_id: str, kind: str, background: BackgroundTasks, fn, *args) -> JobResponse:
    job = await jobs_db.create_job(project_id, job_type=kind)
    await dispatch.start(background, job, fn, *args)
    return JobResponse(job_id=job["id"])


@router.get("/takes", response_model=list[VocalTakeResponse])
async def list_takes(project_id: str) -> list[VocalTakeResponse]:
    takes = await voice_db.list_takes(project_id)
    return [_take_to_response(t) for t in takes]


def _place_sync(wav: bytes, lead_in_s: float, delay_s: float, beat_offset_s: float) -> bytes:
    """Put the take in song time (sing-it requirement 3.2)."""
    from app.services.audio import align

    mono = vr._read_mono(wav)
    return vr._wav(align.place_in_song(mono, vr.pitch_svc.SR, lead_in_s, delay_s, beat_offset_s))


@router.post("/takes", response_model=UploadTakeResponse)
async def upload_take(
    project_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    beat_version_id: Optional[str] = Form(default=None),
    beat_offset_s: Optional[float] = Form(default=None, ge=0, le=900),
    lead_in_s: Optional[float] = Form(default=None, ge=-2, le=10),
    headphones: Optional[bool] = Form(default=None),
    user_id: str = Depends(get_current_user_id),
) -> UploadTakeResponse:
    """
    Upload a vocal take. When it was sung over the beat, the browser says which beat, where in the song the beat
    started and how long after the recording began it started; the take is then placed in song time, corrected by
    this person's measured device delay. Then a background job reads the pitch line and the recording engineer
    checks the recording.
    """
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="That recording is too long for me to take in one go.")
    ext = "webm"
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        ext = ext if ext.isalnum() and len(ext) <= 5 else "webm"
    wav = await asyncio.to_thread(to_wav, raw, input_ext=ext)

    params: dict = {}
    if beat_version_id and lead_in_s is not None:
        delay_ms = await asyncio.to_thread(voice_db.get_input_delay_ms, user_id)
        raw_url = upload_audio("vocals", wav, extension="wav", name_prefix="recorded")
        wav = await asyncio.to_thread(_place_sync, wav, lead_in_s, (delay_ms or 0.0) / 1000.0, beat_offset_s or 0.0)
        params = {"beat_version_id": beat_version_id, "beat_offset_s": beat_offset_s or 0.0, "lead_in_s": lead_in_s,
                  "delay_ms": delay_ms, "delay_checked": delay_ms is not None, "headphones": headphones,
                  "recorded_url": raw_url, "song_time": True}
    elif headphones is not None:
        params = {"headphones": headphones}

    audio_url = upload_audio("vocals", wav, extension="wav", name_prefix="take")
    count = voice_db.count_takes_sync(project_id)
    take = await voice_db.create_take(project_id, audio_url, label=f"Recording {count + 1}", params=params)

    # A freshly recorded take becomes the active vocal (cross-room rule, voice-to-export-flow R2): the most
    # recently chosen vocal wins, so recording clears any older comp pointer. The comp itself is kept.
    await projects_db.update_project_active_state(project_id, {"active_vocal_id": take["id"], "active_comp_id": None})

    job = await jobs_db.create_job(project_id, job_type="pitch_analysis")
    await dispatch.start(background, job, vr.run_after_take_job, project_id, take, wav)
    return UploadTakeResponse(take=_take_to_response(take), analysis_job_id=job["id"])


@router.post("/delay-check")
async def delay_check(
    project_id: str,
    file: UploadFile = File(...),
    click_times: str = Form(...),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    The one-time timing check (requirement 3.1): four clicks were played at `click_times` (seconds into the
    recording) and the person clapped along. The delay is stored for this person and used for every new take.
    """
    try:
        clicks = [float(x) for x in json.loads(click_times)][:16]
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="I didn't get the click times.") from exc
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="That check was longer than it needs to be.")
    ext = (file.filename or "check.webm").rsplit(".", 1)[-1].lower()
    wav = await asyncio.to_thread(to_wav, raw, input_ext=ext if ext.isalnum() and len(ext) <= 5 else "webm")
    out = await asyncio.to_thread(vr._delay_sync, wav, clicks)
    if out["delay_ms"] is None or out["confidence"] < 0.3:
        return {"ok": False, "message": "I couldn't hear the claps clearly. Try again a little closer to the mic, clapping right on each click."}
    await asyncio.to_thread(voice_db.set_input_delay_ms, user_id, out["delay_ms"])
    return {"ok": True, "delay_ms": out["delay_ms"],
            "message": "Got it. I'll line up every take you record on this computer from now on."}


@router.get("/settings")
async def voice_settings(project_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    return {"input_delay_ms": await asyncio.to_thread(voice_db.get_input_delay_ms, user_id)}


@router.delete("/takes/{take_id}")
async def delete_take(project_id: str, take_id: str) -> dict:
    """Soft-delete a take (audio kept — creative work is never destroyed)."""
    await _owned_take(project_id, take_id)
    await voice_db.soft_delete_take(take_id)
    return {"status": "ok"}


@router.post("/takes/{take_id}/correct", response_model=JobResponse)
async def correct_pitch(project_id: str, take_id: str, body: CorrectPitchRequest, background: BackgroundTasks) -> JobResponse:
    """Tune a take toward the song's own notes (requirement 2). Makes a new version; the take is kept."""
    take = await _owned_take(project_id, take_id)
    return await _job(project_id, "pitch_correction", background, vr.run_tune_job, project_id, take, body.mode)


@router.post("/takes/{take_id}/align", response_model=JobResponse)
async def align_take(project_id: str, take_id: str, body: AlignRequest, background: BackgroundTasks) -> JobResponse:
    """Tighten the timing: lines that start early or late move toward the beat (requirement 3.3)."""
    take = await _owned_take(project_id, take_id)
    return await _job(project_id, "vocal_align", background, vr.run_align_job, project_id, take, body.mode)


@router.post("/takes/{take_id}/remove-bleed", response_model=JobResponse)
async def remove_bleed(project_id: str, take_id: str, background: BackgroundTasks) -> JobResponse:
    """Take the beat out of a take recorded without headphones (requirement 4)."""
    take = await _owned_take(project_id, take_id)
    return await _job(project_id, "vocal_bleed", background, vr.run_bleed_job, project_id, take)


@router.post("/takes/{take_id}/use-as-melody", response_model=JobResponse)
async def use_as_melody(project_id: str, take_id: str, background: BackgroundTasks) -> JobResponse:
    """Read the tune from a take, the same way as a hum: played back, then confirmed (requirement 8)."""
    from app.services.jobs.intake_runner import run_hum_intake_job
    from app.services.storage.signing import fetch_audio_bytes

    take = await _owned_take(project_id, take_id)
    audio = await asyncio.to_thread(fetch_audio_bytes, take["audio_url"], 30)
    ext = take["audio_url"].rsplit("?", 1)[0].rsplit(".", 1)[-1].lower()
    return await _job(project_id, "hum_intake", background, run_hum_intake_job, project_id, audio, ext if ext in ("wav", "mp3") else "wav")


@router.post("/guide", response_model=JobResponse)
async def make_guide(project_id: str, background: BackgroundTasks) -> JobResponse:
    """The tune on a voice-like sound, to sing along with (requirement 1). Made once per beat version."""
    state = await projects_db.get_project_active_state(project_id) or {}
    bvid = state.get("active_beat_version_id")
    if not bvid:
        raise HTTPException(status_code=409, detail="There's no beat yet, so there's no tune to sing along with. Sing it your way!")
    return await _job(project_id, "vocal_guide", background, vr.run_guide_job, project_id, bvid)


async def _take_refs(project_id: str, take_ids: list[str]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for tid in dict.fromkeys(take_ids):
        take = await _owned_take(project_id, tid)
        refs.append((tid, take["audio_url"]))
    return refs


@router.post("/comp", response_model=JobResponse)
async def generate_comp(project_id: str, body: CompRequest, background: BackgroundTasks) -> JobResponse:
    """The best of several takes, phrase by phrase (requirement 5)."""
    if len(set(body.take_ids)) < 2:
        raise HTTPException(status_code=400, detail="Comping needs at least two takes.")
    refs = await _take_refs(project_id, body.take_ids)
    return await _job(project_id, "vocal_comp", background, vr.run_phrase_comp_job, project_id, refs)


@router.get("/comp/active")
async def active_comp(project_id: str) -> dict:
    """The comp in use (or the newest), with which take each line came from."""
    state = await projects_db.get_project_active_state(project_id) or {}
    comp = await voice_db.get_comp(state["active_comp_id"]) if state.get("active_comp_id") else await voice_db.get_latest_comp(project_id)
    if not comp or comp.get("project_id") != project_id:
        return {"comp": None}
    return {"comp": {"id": comp["id"], "audio_url": comp["audio_url"], "segments": comp.get("segments") or [],
                     "active": comp["id"] == state.get("active_comp_id"), "created_at": str(comp.get("created_at"))}}


@router.post("/comp/{comp_id}/swap", response_model=JobResponse)
async def swap_phrase(project_id: str, comp_id: str, body: SwapRequest, background: BackgroundTasks) -> JobResponse:
    """Use the same line from another take. Makes a NEW comp; the earlier one is kept."""
    comp = await voice_db.get_comp(comp_id)
    if not comp or comp.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="I can't find that version.")
    ids = list(dict.fromkeys([s["take_id"] for s in comp.get("segments") or []] + [body.take_id]))
    refs = await _take_refs(project_id, ids)
    return await _job(project_id, "vocal_comp", background, vr.run_swap_job, project_id, comp, refs, body.phrase_index, body.take_id)


@router.post("/harmony", response_model=JobResponse)
async def generate_harmony(project_id: str, body: HarmonyRequest, background: BackgroundTasks) -> JobResponse:
    """A harmony from the person's own voice that follows the chords, in the sections they choose (requirement 6)."""
    take = await _owned_take(project_id, body.take_id)
    return await _job(project_id, "harmony", background, vr.run_chord_harmony_job, project_id, take, body.type, body.sections)


@router.post("/active")
async def set_active_vocal(
    project_id: str, body: SetActiveVocalRequest
) -> dict:
    """Set which vocal (a take or a comp) is the active one for the song."""
    if body.vocal_type == "comp":
        comp = await voice_db.get_comp(body.vocal_id)
        if not comp or comp.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail="I can't find that version.")
    else:
        await _owned_take(project_id, body.vocal_id)
    from app.services.team.identity import refresh_soon

    refresh_soon(project_id)                 # a take kept is a major choice (spec 10)
    key = "active_comp_id" if body.vocal_type == "comp" else "active_vocal_id"
    updates: dict = {key: body.vocal_id}
    if body.vocal_type != "comp":
        # Last chosen wins: picking a take overrides any active comp.
        updates["active_comp_id"] = None
    await projects_db.update_project_active_state(project_id, updates)
    return {"status": "ok", key: body.vocal_id}


async def _take_facts(project_id: str, takes: list[dict]) -> list[dict]:
    from app.services.audio import song_notes as sn
    from app.services.jobs.voice_runner import section_phrase

    if not takes:
        return []
    try:
        state = await projects_db.get_project_active_state(project_id) or {}
    except Exception:  # noqa: BLE001  facts are a help; the conversation works without them
        state = {}
    song = await sn.for_project(project_id)
    out = []
    for t in takes:
        f = t.get("facts") or {}
        out.append({"id": t["id"], "label": t.get("label") or "Take", "kind": t.get("kind") or "take",
                    "active": t["id"] == state.get("active_vocal_id"), "seconds": f.get("seconds"),
                    "sections": [section_phrase(song, i).removeprefix("the ") for i in (f.get("sections") or [])],
                    "on_the_notes": f.get("on_the_notes"), "sits_ms": f.get("sits_ms"),
                    "bleed": (f.get("bleed") or 0) > 0.12 and t.get("kind") != "cleaned"})
    return out


@router.post("/conversation", response_model=VoiceConversationResponse)
async def voice_conversation(
    project_id: str, body: VoiceConversationRequest
) -> VoiceConversationResponse:
    """Voice Room conversation — the patient vocal producer."""
    takes = [t for t in await voice_db.list_takes(project_id) if not t.get("is_harmony")]
    take_count = len([t for t in takes if (t.get("kind") or "take") == "take"])
    take_facts = await _take_facts(project_id, takes)
    history = [{"role": m.role, "content": m.content} for m in body.history]
    if not history:   # after a reload the page has nothing; the stored conversation is the memory
        history = convo.recent_messages(await convo.history(project_id, "voice"))
    messages = build_voice_room_messages(take_count, history, body.message, take_facts)

    system = await convo.with_earlier(project_id, "voice", await system_with_brief(project_id, VOICE_ROOM_SYSTEM, "vocal_producer"))
    try:
        result = chat_structured(system, messages)
        from app.services.team.identity import handle_reply

        await handle_reply(project_id, result, body.message, "voice")   # a named artist becomes a feeling (spec 10)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Frank stepped away for a second — try again?"
        ) from exc

    allowed = {"correct_pitch", "line_up", "remove_bleed", "build_comp", "add_harmony", "guide", "use_as_melody"}
    actions = [
        ConversationAction(type=a["type"], params=a.get("params", {}))
        for a in result.get("actions", [])
        if isinstance(a, dict) and a.get("type") in allowed
    ]
    result["message"] = await convo.enforce_reply(project_id, "voice", result.get("message", ""))
    await convo.record(project_id, "voice", body.message, result.get("message", ""), [a.model_dump() for a in actions])
    return VoiceConversationResponse(message=result.get("message", ""), actions=actions)


# ── organs (frankenstein spec 14, requirements 4.1-4.3) ────────────────────���─────────────────────────────

from pydantic import BaseModel as _BaseModel  # noqa: E402


class InstrumentRequest(_BaseModel):
    instrument: str = "violin"


@router.post("/takes/{take_id}/quiet", response_model=JobResponse)
async def quiet_take(project_id: str, take_id: str, background: BackgroundTasks) -> JobResponse:
    """Take the room noise out (fans, hiss, traffic). A new take; the original is kept."""
    take = await _owned_take(project_id, take_id)
    return await _job(project_id, "vocal_quiet", background, vr.run_quiet_job, project_id, take)


@router.post("/takes/{take_id}/instrument", response_model=JobResponse)
async def take_as_instrument(project_id: str, take_id: str, body: InstrumentRequest, background: BackgroundTasks) -> JobResponse:
    """Play this hum or line as an instrument, keeping the way they sang it."""
    if body.instrument not in vr.INSTRUMENT_WORDS:
        raise HTTPException(status_code=400, detail="I can play it as a violin, flute, soft flute, trumpet or saxophone.")
    take = await _owned_take(project_id, take_id)
    return await _job(project_id, "vocal_instrument", background, vr.run_instrument_job, project_id, take, body.instrument)


@router.post("/guide/sung", response_model=JobResponse)
async def sung_guide(project_id: str, background: BackgroundTasks) -> JobResponse:
    """A guide voice that sings their words on the tune, so they can hear how a line goes."""
    return await _job(project_id, "sung_guide", background, vr.run_sung_guide_job, project_id)
