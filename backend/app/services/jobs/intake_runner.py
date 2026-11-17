"""
Intake job runners (start-from-any-input spec 02).

A hum goes in; a tune comes out, but is NOT used until the person confirms it (requirement 3.5).
The original recording is stored untouched, next to the converted copy the analysis reads. A
recording Frank cannot use is not a failure: the job finishes normally with a kind reason, so the
person can try again.
"""

from __future__ import annotations

import asyncio

from app.db import jobs as jobs_db
from app.models.song import MelodySketch
from app.services.audio.convert import to_wav
from app.services.intake import hints, melody, preview
from app.services.jobs.staleness import with_retries
from app.services.song import store
from app.services.storage.files import upload_audio

UNREADABLE = "I couldn't open that recording. Want to try recording it again?"

# One hum is analysed at a time. Each analysis builds large tables, so several at once could use
# more memory than a small server has. Others simply wait their turn.
_one_at_a_time = asyncio.Semaphore(1)


def _hum_sync(audio: bytes, ext: str) -> dict:
    """Blocking work: store the original, convert, find the tune, render the playback."""
    original_url = upload_audio("hums", audio, extension=ext if ext.isalnum() and len(ext) <= 5 else "bin", name_prefix="original")
    try:
        wav = to_wav(audio, ext)
    except RuntimeError:
        return {"ok": False, "reason": UNREADABLE, "original_url": original_url}
    hum_url = upload_audio("hums", wav, extension="wav")

    result = melody.extract_melody(wav, "wav", source_audio=hum_url)
    if not result.ok or result.sketch is None:
        return {"ok": False, "reason": result.reason, "hum_url": hum_url, "original_url": original_url}

    sketch = result.sketch
    playback = preview.render_preview_mp3(sketch)
    preview_url = upload_audio("hums", playback, extension="mp3", name_prefix="heard")
    return {
        "ok": True,
        "hum_url": hum_url,
        "original_url": original_url,
        "preview_url": preview_url,
        "sketch": sketch.model_dump(mode="json"),
        "description": melody.describe_melody(sketch),
        "diagnostics": result.diagnostics,
    }


async def run_hum_intake_job(job_id: str, project_id: str, audio: bytes, ext: str) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        async with _one_at_a_time:
            out = await asyncio.to_thread(_hum_sync, audio, ext)

        if not out["ok"]:
            await with_retries(
                lambda: jobs_db.mark_complete(
                    job_id,
                    {k: v for k, v in out.items() if k in ("ok", "reason", "hum_url", "original_url")},
                )
            )
            return

        sketch = MelodySketch(**out["sketch"])
        # Stored as a new version but NOT made active until the person says it is their tune.
        version = await store.write_facet(
            project_id,
            "melody",
            sketch.model_dump(mode="json"),
            author="frank",
            operation="extract_from_hum",
            op_params={
                "diagnostics": out["diagnostics"],
                "preview_url": out["preview_url"],
                "original_url": out["original_url"],
            },
            label="Hummed tune",
            activate=False,
        )
        result = {
            "ok": True,
            "version_id": version.id,
            "hum_url": out["hum_url"],
            "preview_url": out["preview_url"],
            "description": out["description"],
            "unsure_about": hints.unsure_about(sketch),
        }
        await with_retries(lambda: jobs_db.mark_complete(job_id, result))
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Something went wrong on my side while listening. Your hum is safe. Want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


def _rhythm_sync(audio: bytes, ext: str) -> dict:
    """Blocking work: store the original, find the groove, render the drum playback."""
    from app.services.intake import rhythm

    safe = ext if ext.isalnum() and len(ext) <= 5 else "bin"
    original_url = upload_audio("hums", audio, extension=safe, name_prefix="tapped-original")
    try:
        wav = to_wav(audio, ext)
    except RuntimeError:
        return {"ok": False, "reason": UNREADABLE, "original_url": original_url}
    groove = rhythm.groove_from_audio(wav)
    if not groove.ok:
        return {"ok": False, "reason": groove.reason, "original_url": original_url}
    preview_url = upload_audio("hums", rhythm.render_preview_mp3(groove), extension="mp3", name_prefix="tapped-heard")
    return {"ok": True, "original_url": original_url, "preview_url": preview_url, "groove": groove.to_dict()}


async def run_rhythm_intake_job(job_id: str, project_id: str, audio: bytes, ext: str) -> None:
    """A tapped rhythm goes in; a groove and a drum playback come out. It is only used once the person says yes."""
    try:
        await jobs_db.mark_processing(job_id)
        async with _one_at_a_time:
            out = await asyncio.to_thread(_rhythm_sync, audio, ext)
        await with_retries(lambda: jobs_db.mark_complete(job_id, out))
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "I couldn't work out that rhythm just now. Want to try tapping it again?")
        except Exception:  # noqa: BLE001
            pass
        raise exc
