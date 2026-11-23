"""
How long a stored recording is, without downloading it (core-path spec 15, requirement 3).
ffprobe reads only the file's header over the network; the address is signed first, like every audio fetch.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Optional

log = logging.getLogger("frank.duration")


def seconds_of(url: Optional[str]) -> float:
    """Length in seconds, or 0.0 when it cannot be told (the caller then plans as before)."""
    if not url:
        return 0.0
    try:
        from app.services.storage.signing import sign_response_json

        signed = sign_response_json({"u": url})["u"]
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", signed], capture_output=True, text=True, timeout=60)
        return max(0.0, float(r.stdout.strip() or 0.0))
    except Exception:  # noqa: BLE001
        log.warning("could not measure a recording's length", exc_info=True)
        return 0.0


async def active_voice_seconds(project_id: str) -> float:
    """How long the song's current vocal is (the best-of version, else the chosen recording)."""
    import asyncio

    from app.db import projects as projects_db
    from app.db import voice as voice_db
    from app.services.audio.vocal_resolution import resolve_vocal_url

    try:
        state = await projects_db.get_project_active_state(project_id) or {}
        comp = await voice_db.get_comp(state["active_comp_id"]) if state.get("active_comp_id") else None
        take = await voice_db.get_take(state["active_vocal_id"]) if state.get("active_vocal_id") else None
        url = resolve_vocal_url(comp, take)
    except Exception:  # noqa: BLE001
        return 0.0
    return await asyncio.to_thread(seconds_of, url)
