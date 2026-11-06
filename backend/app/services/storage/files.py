"""
Supabase Storage helpers.
All audio files live in Supabase Storage, never in the database or the repo.
"""

import uuid
from app.db.client import get_supabase


def upload_audio(bucket: str, data: bytes, extension: str = "wav") -> str:
    """
    Upload audio bytes to a Supabase Storage bucket.
    Returns the public URL of the uploaded file.
    """
    supabase = get_supabase()
    filename = f"{uuid.uuid4()}.{extension}"

    content_type = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "webm": "audio/webm",
        "ogg": "audio/ogg",
    }.get(extension, "application/octet-stream")

    supabase.storage.from_(bucket).upload(
        path=filename,
        file=data,
        file_options={"content-type": content_type, "upsert": "false"},
    )

    return supabase.storage.from_(bucket).get_public_url(filename)


def create_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    """Create a time-limited signed URL for a private file (used for downloads)."""
    supabase = get_supabase()
    result = supabase.storage.from_(bucket).create_signed_url(path, expires_in)
    return result["signedURL"]
