from pydantic import BaseModel
from typing import Optional, Any
from app.models.conversation import ConversationMessage, ConversationAction


class GenerateBeatRequest(BaseModel):
    fingerprint: dict[str, Any] = {}
    duration_hint: Optional[int] = None


class EditSectionRequest(BaseModel):
    section_index: int
    instruction: Optional[str] = None


class AddStemRequest(BaseModel):
    stem_type: str
    section_index: Optional[int] = None  # None = all sections


class MuteStemRequest(BaseModel):
    stem_type: str
    section_index: Optional[int] = None  # None = all sections


class BeatConversationRequest(BaseModel):
    message: str
    beat_state: dict[str, Any] = {}
    history: list[ConversationMessage] = []


class BeatConversationResponse(BaseModel):
    message: str
    actions: list[ConversationAction] = []


class SetActiveBeatRequest(BaseModel):
    beat_version_id: str


class UpdateSectionRequest(BaseModel):
    label: Optional[str] = None
    new_index: Optional[int] = None


class BeatVersionResponse(BaseModel):
    id: str
    project_id: str
    render_url: Optional[str] = None
    label: Optional[str] = None
    params: dict[str, Any] = {}
    created_at: str


class JobResponse(BaseModel):
    job_id: str
