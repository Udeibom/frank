"""
Export job runner.

Takes a mix version's render, optionally runs it through the mastering chain,
and produces the final downloadable MP3 (320kbps), stored as an export record.
All fetch + master + upload + record runs in one worker thread.
"""

from __future__ import annotations
import asyncio

from app.services.storage.signing import fetch_audio_bytes
from app.db import jobs as jobs_db
from app.services.jobs.heavy import run_heavy
from app.db import export as export_db
from app.db import mix as mix_db
from app.services.storage.files import upload_audio_with_path
from app.services.audio import mastering


def _fetch(url: str) -> bytes:
    return fetch_audio_bytes(url, timeout=60)


def _reencode_320(mp3_bytes: bytes) -> bytes:
    """Re-encode an existing mix MP3 to 320kbps for a clean final export."""
    import subprocess
    import tempfile
    import os

    in_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(mp3_bytes)
            in_path = f.name
        out_path = in_path[:-4] + ".export.mp3"
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-b:a", "320k", out_path],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode()[:200])
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        for p in (in_path, out_path):
            if p and os.path.exists(p):
                os.remove(p)


def _export_sync(project_id: str, mix_version: dict, layers: dict, apply_mastering: bool) -> dict:
    """
    Finishing (finish-and-intent spec 11, requirement 2): the mix is rendered again at full quality and kept
    uncompressed, so the 320 kbps file never comes from a small preview. Both the mix as it is ("before") and the
    finished song ("after") are made from that one render, so the person can compare and choose. Dedup: an
    export already made for this mix version is reused.
    """
    from app.services.jobs.mix_runner import render_array

    mix_version_id = mix_version["id"]
    wanted = export_db.find_existing_export_sync(project_id, mix_version_id, apply_mastering)
    other = export_db.find_existing_export_sync(project_id, mix_version_id, not apply_mastering)
    if wanted and (other or not apply_mastering):
        before = other if apply_mastering else wanted
        shape = mastering._decode_with_ffmpeg(_fetch(wanted["audio_url"])).T       # (channels, samples)
        return {"export_id": wanted["id"], "audio_url": wanted["audio_url"], "before_url": before["audio_url"] if before else None,
                "reused": True, "waveform": waveform(shape)}

    params = {k: v for k, v in (mix_version.get("mix_params") or {}).items() if k != "sources"}
    audio = render_array(layers, params)                       # uncompressed, (channels, samples)
    report: dict = {}
    made: dict[bool, dict] = {}
    if not (other if apply_mastering else wanted):
        plain = mastering.encode_plain(audio)
        path, url = upload_audio_with_path("exports", plain, extension="mp3", name_prefix="as-mixed")
        made[False] = export_db.create_export_sync(project_id, url, path, mix_version_id, False, "mp3", "320k")
        del plain
    if apply_mastering and not wanted:
        finished, report = mastering.finish(audio)
        path, url = upload_audio_with_path("exports", finished, extension="mp3", name_prefix="export")
        made[True] = export_db.create_export_sync(project_id, url, path, mix_version_id, True, "mp3", "320k")
    peaks = waveform(audio)
    del audio
    final = made.get(apply_mastering) or wanted
    before = made.get(False) or (other if apply_mastering else wanted)
    return {"export_id": final["id"], "audio_url": final["audio_url"], "before_url": before["audio_url"] if before else None,
            "reused": False, "finish": report, "waveform": peaks}


WAVE_POINTS = 300


def waveform(audio) -> list[float]:
    """The song's shape for the final-listen screen (export-room 7.1): loudest moment per slice, 0..1."""
    import numpy as np

    if audio.size == 0:
        return []
    mono = np.abs(audio).max(axis=0)
    step = max(1, mono.size // WAVE_POINTS)
    peaks = mono[: step * (mono.size // step)].reshape(-1, step).max(axis=1)
    top = float(peaks.max()) or 1.0
    return [round(float(p) / top, 3) for p in peaks[:WAVE_POINTS]]


async def run_export_job(
    job_id: str, project_id: str, mix_version_id: str, apply_mastering: bool
) -> None:
    from app.services.jobs.mix_runner import layers_for

    try:
        await jobs_db.mark_processing(job_id)

        version = await mix_db.get_mix_version(mix_version_id)
        if not version or not version.get("render_url"):
            await jobs_db.mark_failed(
                job_id, "That mix isn't ready to export yet."
            )
            return
        layers = await layers_for(project_id, version)
        if not layers.get("vocal_url") and not layers.get("beat_url") and not layers.get("parts"):
            await jobs_db.mark_failed(job_id, "I can't find the voice or the music this mix was made from.")
            return

        result = await run_heavy(_export_sync, project_id, version, layers, apply_mastering)
        if apply_mastering:
            from app.db import projects as projects_db

            await projects_db.update_project(project_id, {"status": "exported"})     # the song is finished
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't finish your song just then — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ── a master matched to a song the person picked (frankenstein spec 14, requirement 6.4) ─────────────────

def _matched_sync(project_id: str, mix_version: dict, layers: dict, reference: bytes, ref_ext: str) -> dict:
    """Frank's own render, sent with the reference to Matchering on frank-ears. The result is a second master to
    compare with Frank's; nothing replaces the person's chosen one."""
    import io

    import numpy as np
    import soundfile as sf

    from app.services import provenance
    from app.services.jobs.mix_runner import render_array
    from app.services.remote import organs

    params = {k: v for k, v in (mix_version.get("mix_params") or {}).items() if k != "sources"}
    audio = render_array(layers, params)
    buf = io.BytesIO()
    sf.write(buf, np.ascontiguousarray(audio.T), mastering.SR, format="WAV", subtype="PCM_16")
    del audio
    matched = organs.match_master(buf.getvalue(), reference, "wav", ref_ext)
    del buf
    arr = mastering._decode_with_ffmpeg(matched).T if hasattr(mastering, "_decode_with_ffmpeg") else None
    mp3 = mastering.encode_plain(arr) if arr is not None else matched
    path, url = upload_audio_with_path("exports", mp3, extension="mp3", name_prefix="matched")
    row = export_db.create_export_sync(project_id, url, path, mix_version["id"], True, "mp3", export_db.MATCHED)
    provenance.note(project_id, "export", row["id"], "reference_master")
    return {"export_id": row["id"], "audio_url": url, "kind": "matched", "waveform": waveform(arr) if arr is not None else []}


async def run_matched_job(job_id: str, project_id: str, mix_version_id: str, reference: bytes, ref_ext: str) -> None:
    from app.services.jobs.mix_runner import layers_for
    from app.services.remote.spaces import RemoteUnavailable

    try:
        await jobs_db.mark_processing(job_id)
        version = await mix_db.get_mix_version(mix_version_id)
        if not version:
            await jobs_db.mark_failed(job_id, "That mix isn't ready yet.")
            return
        layers = await layers_for(project_id, version)
        result = await run_heavy(_matched_sync, project_id, version, layers, reference, ref_ext)
        await jobs_db.mark_complete(job_id, result)
    except RemoteUnavailable as e:
        await jobs_db.mark_failed(job_id, e.plain)
    except Exception as exc:  # noqa: BLE001
        await jobs_db.mark_failed(job_id, "I couldn't match it to that song just now. Your own finish is safe. Want to try again?")
        raise exc
