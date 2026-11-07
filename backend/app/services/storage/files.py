"""
Supabase Storage helpers.
All audio files live in Supabase Storage, never in the database or the repo.
"""

import uuid
from app.db.client import get_supabase


def upload_audio(
    bucket: str,
    data: bytes,
    extension: str = "wav",
    name_prefix: str | None = None,
) -> str:
    """
    Upload audio bytes to a Supabase Storage bucket.
    Returns the public URL of the uploaded file.

    name_prefix, if given, is prepended to the filename. Callers use this to
    embed a cache key so identical generations can be matched later.
    """
    supabase = get_supabase()
    unique = uuid.uuid4().hex
    base = f"{name_prefix}-{unique}" if name_prefix else unique
    filename = f"{base}.{extension}"

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
