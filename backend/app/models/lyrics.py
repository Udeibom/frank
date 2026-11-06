from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SaveLyricsRequest(BaseModel):
    content: str
    label: Optional[str] = None


class UpdateLyricsLabelRequest(BaseModel):
    label: str


class SetActiveLyricsRequest(BaseModel):
    lyrics_version_id: str


class LyricsVersionResponse(BaseModel):
    id: str
    project_id: str
    content: str
    label: Optional[str] = None
    created_at: datetime


class VoiceMemoResponse(BaseModel):
    transcription: str
    audio_url: str
