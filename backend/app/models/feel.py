from pydantic import BaseModel
from typing import Optional, Any
from app.models.conversation import ConversationMessage, ConversationAction


class FeelConversationRequest(BaseModel):
    message: str
    fingerprint: dict[str, Any] = {}
    history: list[ConversationMessage] = []


class FeelConversationResponse(BaseModel):
    message: str
    fingerprint_update: dict[str, Any] = {}
    actions: list[ConversationAction] = []


class GenerateTextureRequest(BaseModel):
    fingerprint: dict[str, Any] = {}
    fingerprint_id: Optional[str] = None


class SaveFingerprintRequest(BaseModel):
    fingerprint: dict[str, Any]
    conversation_summary: Optional[str] = None


class FingerprintResponse(BaseModel):
    id: str
    project_id: str
    fingerprint: dict[str, Any]
    conversation_summary: Optional[str] = None
    created_at: str


class TextureResponse(BaseModel):
    id: str
    audio_url: str
    approved: bool = False
    created_at: str
class TextureWaveformResponse(BaseModel):
    texture_id: str
    waveform: list[float]
class HumAnalysisResponse(BaseModel):
    analysis: dict[str, Any]
    audio_url: str


class JobResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    waiting: Optional[str] = None        # "Two songs are ahead of yours…" while it waits its turn
