from pydantic import BaseModel
from typing import Optional, Any
from app.models.conversation import ConversationMessage, ConversationAction


class RenderMixRequest(BaseModel):
    mix_params: dict[str, Any] = {}
    quality: str = "preview"  # preview | full


class MixConversationRequest(BaseModel):
    message: str
    mix_params: dict[str, Any] = {}
    history: list[ConversationMessage] = []


class MixConversationResponse(BaseModel):
    message: str
    mix_params: dict[str, Any]       # the updated params after applying actions
    actions: list[ConversationAction] = []
    render: bool                     # whether the client should kick off a render


class SetActiveMixRequest(BaseModel):
    mix_version_id: str


class MixVersionResponse(BaseModel):
    id: str
    project_id: str
    render_url: Optional[str] = None
    label: Optional[str] = None
    mix_params: dict[str, Any] = {}
    created_at: str


class JobResponse(BaseModel):
    job_id: str
