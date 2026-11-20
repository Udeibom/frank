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
