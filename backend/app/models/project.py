from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    title: str = "Untitled Song"


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None  # draft | in_progress | exported


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectActiveState(BaseModel):
    project_id: str
    active_lyrics_id: Optional[str] = None
    active_fingerprint_id: Optional[str] = None
    active_beat_version_id: Optional[str] = None
    active_vocal_id: Optional[str] = None
    active_comp_id: Optional[str] = None
    active_mix_id: Optional[str] = None
    updated_at: Optional[datetime] = None


class ProjectWithState(BaseModel):
    project: ProjectResponse
    active_state: Optional[ProjectActiveState] = None
