from pydantic import BaseModel, Field
from typing import Literal, Optional, Any
from app.models.conversation import ConversationMessage, ConversationAction


class VocalTakeResponse(BaseModel):
    id: str
    project_id: str
    audio_url: str
    processed_url: Optional[str] = None
    pitch_data: Optional[list[dict[str, Any]]] = None
    label: Optional[str] = None
    created_at: str
    kind: str = "take"                      # take | tuned | lined_up | cleaned | harmony
    parent_take_id: Optional[str] = None
    is_harmony: bool = False
    params: dict[str, Any] = Field(default_factory=dict)
    facts: dict[str, Any] = Field(default_factory=dict)


class UploadTakeResponse(BaseModel):
    take: VocalTakeResponse
    analysis_job_id: str


class CorrectPitchRequest(BaseModel):
    mode: Literal["light", "moderate", "full"] = "light"


class AlignRequest(BaseModel):
    mode: Literal["moderate", "full"] = "moderate"     # the gentlest setting never moves timing


class SwapRequest(BaseModel):
    phrase_index: int = Field(ge=0)
    take_id: str


class CompRequest(BaseModel):
    take_ids: list[str] = Field(max_length=8)


class HarmonyRequest(BaseModel):
    take_id: str
    type: Literal["above", "below", "both"] = "above"
    sections: Optional[list[Literal["intro", "verse", "pre-chorus", "chorus", "bridge", "outro"]]] = None


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
