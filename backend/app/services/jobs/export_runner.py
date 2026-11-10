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


def _export_sync(
    project_id: str, mix_version_id: str, mix_url: str, apply_mastering: bool
) -> dict:
    """
    Fetch the mix, master if requested, upload the final MP3, record it.
    Dedup first: if an export for this exact mix version + mastering choice
    already exists, reuse it (download stays instant, no duplicate rows).
    """
    existing = export_db.find_existing_export_sync(
        project_id, mix_version_id, apply_mastering
    )
    if existing:
        return {
            "export_id": existing["id"],
            "audio_url": existing["audio_url"],
            "reused": True,
        }

    mix_bytes = _fetch(mix_url)
    final_mp3 = mastering.master(mix_bytes) if apply_mastering else _reencode_320(mix_bytes)
    storage_path, audio_url = upload_audio_with_path(
        "exports", final_mp3, extension="mp3", name_prefix="export"
    )
    record = export_db.create_export_sync(
        project_id,
        audio_url,
        storage_path,
        mix_version_id,
        apply_mastering,
        "mp3",
        "320k",
    )
    return {"export_id": record["id"], "audio_url": audio_url, "reused": False}


async def run_export_job(
    job_id: str, project_id: str, mix_version_id: str, apply_mastering: bool
) -> None:
    try:
        await jobs_db.mark_processing(job_id)

        version = await mix_db.get_mix_version(mix_version_id)
        if not version or not version.get("render_url"):
            await jobs_db.mark_failed(
                job_id, "That mix isn't ready to export yet."
            )
            return

        result = await asyncio.to_thread(
            _export_sync,
            project_id,
            mix_version_id,
            version["render_url"],
            apply_mastering,
        )
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't finish your song just then — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc
