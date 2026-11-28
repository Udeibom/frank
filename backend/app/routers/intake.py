"""Intake routes (start-from-any-input spec 02). Mounted under the project ownership check."""

from __future__ import annotations
from app.services.jobs import dispatch

import asyncio
import logging
import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, ValidationError

from app.db import feel as feel_db
from app.db import jobs as jobs_db
from app.db import lyrics as lyrics_db
from app.db import projects as projects_db
from app.db import song as song_db
from app.models.feel import JobResponse
from app.models.song import FacetVersionResponse, LyricsReading, MelodySketch
from app.services.intake import lyrics as lyrics_svc
from app.services.intake import merge as merge_svc
from app.services.generation import fingerprint as fp_utils
from app.services.llm.groq_client import chat_json
from app.services.intake.hints import fingerprint_hints
from app.services.jobs.intake_runner import run_hum_intake_job, run_rhythm_intake_job
from app.services.song import store
from app.services.song.versions import VersionError

router = APIRouter(prefix="/projects/{project_id}/intake", tags=["intake"])

# A minute of hum is well under a megabyte in a browser's format and around 10 MB as raw phone audio.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_EXTENSION = re.compile(r"[a-z0-9]{1,5}")


class ConfirmMelodyResponse(BaseModel):
    version: FacetVersionResponse
    fingerprint_hints: dict
    question: Optional[str] = None      # a tune that disagrees with what is settled asks which should lead (req 6.5)


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
    await dispatch.start(background, job, run_hum_intake_job, project_id, raw, safe_extension(file.filename))
    return JobResponse(job_id=job["id"])


@router.post("/rhythm", response_model=JobResponse)
async def start_rhythm_intake(
    project_id: str, background: BackgroundTasks, file: UploadFile = File(...)
) -> JobResponse:
    """Turn tapped or spoken beats into a groove. The result waits for the person's yes: the browser then saves it in the feel."""
    raw = await _read_limited(file)
    if not raw:
        raise HTTPException(status_code=400, detail="I didn't get any sound from that recording. Could you try once more?")
    job = await jobs_db.create_job(project_id, job_type="rhythm_intake")
    await dispatch.start(background, job, run_rhythm_intake_job, project_id, raw, safe_extension(file.filename))
    return JobResponse(job_id=job["id"])


async def _find_melody(project_id: str, version_id: str):
    versions = await song_db.list_versions(project_id, "melody")
    found = next((v for v in versions if v.id == version_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail="I can't find that tune any more.")
    return found


async def _counted_for_the_song(project_id: str, content: dict) -> dict:
    """
    The tune counted at the speed that fits the song (core-path spec 15, 2.1): a slow worship hum read at 138 is
    the same pulse as 69, and the song should be built at 69. The notes are rescaled, so the tune sounds the same.
    """
    from app.services.intake import pace
    from app.services.song import record as song_record

    try:
        speed = float(content.get("tempo_bpm") or 0)
        if speed <= 0:
            return content
        lyrics = (await lyrics_db.get_latest_version(project_id) or {}).get("content") or ""
        intent = (await song_record.active_facet(project_id, "intent") or {}).get("text") or ""
        latest = await feel_db.get_latest_fingerprint(project_id)
        factor = pace.choose_factor(speed, pace.centre(f"{intent} {lyrics}", (latest or {}).get("fingerprint")))
        return pace.recount(content, factor)
    except Exception:  # noqa: BLE001 - the tune as heard is still a fine tune
        log.warning("could not choose the tune's count", exc_info=True)
        return content


async def _record_hum_start(project_id: str, version_id: str) -> None:
    try:
        latest = await feel_db.get_latest_fingerprint(project_id)
        base = dict((latest or {}).get("fingerprint") or {})
        start = {"kind": "hum", "source_id": version_id}
        if fp_utils.approved_start(base) == start:
            return
        saved = await feel_db.save_fingerprint(
            project_id, fp_utils.with_approved_start(base, start), (latest or {}).get("conversation_summary")
        )
        await projects_db.update_project_active_state(project_id, {"active_fingerprint_id": saved["id"]})
    except Exception:  # noqa: BLE001
        log.warning("could not record the hum as the beat's start", exc_info=True)


async def _clear_hum_start(project_id: str, version_ids: set[str]) -> None:
    try:
        latest = await feel_db.get_latest_fingerprint(project_id)
        base = dict((latest or {}).get("fingerprint") or {})
        start = fp_utils.approved_start(base)
        if not start or start.get("kind") != "hum" or start.get("source_id") not in version_ids:
            return
        saved = await feel_db.save_fingerprint(
            project_id, fp_utils.without_approved_start(base), (latest or {}).get("conversation_summary")
        )
        await projects_db.update_project_active_state(project_id, {"active_fingerprint_id": saved["id"]})
    except Exception:  # noqa: BLE001
        log.warning("could not clear the rejected hum as the beat's start", exc_info=True)


@router.post("/melody/{version_id}/confirm", response_model=ConfirmMelodyResponse)
async def confirm_melody(project_id: str, version_id: str) -> ConfirmMelodyResponse:
    """The person said "yes, that's my tune". Only now does it become the song's tune."""
    found = await _find_melody(project_id, version_id)
    content = found.content if found.content.get("confirmed") else await _counted_for_the_song(project_id, found.content)
    # Check the content is a real tune BEFORE writing anything, so a bad version cannot leave a
    # half-saved step behind.
    try:
        sketch = MelodySketch(**{**content, "confirmed": True})
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="That tune can't be saved right now.") from exc

    # Saying yes twice is the same as saying it once.
    if found.content.get("confirmed"):
        await store.activate_facet_version(project_id, "melody", found.id)
        await _record_hum_start(project_id, found.id)
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
    await _record_hum_start(project_id, confirmed.id)
    hints = fingerprint_hints(sketch, sketch.source_audio)
    return ConfirmMelodyResponse(
        version=FacetVersionResponse(**confirmed.model_dump(), is_active=True),
        fingerprint_hints=hints,
        question=await _tune_question(project_id, hints),
    )


async def _tune_question(project_id: str, hints: dict) -> Optional[str]:
    """The tune against what the song already settled (the words' feeling, the talk): one question, never a silent pick."""
    try:
        latest = await feel_db.get_latest_fingerprint(project_id)
        _, _, conflicts = merge_svc.merge_fingerprint((latest or {}).get("fingerprint"), hints)
        return merge_svc.conflict_question(conflicts, "tune")
    except Exception:  # noqa: BLE001
        return None


@router.post("/melody/{version_id}/reject")
async def reject_melody(project_id: str, version_id: str) -> dict:
    """The person said it is not their tune. Remember that, and leave the song's tune untouched."""
    found = await _find_melody(project_id, version_id)
    await _clear_hum_start(project_id, {version_id, found.id})
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


# ─── Reading the words ───────────────────────

log = logging.getLogger("frank.intake")

# Songs being read right now. Each read is one request to a rate-limited model, so a second press
# (a double click, a second tab) is turned away instead of doubling the cost.
_reading_now: set[str] = set()

TRUNCATED_NOTE = " Your song is longer than I can read in one go, so I read the first part."


class ReadLyricsRequest(BaseModel):
    content: Optional[str] = Field(default=None, max_length=50_000)   # the words as on screen; defaults to the saved lyrics


class ReadLyricsResponse(BaseModel):
    ok: bool
    message: str                      # what Frank says, in plain words
    reading: Optional[LyricsReading] = None
    filled: list[str] = []            # parts of the song's direction that the words filled in
    asked: Optional[str] = None       # the one question Frank is asking, if any
    reused: bool = False              # True when these exact words were already read


async def _already_read(project_id: str, fingerprint: str) -> Optional[tuple[str, Optional[str]]]:
    """If the active feeling and structure were both made from exactly these words, return (summary, question)."""
    active = await song_db.get_active_map(project_id)
    ids = [active.get("feeling"), active.get("structure")]
    if not all(ids):
        return None
    by_id = {v.id: v for v in await song_db.get_versions(project_id, [i for i in ids if i])}
    feeling, structure = by_id.get(active["feeling"]), by_id.get(active["structure"])
    if feeling is None or structure is None:
        return None
    if feeling.content.get("lyrics_fingerprint") != fingerprint or structure.content.get("lyrics_fingerprint") != fingerprint:
        return None
    return str(feeling.content.get("summary", "")), (feeling.content.get("question") or None)


@router.post("/lyrics", response_model=ReadLyricsResponse)
async def read_lyrics_route(project_id: str, body: ReadLyricsRequest) -> ReadLyricsResponse:
    """
    Read the song's words for their feeling and structure. Fills the feeling and structure parts of
    the song record, and lets the words suggest a direction for the music without changing anything
    the person already settled. A disagreement becomes one question, not a silent choice.
    """
    if project_id in _reading_now:
        raise HTTPException(status_code=409, detail="I'm already reading your words. Give me a moment.")
    _reading_now.add(project_id)
    try:
        return await _read_lyrics(project_id, body)
    finally:
        _reading_now.discard(project_id)


async def _read_lyrics(project_id: str, body: ReadLyricsRequest) -> ReadLyricsResponse:
    text = body.content
    if text is None:
        state = await projects_db.get_project_active_state(project_id) or {}
        active = await lyrics_db.get_version(state["active_lyrics_id"]) if state.get("active_lyrics_id") else None
        text = (active or {}).get("content") or ""

    # The exact words that would be read (a very long song is cut on a line break).
    kept, was_cut = lyrics_svc.cut_to_fit(text)
    if not lyrics_svc.too_little(kept):
        seen = await _already_read(project_id, lyrics_svc.fingerprint_of(kept))
        if seen is not None:
            summary, question = seen
            note = TRUNCATED_NOTE if was_cut else ""
            return ReadLyricsResponse(
                ok=True, message=f"{summary}{(' ' + question) if question else ''}{note}", asked=question, reused=True,
            )

    try:
        reading = await asyncio.to_thread(lyrics_svc.read_lyrics, text, chat_json)
    except Exception as exc:  # noqa: BLE001  (a dropped connection, a rate limit, ...)
        log.warning("reading lyrics failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="I couldn't read your words just now. Your lyrics are safe. Want to try again?") from exc

    if not reading.ok:
        return ReadLyricsResponse(ok=False, message=reading.reason or "I need a few more lines to read.")

    # What the words suggest for the music, and the one question to ask (a disagreement beats a vague doubt).
    hints = lyrics_svc.lyrics_hints(reading)
    conflict_q: Optional[str] = None
    merged: Optional[dict] = None
    filled: list[str] = []
    latest: Optional[dict] = None
    if hints:
        latest = await feel_db.get_latest_fingerprint(project_id)
        merged, filled, conflicts = merge_svc.merge_fingerprint((latest or {}).get("fingerprint"), hints)
        conflict_q = merge_svc.conflict_question(conflicts, "words")
    asked = conflict_q or reading.question

    based_on = {"lyrics_fingerprint": reading.based_on, "truncated": reading.truncated}
    if reading.feeling is not None:
        await store.write_facet(
            project_id, "feeling", {**reading.feeling.model_dump(), "question": asked, **based_on},
            author="frank", operation="read_lyrics", label="Feeling of the words",
        )
    await store.write_facet(
        project_id, "structure",
        {"sections": [s.model_dump() for s in reading.sections], "from_model": reading.from_model, **based_on},
        author="frank", operation="read_lyrics", label="Shape of the song",
    )

    # The suggested direction is a bonus. If saving it fails, the reading itself still succeeded.
    if filled and merged is not None:
        try:
            saved = await feel_db.save_fingerprint(project_id, merged, (latest or {}).get("conversation_summary"))
            await projects_db.update_project_active_state(project_id, {"active_fingerprint_id": saved["id"]})
        except Exception as exc:  # noqa: BLE001
            log.warning("could not save the direction suggested by the words: %s", type(exc).__name__)
            filled = []

    note = TRUNCATED_NOTE if reading.truncated else ""
    if reading.feeling is not None:
        message = f"{reading.feeling.summary}{(' ' + asked) if asked else ''}{note}"
    else:
        message = (
            "I've marked out the verses and choruses from how you laid the words out. "
            "I couldn't read the feeling just now, so tell me how it should feel." + note
        )
    return ReadLyricsResponse(ok=True, message=message, reading=reading, filled=filled, asked=asked)


# ── a description, typed or spoken (spec 02, requirement 5) ──────────────

class DescriptionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class DescriptionResponse(BaseModel):
    ok: bool
    message: str
    heard: Optional[str] = None             # the words Frank read (the transcription, for a voice memo)
    asked: Optional[str] = None
    filled: list[str] = []


async def _from_description(project_id: str, text: str, source: str, audio_url: Optional[str] = None) -> DescriptionResponse:
    from app.models.song import USER_AUTHOR
    from app.services.intake import description as desc_svc
    from app.services.song import record as song_record

    if desc_svc.too_little(text):
        return DescriptionResponse(ok=False, message="Tell me a little more: a few words about how it should feel is enough.", heard=text)
    try:
        reading = await asyncio.to_thread(desc_svc.read_description, text, chat_json)
    except Exception as exc:  # noqa: BLE001
        log.warning("reading a description failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="I couldn't take that in just now. Your words are safe. Want to try again?") from exc
    original = {"source": source, "text": text.strip()[:2000], **({"audio_url": audio_url} if audio_url else {})}
    # 1. their words are the intent statement, if the song has none yet (only the person writes the intent)
    if not await song_record.active_facet(project_id, "intent"):
        await store.write_facet(project_id, "intent", {"text": text.strip()[:600], "room": "start"}, author=USER_AUTHOR,
                                operation=f"described_by_{source}", op_params=original, label="What you said the song is")
    # 2. the feeling, with the confidence of every value (requirement 6.1)
    await store.write_facet(project_id, "feeling", {"words": reading["feeling_words"], "summary": reading["summary"],
                                                    "confidence": reading["confidence"], "from": source},
                            author="frank", operation=f"read_{source}", op_params=original, label="Feeling you described")
    # 3. confident hints fill gaps in the song's direction; a disagreement becomes one question
    filled: list[str] = []
    asked = reading["question"] or None
    if reading["hints"]:
        latest = await feel_db.get_latest_fingerprint(project_id)
        merged, filled, conflicts = merge_svc.merge_fingerprint((latest or {}).get("fingerprint"), reading["hints"])
        asked = merge_svc.conflict_question(conflicts, "words") or asked
        if filled:
            try:
                saved = await feel_db.save_fingerprint(project_id, merged, (latest or {}).get("conversation_summary"))
                await projects_db.update_project_active_state(project_id, {"active_fingerprint_id": saved["id"]})
            except Exception as exc:  # noqa: BLE001
                log.warning("could not save the direction from the description: %s", type(exc).__name__)
                filled = []
    message = reading["summary"] or "I've got the feeling you described."
    if asked:
        message = f"{message} {asked}"
    return DescriptionResponse(ok=True, message=message, heard=text, asked=asked, filled=filled)


@router.post("/description", response_model=DescriptionResponse)
async def start_from_description(project_id: str, body: DescriptionRequest) -> DescriptionResponse:
    """'It should feel like walking home alone at night': the song starts from how it should feel."""
    return await _from_description(project_id, body.text, "description")


@router.post("/voice-memo", response_model=DescriptionResponse)
async def start_from_voice_memo(project_id: str, file: UploadFile = File(...)) -> DescriptionResponse:
    """A spoken description: kept as audio, transcribed, then read like a typed one (requirement 5.1)."""
    from app.services.audio.convert import to_wav
    from app.services.llm.whisper import transcribe
    from app.services.storage.files import upload_audio

    raw = await _read_limited(file)
    wav = await asyncio.to_thread(to_wav, raw, input_ext=safe_extension(file.filename))
    audio_url = upload_audio("voice-memos", wav, extension="wav", name_prefix="described")
    try:
        text = (await transcribe(wav)).strip()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="I couldn't make out the recording. Want to try again?") from exc
    if not text:
        return DescriptionResponse(ok=False, message="I couldn't hear any words in that. Want to try again, a little closer?")
    return await _from_description(project_id, text, "voice_memo", audio_url)



# ── one way in: a recording, whatever it is (spec 02, requirement 1.2) ───

def is_speech(wav: bytes, words: int) -> bool:
    """
    Talking has many words and little held pitch; humming or singing holds notes. Decides which path a recording
    takes, so nobody has to choose before they start.
    """
    from app.services.audio import vocal_notes
    from app.services.jobs.voice_runner import _read_mono

    mono = _read_mono(wav)
    seconds = max(0.5, mono.shape[0] / 44100)
    notes = vocal_notes.sung_notes(mono, 44100)
    held = sum(n.length for n in notes if n.length >= 0.25) / seconds
    return words >= 5 and held < 0.35


class RecordingResponse(BaseModel):
    kind: str                                     # "description" | "hum"
    description: Optional[DescriptionResponse] = None
    job_id: Optional[str] = None                  # the hum's job, when it was a tune


@router.post("/recording", response_model=RecordingResponse)
async def start_from_recording(project_id: str, background: BackgroundTasks, file: UploadFile = File(...)) -> RecordingResponse:
    """Hum it, sing it or say it: Frank works out which, then takes the right path."""
    from app.services.audio.convert import to_wav
    from app.services.llm.whisper import transcribe
    from app.services.storage.files import upload_audio

    raw = await _read_limited(file)
    ext = safe_extension(file.filename)
    wav = await asyncio.to_thread(to_wav, raw, input_ext=ext)
    try:
        text = (await transcribe(wav)).strip()
    except Exception:  # noqa: BLE001  no words to read: treat it as a tune
        text = ""
    words = len(re.findall(r"[A-Za-z']+", text))
    if text and await asyncio.to_thread(is_speech, wav, words):
        audio_url = upload_audio("voice-memos", wav, extension="wav", name_prefix="described")
        return RecordingResponse(kind="description", description=await _from_description(project_id, text, "voice_memo", audio_url))
    job = await jobs_db.create_job(project_id, job_type="hum_intake")
    await dispatch.start(background, job, run_hum_intake_job, project_id, raw, ext)
    return RecordingResponse(kind="hum", job_id=job["id"])


# ── a picture, or right now (frankenstein spec 14, requirements 6.6 and 6.7) ─────────────────────────────────

async def _fill_hints(project_id: str, hints: dict) -> list[str]:
    """Measured hints fill gaps in the song's direction; they never overwrite what the person or Frank set."""
    if not hints:
        return []
    latest = await feel_db.get_latest_fingerprint(project_id)
    merged, filled, _ = merge_svc.merge_fingerprint((latest or {}).get("fingerprint"), hints)
    if filled:
        try:
            saved = await feel_db.save_fingerprint(project_id, merged, (latest or {}).get("conversation_summary"))
            await projects_db.update_project_active_state(project_id, {"active_fingerprint_id": saved["id"]})
        except Exception as exc:  # noqa: BLE001
            log.warning("could not save hints: %s", type(exc).__name__)
            return []
    return filled


IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}


@router.post("/picture", response_model=DescriptionResponse)
async def start_from_picture(project_id: str, file: UploadFile = File(...)) -> DescriptionResponse:
    """A photo that shows the feeling. Colours are measured here; the feeling is read by Gemini where allowed."""
    from app.services import provenance, region
    from app.services.intake import picture
    from app.services.llm import gemini_media

    if file.content_type and file.content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="That doesn't look like a picture. A photo or screenshot works best.")
    data = await _read_limited(file)
    try:
        px = await asyncio.to_thread(picture.pixels, data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="I couldn't open that picture. Want to try another one?") from exc
    colours = picture.colours(px)
    look = await asyncio.to_thread(gemini_media.look, data, file.content_type or "image/jpeg") if region.gemini_allowed() else None
    text = picture.description_from(look, colours)
    result = await _from_description(project_id, text, "picture")
    filled = await _fill_hints(project_id, picture.hints(colours))
    if look:
        await asyncio.to_thread(provenance.note, project_id, "feeling", None, "looked")
    else:
        await asyncio.to_thread(provenance.note, project_id, "feeling", None, "looked",
                                "Feeling: taken from the colours of your picture", "Measured by Frank")
    result.filled = sorted(set(result.filled) | set(filled))
    if not look and not region.gemini_allowed():
        result.message = f"{result.message} (I went by the picture's colours: {region.GEMINI_REGION_MESSAGE[0].lower()}{region.GEMINI_REGION_MESSAGE[1:]})"
    return result


class MomentRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    hour: Optional[int] = Field(default=None, ge=0, le=23)     # the browser's local hour, if weather is unavailable


@router.post("/moment", response_model=DescriptionResponse)
async def start_from_moment(project_id: str, body: MomentRequest) -> DescriptionResponse:
    """Right now: the person's time of day and weather become the feeling."""
    from app.services import provenance
    from app.services.intake import moment

    code = temp = None
    hour = body.hour if body.hour is not None else 21
    try:
        w = await asyncio.to_thread(moment.weather, body.latitude, body.longitude)
        code, temp = w.get("code"), w.get("temp_c")
        if w.get("local_time") and "T" in str(w["local_time"]):
            hour = int(str(w["local_time"]).split("T")[1][:2])
    except Exception:  # noqa: BLE001 - no weather: the time of day still says a lot
        log.info("open-meteo unavailable; using the time of day only")
    result = await _from_description(project_id, moment.describe(hour, code, temp, None), "moment")
    filled = await _fill_hints(project_id, moment.hints(hour, code))
    await asyncio.to_thread(provenance.note, project_id, "feeling", None, "moment")
    result.filled = sorted(set(result.filled) | set(filled))
    return result
