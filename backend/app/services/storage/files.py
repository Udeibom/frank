"""
Supabase Storage helpers.
All audio files live in Supabase Storage, never in the database or the repo.
"""

import time
import uuid
from app.db.client import get_supabase

_CONTENT_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
}

_MAX_UPLOAD_ATTEMPTS = 3


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

    Retries transient failures. The sync Supabase storage client can raise an
    UnboundLocalError inside its own _request when the underlying HTTP call
    fails before producing a response (a connection race that shows up under
    rapid sequential uploads from a background job). Retrying with a fresh
    request recovers from it; each attempt uses a new unique filename.
    """
    content_type = _CONTENT_TYPES.get(extension, "application/octet-stream")

    last_error: Exception | None = None
    for attempt in range(_MAX_UPLOAD_ATTEMPTS):
        supabase = get_supabase()
        unique = uuid.uuid4().hex
        base = f"{name_prefix}-{unique}" if name_prefix else unique
        filename = f"{base}.{extension}"
        try:
            supabase.storage.from_(bucket).upload(
                path=filename,
                file=data,
                file_options={"content-type": content_type, "upsert": "false"},
            )
            return supabase.storage.from_(bucket).get_public_url(filename)
        except Exception as exc:  # noqa: BLE001 — retry any transient failure
            last_error = exc
            time.sleep(0.5 * (attempt + 1))  # brief backoff before retry

    raise RuntimeError(
        f"Upload to {bucket} failed after {_MAX_UPLOAD_ATTEMPTS} attempts"
    ) from last_error


def upload_audio_with_path(
    bucket: str,
    data: bytes,
    extension: str = "wav",
    name_prefix: str | None = None,
) -> tuple[str, str]:
    """
    Like upload_audio, but returns (storage_path, public_url). The storage path
    is needed to generate signed URLs later (e.g. for private export buckets).
    """
    content_type = _CONTENT_TYPES.get(extension, "application/octet-stream")

    last_error: Exception | None = None
    for attempt in range(_MAX_UPLOAD_ATTEMPTS):
        supabase = get_supabase()
        unique = uuid.uuid4().hex
        base = f"{name_prefix}-{unique}" if name_prefix else unique
        filename = f"{base}.{extension}"
        try:
            supabase.storage.from_(bucket).upload(
                path=filename,
                file=data,
                file_options={"content-type": content_type, "upsert": "false"},
            )
            url = supabase.storage.from_(bucket).get_public_url(filename)
            return filename, url
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.5 * (attempt + 1))

    raise RuntimeError(
        f"Upload to {bucket} failed after {_MAX_UPLOAD_ATTEMPTS} attempts"
    ) from last_error


def create_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    """Create a time-limited signed URL for a private file (used for downloads)."""
    supabase = get_supabase()
    result = supabase.storage.from_(bucket).create_signed_url(path, expires_in)
    return result["signedURL"]
