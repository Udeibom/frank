"""
Add an atmosphere to the song (frankenstein spec 14, requirement 3.7): a recorded sound from Freesound, or one made
from the song's feeling words by Stable Audio 3 Small on the frank-hands Space. It becomes one named layer in the
mix (mix_params.atmosphere), so a new mix version is rendered and the old one is kept; "take it out" is one switch.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.db import jobs as jobs_db
from app.db import mix as mix_db
from app.db import projects as projects_db
from app.services import provenance
from app.services.jobs import mix_runner
from app.services.storage.files import upload_audio

log = logging.getLogger("frank.atmosphere")


async def _feeling_words(project_id: str) -> list[str]:
    from app.services.song import record as song_record

    words: list[str] = []
    feeling = await song_record.active_facet(project_id, "feeling") or {}
    words += [str(w) for w in feeling.get("words", []) + feeling.get("loved_qualities", [])]
    intent = await song_record.active_facet(project_id, "intent") or {}
    if intent.get("text"):
        words.append(str(intent["text"]))
    return words


def _from_freesound(words: list[str]) -> Optional[tuple[bytes, str, str, Optional[str]]]:
    from app.services.sounds import freesound

    if not freesound.available():
        return None
    sound = freesound.pick(words)
    if not sound:
        return None
    return freesound.fetch(sound), "atmosphere_freesound", f"Atmosphere: {sound['name']}", sound["attribution"]


def _from_hands(words: list[str]) -> Optional[tuple[bytes, str, str, Optional[str]]]:
    from app.services.remote import spaces

    prompt = "ambient atmosphere, no melody, no drums: " + ", ".join(words[:6])
    try:
        out = spaces.call("hands", "/ambience", prompt, 20.0, timeout=300)
        return spaces.read_file(out), "atmosphere_generated", "Atmosphere: made from your words", None
    except spaces.RemoteUnavailable:
        return None


async def run_atmosphere_job(job_id: str, project_id: str, source: str, words: Optional[list[str]], level_db: float) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        words = words or await _feeling_words(project_id) or ["quiet room"]
        got = None
        order = [_from_freesound, _from_hands] if source != "generated" else [_from_hands, _from_freesound]
        for fn in order:
            got = await asyncio.to_thread(fn, words)
            if got:
                break
        if not got:
            await jobs_db.mark_failed(job_id, "I couldn't find or make a sound for that just now. Want to describe the place in a few words instead?")
            return
        audio, organ, plain, attribution = got
        url = await asyncio.to_thread(upload_audio, "mixes", audio, "mp3", "atmosphere")
        state = await projects_db.get_project_active_state(project_id) or {}
        current = await mix_db.get_mix_version(state["active_mix_id"]) if state.get("active_mix_id") else None
        params = dict((current or {}).get("params") or {})
        params["atmosphere"] = {"url": url, "enabled": True, "level_db": level_db, "plain": plain,
                                "organ": organ, "attribution": attribution}
        await mix_runner.run_mix_job(job_id, project_id, params, "preview")
        state = await projects_db.get_project_active_state(project_id) or {}
        await asyncio.to_thread(provenance.note, project_id, "mix", state.get("active_mix_id"), organ, plain, attribution)
    except Exception as exc:  # noqa: BLE001
        log.warning("atmosphere job failed", exc_info=True)
        await jobs_db.mark_failed(job_id, "I couldn't add that atmosphere just now. Nothing was lost. Want to try again?")
        raise exc
