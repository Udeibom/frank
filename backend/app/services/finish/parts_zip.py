"""
"Download separate parts" (finish-and-intent spec 11, requirement 5.1): one zip with a file per part of the music
(made from the saved plan when needed), the voice in use and the harmony, named in plain words.
"""
from __future__ import annotations

import io
import zipfile

PLAIN_FILE = {"drums": "Drums", "bass": "Bass", "keys": "Keys", "melody": "Tune", "pad": "Soft background",
              "strings": "Strings", "arp": "Running pattern", "extras": "Little touches"}


def file_name(part: str) -> str:
    return f"{PLAIN_FILE.get(part, part.capitalize())}.mp3"


def build_zip(files: list[tuple[str, bytes]], title: str) -> bytes:
    """Stored without recompression (the files are already MP3)."""
    buf = io.BytesIO()
    folder = "".join(c for c in title if c.isalnum() or c in " -_").strip() or "My song"
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        for name, data in files:
            z.writestr(f"{folder}/{name}", data)
        z.writestr(f"{folder}/README.txt", "Each file is one part of your song, all the same length, starting together.\n"
                   "Drop them into any music app and they line up.\n")
    return buf.getvalue()


async def run_parts_zip_job(job_id: str, project_id: str) -> None:
    import asyncio

    from app.db import jobs as jobs_db
    from app.db import projects as projects_db
    from app.services.jobs import beat_runner, mix_runner
    from app.services.storage.files import upload_audio_with_path
    from app.services.storage.signing import fetch_audio_bytes

    try:
        await jobs_db.mark_processing(job_id)
        layers = await mix_runner._resolve_layers(project_id)
        bvid = layers.get("beat_version_id")
        if not bvid and not layers.get("vocal_url"):
            await jobs_db.mark_failed(job_id, "There's nothing to download yet. Build a beat or record a take first.")
            return
        parts = await beat_runner.ensure_parts(project_id, bvid) if bvid else {}

        def make() -> bytes:
            files = [(file_name(p), fetch_audio_bytes(u, 60)) for p, u in sorted(parts.items())]
            if layers.get("vocal_url"):
                voice = fetch_audio_bytes(layers["vocal_url"], 60)
                if not layers["vocal_url"].split("?")[0].endswith(".mp3"):
                    from app.services.jobs.voice_runner import _to_mp3

                    voice = _to_mp3(voice)          # a WAV voice would push the zip past the 50 MB upload limit
                files.append(("Your voice.mp3", voice))
            if layers.get("harmony_url"):
                files.append(("Harmony.mp3", fetch_audio_bytes(layers["harmony_url"], 60)))
            return build_zip(files, project.get("title") or "My song")

        project = await projects_db.get_project(project_id) or {}
        data = await asyncio.to_thread(make)
        _, url = await asyncio.to_thread(upload_audio_with_path, "exports", data, "zip", "parts")
        await jobs_db.mark_complete(job_id, {"zip_url": url, "parts": sorted(parts), "bytes": len(data)})
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "Frank couldn't put the separate parts together. Want to try again?")
        except Exception:  # noqa: BLE001
            pass
        raise exc
