"""
Voice Room job runners.

CPU-bound vocal work runs in background threads: pitch analysis after upload,
pitch correction, vocal comping, and harmony generation. Each follows Frank's
pattern — do the blocking work (analysis/processing + upload + DB record) in one
worker thread, and never overwrite the original take.
"""

from __future__ import annotations
import asyncio

from app.services.storage.signing import fetch_audio_bytes
from app.db import jobs as jobs_db
from app.db import voice as voice_db
from app.db import projects as projects_db
from app.services.storage.files import upload_audio
from app.services.audio import pitch as pitch_svc
from app.services.audio import comp as comp_svc
from app.services.audio import harmony as harmony_svc
from app.services.generation.renderer import to_mp3_bytes
import io
import soundfile as sf


def _fetch(url: str) -> bytes:
    """Download stored audio. Runs inside the worker thread, not the event loop."""
    return fetch_audio_bytes(url, timeout=30)


def _to_mp3(wav_bytes: bytes) -> bytes:
    """Convert WAV bytes to MP3 for compact, fast-streaming playback storage."""
    data, sr = sf.read(io.BytesIO(wav_bytes), dtype="int16")
    import numpy as np

    if data.ndim == 1:
        data = np.column_stack([data, data])  # to_mp3_bytes expects stereo
    return to_mp3_bytes(data)


# ─── Pitch analysis after upload ─────────────

def _analyze_take_sync(take_id: str, wav_bytes: bytes) -> list[dict]:
    """Detect the pitch contour and store it on the take."""
    contour = pitch_svc.detect_pitch_contour(wav_bytes)
    voice_db.update_take_sync(take_id, {"pitch_data": contour})
    return contour


async def run_pitch_analysis_job(
    job_id: str, take_id: str, wav_bytes: bytes
) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        contour = await asyncio.to_thread(_analyze_take_sync, take_id, wav_bytes)
        await jobs_db.mark_complete(
            job_id, {"take_id": take_id, "contour_points": len(contour)}
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "Couldn't analyze that take.")
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ─── Pitch correction ────────────────────────

def _correct_sync(project_id: str, take_id: str, audio_url: str, mode: str) -> dict:
    """
    Correct a take's pitch and store the result as the take's processed_url.
    The original audio_url is never touched — the user compares and chooses.
    Fetch + process + upload all run here, inside the worker thread.
    """
    wav_bytes = _fetch(audio_url)
    corrected_wav = pitch_svc.correct_pitch(wav_bytes, mode)
    # Store the playback copy as MP3 (small, streams fast); original stays WAV.
    corrected_mp3 = _to_mp3(corrected_wav)
    processed_url = upload_audio(
        "vocals", corrected_mp3, extension="mp3", name_prefix=f"tuned-{mode}"
    )
    voice_db.update_take_sync(take_id, {"processed_url": processed_url})
    return {"take_id": take_id, "processed_url": processed_url}


async def run_correction_job(
    job_id: str, project_id: str, take_id: str, audio_url: str, mode: str
) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        result = await asyncio.to_thread(
            _correct_sync, project_id, take_id, audio_url, mode
        )
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't tune that take — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ─── Vocal comp ──────────────────────────────

def _comp_sync(project_id: str, take_refs: list[tuple[str, str]]) -> dict:
    """take_refs: list of (take_id, audio_url). Fetches in-thread."""
    takes = [(tid, _fetch(url)) for tid, url in take_refs]
    comp_wav, segments = comp_svc.build_comp(takes)
    comp_mp3 = _to_mp3(comp_wav)
    comp_url = upload_audio("vocals", comp_mp3, extension="mp3", name_prefix="comp")
    record = voice_db.create_comp_sync(project_id, comp_url, segments)
    return {"comp_id": record["id"], "audio_url": comp_url, "segments": segments}


async def run_comp_job(
    job_id: str, project_id: str, take_refs: list[tuple[str, str]]
) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        result = await asyncio.to_thread(_comp_sync, project_id, take_refs)
        await projects_db.update_project_active_state(
            project_id, {"active_comp_id": result["comp_id"]}
        )
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't put that together — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ─── Harmony ─────────────────────────────────

def _harmony_sync(
    project_id: str,
    take_id: str,
    audio_url: str,
    harmony_type: str,
    mode: str | None,
) -> dict:
    """
    Generate a harmony layer from a take, using the song's mode so the interval
    fits the key. Stored as its own take record (a harmony layer). We store an
    empty pitch_data list (not null) so the UI doesn't show a perpetual
    "listening…" state for a harmony that was never a raw recording.
    """
    wav_bytes = _fetch(audio_url)
    harmony_wav = harmony_svc.generate_harmony(wav_bytes, harmony_type, mode)
    harmony_mp3 = _to_mp3(harmony_wav)
    harmony_url = upload_audio(
        "vocals", harmony_mp3, extension="mp3", name_prefix="harmony"
    )
    record = voice_db.create_take_sync(
        project_id, harmony_url, label=f"Harmony ({harmony_type})"
    )
    voice_db.update_take_sync(record["id"], {"pitch_data": []})
    return {"harmony_take_id": record["id"], "audio_url": harmony_url}


async def run_harmony_job(
    job_id: str,
    project_id: str,
    take_id: str,
    audio_url: str,
    harmony_type: str,
    mode: str | None = None,
) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        result = await asyncio.to_thread(
            _harmony_sync, project_id, take_id, audio_url, harmony_type, mode
        )
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't build that harmony — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc
