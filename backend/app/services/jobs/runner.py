"""
Background job runner.

Generation work (textures now, beats/mixes later) is CPU-bound and takes several
seconds. Running it inside a request handler would block the worker and risk a
Render free-tier timeout. So routes create a job row, schedule the work via
FastAPI BackgroundTasks, and return a job_id immediately. The frontend polls
the job status endpoint until the result is ready.

Each runner: marks the job processing, does the work, uploads audio, writes the
DB record, and marks the job complete (or failed with a friendly message).
"""

from __future__ import annotations
import asyncio

from app.db import jobs as jobs_db
from app.db import feel as feel_db
from app.db import projects as projects_db
from app.services.storage.files import upload_audio
from app.services.generation import fingerprint as fp_utils
from app.services.generation.texture import generate_texture_wav


async def run_texture_job(
    job_id: str, project_id: str, fingerprint: dict, fingerprint_id: str | None
) -> None:
    """
    Generate a Feel Lab texture: render audio, store it, record it.
    Checks the cache first so identical parameters reuse an existing texture.
    """
    try:
        await jobs_db.mark_processing(job_id)

        cache_key = fp_utils.texture_cache_key(fingerprint)

        # Cache hit — reuse the existing texture, no re-render.
        cached = await feel_db.find_cached_texture(project_id, cache_key)
        if cached:
            await jobs_db.mark_complete(
                job_id, {"audio_url": cached["audio_url"], "texture_id": cached["id"], "cached": True}
            )
            return

        # Render off the event loop so we don't block other requests.
        wav = await asyncio.to_thread(generate_texture_wav, fingerprint)

        # Store the audio, then create the texture record (the versioning step
        # for this asset) with the explicit cache key and fingerprint link.
        audio_url = upload_audio(
            "textures", wav, extension="wav", name_prefix=cache_key
        )
        texture = await feel_db.save_texture(
            project_id, audio_url, cache_key, fingerprint_id
        )

        await jobs_db.mark_complete(
            job_id,
            {"audio_url": audio_url, "texture_id": texture["id"], "cached": False},
        )
    except Exception as exc:  # noqa: BLE001 — we translate to a friendly message
        # Guard the failure write itself: if marking failed also throws, we must
        # not mask the original error, and the job must not silently vanish.
        try:
            await jobs_db.mark_failed(
                job_id,
                "Frank couldn't find that sound just now — want to try again?",
            )
        except Exception:  # noqa: BLE001
            pass
        # Re-raise for server logs while the user still gets a clean message.
        raise exc
