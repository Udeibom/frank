import asyncio

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from app.models.lyrics import (
    SaveLyricsRequest,
    UpdateLyricsLabelRequest,
    SetActiveLyricsRequest,
    LyricsVersionResponse,
    VoiceMemoResponse,
)
from app.db import lyrics as db
from app.db import projects as projects_db
from app.services.audio.convert import to_wav
from app.services.llm.whisper import transcribe
from app.services.storage.files import upload_audio

router = APIRouter(prefix="/projects/{project_id}/lyrics", tags=["lyrics"])


@router.get("", response_model=list[LyricsVersionResponse])
async def list_lyrics_versions(project_id: str) -> list[LyricsVersionResponse]:
    """List all lyrics versions for a project, newest first."""
    versions = await db.list_versions(project_id)
    return [LyricsVersionResponse(**v) for v in versions]


@router.post("", response_model=LyricsVersionResponse, status_code=201)
async def save_lyrics_version(
    project_id: str, body: SaveLyricsRequest
) -> LyricsVersionResponse:
    """
    Save a new lyrics version.
    Deduplication: if the content is identical to the latest version,
    return the existing version instead of creating a duplicate.
    """
    latest = await db.get_latest_version(project_id)
    if latest and latest["content"] == body.content:
        return LyricsVersionResponse(**latest)

    version = await db.create_version(project_id, body.content, body.label)

    # Mark this as the active lyrics version
    await projects_db.update_project_active_state(
        project_id, {"active_lyrics_id": version["id"]}
    )

    from app.services.team.identity import refresh_soon

    refresh_soon(project_id)                 # what makes the song theirs may have changed (spec 10)
    return LyricsVersionResponse(**version)


@router.get("/{version_id}", response_model=LyricsVersionResponse)
async def get_lyrics_version(
    project_id: str, version_id: str
) -> LyricsVersionResponse:
    """Get a single lyrics version."""
    version = await db.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Lyrics version not found")
    return LyricsVersionResponse(**version)


@router.patch("/{version_id}", response_model=LyricsVersionResponse)
async def update_lyrics_label(
    project_id: str, version_id: str, body: UpdateLyricsLabelRequest
) -> LyricsVersionResponse:
    """Update a version's label."""
    updated = await db.update_label(version_id, body.label)
    return LyricsVersionResponse(**updated)


@router.post("/active", status_code=200)
async def set_active_lyrics(
    project_id: str, body: SetActiveLyricsRequest
) -> dict:
    """Set which lyrics version is the active one."""
    await projects_db.update_project_active_state(
        project_id, {"active_lyrics_id": body.lyrics_version_id}
    )
    return {"status": "ok", "active_lyrics_id": body.lyrics_version_id}


@router.post("/voice-memo", response_model=VoiceMemoResponse)
async def transcribe_voice_memo(
    project_id: str, file: UploadFile = File(...)
) -> VoiceMemoResponse:
    """
    Accept a voice memo, store it, transcribe it, and return the text.
    The transcription is a suggestion — never auto-inserted into the lyrics.
    Voice memos are short (seconds), so inline processing is acceptable here.
    """
    raw = await file.read()

    # Determine input extension from the upload
    ext = "webm"
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()

    # Convert to WAV for Whisper
    wav = await asyncio.to_thread(to_wav, raw, input_ext=ext)

    # Store the original memo audio (WAV) — reusable by the Feel Lab later
    audio_url = upload_audio("voice-memos", wav, extension="wav")

    # Transcribe
    try:
        text = await transcribe(wav)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Couldn't make out the recording — want to try again?",
        ) from exc

    return VoiceMemoResponse(transcription=text, audio_url=audio_url)


# ── how the words sound (frankenstein spec 14, requirement 5) ─────────────────────────────────────────────

class AnalyseRequest(BaseModel):
    text: str = Field(max_length=20_000)


class RhymesRequest(BaseModel):
    word: str = Field(min_length=1, max_length=40)


@router.post("/analyse")
async def analyse_lyrics(project_id: str, body: AnalyseRequest) -> dict:
    """Syllables per line, strong syllables, rhyme families, and at most two plain observations."""
    from app.services.words import sound

    lines = await asyncio.to_thread(sound.analyse, body.text)
    return {"lines": sound.as_json(lines), "notes": sound.plain_notes(lines)}


@router.post("/rhymes")
async def find_rhymes(project_id: str, body: RhymesRequest) -> dict:
    from app.services.words import sound

    word = body.word.strip().split()[-1]
    return await asyncio.to_thread(sound.rhymes, word)


class EmotionsRequest(BaseModel):
    text: str = Field(max_length=20_000)


EMOTION_WORDS = {"admiration": "admiring", "amusement": "playful", "anger": "angry", "annoyance": "irritated",
                 "approval": "warm", "caring": "tender", "confusion": "unsure", "curiosity": "curious", "desire": "longing",
                 "disappointment": "let down", "disapproval": "bitter", "disgust": "disgusted", "embarrassment": "exposed",
                 "excitement": "excited", "fear": "afraid", "gratitude": "grateful", "grief": "grieving", "joy": "joyful",
                 "love": "in love", "nervousness": "nervous", "optimism": "hopeful", "pride": "proud", "realization": "awake",
                 "relief": "relieved", "remorse": "sorry", "sadness": "sad", "surprise": "surprised", "neutral": "calm"}
ENERGY = {"anger": 0.85, "excitement": 0.85, "joy": 0.75, "amusement": 0.7, "pride": 0.7, "optimism": 0.6, "desire": 0.55,
          "love": 0.5, "admiration": 0.5, "fear": 0.6, "nervousness": 0.55, "surprise": 0.65, "sadness": 0.3, "grief": 0.25,
          "remorse": 0.3, "disappointment": 0.35, "caring": 0.4, "relief": 0.4, "neutral": 0.45}


@router.post("/emotions")
async def lyric_emotions(project_id: str, body: EmotionsRequest) -> dict:
    """The feelings in each section of the words, as the song's shape (frankenstein spec 14, requirement 5.3)."""
    import re as _re

    from app.services import provenance
    from app.services.remote import organs

    sections: list[tuple[str, list[str]]] = []
    for line in body.text.splitlines():
        s = line.strip()
        m = _re.match(r"^[\[(]?\s*(intro|verse|pre-?chorus|chorus|hook|refrain|bridge|outro)\b[^\])]*[\])]?\s*:?\s*$", s, _re.I)
        if m:
            sections.append((m.group(1).capitalize(), []))
        elif s:
            if not sections:
                sections.append(("Start", []))
            sections[-1][1].append(s)
    sections = [x for x in sections if x[1]]
    if not sections:
        return {"sections": [], "message": "Write a few lines and I'll tell you how they feel."}
    got = await asyncio.to_thread(organs.try_, organs.emotions, [" ".join(lines)[:400] for _, lines in sections])
    if not got:
        return {"sections": [], "message": "I can't read the feelings right now. Try again in a minute."}
    out = []
    for (name, _), top in zip(sections, got):
        feel = [EMOTION_WORDS.get(t["name"], t["name"]) for t in top if t["score"] >= 0.15][:2] or ["calm"]
        energy = sum(ENERGY.get(t["name"], 0.45) * t["score"] for t in top) / max(1e-6, sum(t["score"] for t in top))
        out.append({"section": name, "feels": feel, "energy": round(energy, 2)})
    await asyncio.to_thread(provenance.note, project_id, "words", None, "emotion")
    rises = [b["section"] for a, b in zip(out, out[1:]) if b["energy"] - a["energy"] > 0.15]
    msg = f"Your words lift in the {rises[0].lower()}, so the music could lift there too." if rises else "Your words keep one feeling all the way through."
    return {"sections": out, "message": msg}
