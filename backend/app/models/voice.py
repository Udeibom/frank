from pydantic import BaseModel
from typing import Optional, Any
from app.models.conversation import ConversationMessage, ConversationAction


class VocalTakeResponse(BaseModel):
    id: str
    project_id: str
    audio_url: str
    processed_url: Optional[str] = None
    pitch_data: Optional[list[dict[str, Any]]] = None
    label: Optional[str] = None
    created_at: str


class UploadTakeResponse(BaseModel):
    take: VocalTakeResponse
    analysis_job_id: str


class CorrectPitchRequest(BaseModel):
    mode: str = "light"  # light | moderate | full


class CompRequest(BaseModel):
    take_ids: list[str]


class HarmonyRequest(BaseModel):
    take_id: str
    type: str = "above"  # above | below | both


class SetActiveVocalRequest(BaseModel):
    vocal_id: str
    vocal_type: str = "take"  # take | comp


class JobResponse(BaseModel):
    job_id: str


class VoiceConversationRequest(BaseModel):
    message: str
    history: list[ConversationMessage] = []


class VoiceConversationResponse(BaseModel):
    message: str
    actions: list[ConversationAction] = []
