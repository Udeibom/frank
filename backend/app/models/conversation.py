from pydantic import BaseModel
from typing import Optional, Any


class ConversationMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ConversationAction(BaseModel):
    type: str
    params: dict[str, Any]


class IdeaConversationRequest(BaseModel):
    message: str
    current_lyrics: str = ""
    selected_text: Optional[str] = None
    history: list[ConversationMessage] = []


class ConversationResponse(BaseModel):
    message: str
    actions: list[ConversationAction] = []
