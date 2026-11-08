from pydantic import BaseModel
from typing import Optional


class CreateExportRequest(BaseModel):
    mix_version_id: str
    apply_mastering: bool = False


class ExportResponse(BaseModel):
    id: str
    project_id: str
    audio_url: str
    format: str
    quality: str
    mastered: bool = False
    mix_version_id: Optional[str] = None
    created_at: str


class DownloadUrlResponse(BaseModel):
    url: str
    filename: str


class JobResponse(BaseModel):
    job_id: str
