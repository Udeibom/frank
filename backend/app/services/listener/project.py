"""
Listener, project level: load a project's active audio, measure it, cache by audio version id (spec 03, req 4, 5).
The only write is the cache row. No version, file or active pointer is ever changed.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from app.db import beat as beat_db
from app.db import mix as mix_db
from app.db import projects as projects_db
from app.db import voice as voice_db
from app.db.client import get_supabase
from app.services.audio.convert import to_wav
from app.services.audio.pitch import detect_pitch_contour
from app.services.audio.vocal_resolution import resolve_vocal_url
from app.services.generation import beat as beat_engine
from app.services.listener import service
from app.services.listener.models import MeasurementReport, Unmeasured
from app.services.storage.signing import fetch_audio_bytes

log = logging.getLogger(__name__)
Progress = Optional[Callable[[str], Awaitable[None]]]


def cache_key(parts: dict[str, str], scope: Optional[list[str]]) -> str:
    ids = "|".join(f"{k}:{parts[k]}" for k in sorted(parts))
    return f"v{service.LISTENER_VERSION}|{ids}|scope:{','.join(sorted(scope)) if scope else 'all'}"


def _cache_get(key: str) -> Optional[MeasurementReport]:
    try:
        rows = get_supabase().table("listener_cache").select("report").eq("audio_version_id", key).limit(1).execute().data
        return MeasurementReport.model_validate(rows[0]["report"]) if rows else None
    except Exception:  # noqa: BLE001  a missing cache never stops listening
        log.warning("listener cache read failed", exc_info=True)
        return None


def _cache_put(key: str, report: MeasurementReport) -> None:
    try:
        get_supabase().table("listener_cache").upsert(
            {"audio_version_id": key, "kind": "report", "report": report.model_dump()}
        ).execute()
    except Exception:  # noqa: BLE001
        log.warning("listener cache write failed", exc_info=True)


async def _say(progress: Progress, text: str) -> None:
    if progress:
        await progress(text)


async def measure_song(project_id: str, scope: Optional[list[str]] = None, progress: Progress = None) -> MeasurementReport:
    """Measure the project's active beat, vocal and mix. Same audio versions + same scope = cached report."""
    state = await projects_db.get_project_active_state(project_id) or {}
    beat_id, mix_id = state.get("active_beat_version_id"), state.get("active_mix_id")
    take = await voice_db.get_take(state["active_vocal_id"]) if state.get("active_vocal_id") else None
    comp = await voice_db.get_comp(state["active_comp_id"]) if state.get("active_comp_id") else None
    vocal_url = resolve_vocal_url(comp, take)
    mix = await mix_db.get_mix_version(mix_id) if mix_id else None
    beat = await beat_db.get_beat_version(beat_id) if beat_id else None

    versions: dict[str, str] = {}
    if beat:
        versions["beat"] = beat["id"]
    if vocal_url:
        versions["vocal"] = (comp or take or {}).get("id", vocal_url)
    if mix:
        versions["mix"] = mix["id"]
    if not versions:
        rep = MeasurementReport(scope=scope)
        rep.unmeasured.append(Unmeasured(id="song", why="There's nothing to listen to yet: no beat, vocal or mix."))
        return rep

    key = cache_key(versions, scope)
    cached = await asyncio.to_thread(_cache_get, key)
    if cached is not None:
        return cached

    await _say(progress, "Listening closely...")
    beat_audio = mix_audio = vocal_audio = None
    sections, fp, bpm, score = [], {}, 0.0, None
    if beat:
        sections, fp = beat_engine.sections_from_params(beat["params"])
        bpm = float(fp["tempo_bpm"])
        if beat.get("render_url"):
            beat_audio = service.decode(await asyncio.to_thread(fetch_audio_bytes, beat["render_url"]))
        seed = beat["params"].get("seed")
        seed = seed if isinstance(seed, int) else beat_engine.default_seed(fp)
        lead = beat_engine.lead_from_params(beat["params"])
        await _say(progress, "Reading the notes of the song...")
        score = await asyncio.to_thread(service.score_facts, sections, fp, seed, lead)
    contour = None
    if vocal_url:
        await _say(progress, "Listening to your voice...")
        raw = await asyncio.to_thread(fetch_audio_bytes, vocal_url)
        vocal_audio = service.decode(raw)
        wav = await asyncio.to_thread(to_wav, raw, "webm")
        contour = await asyncio.to_thread(detect_pitch_contour, wav)
    if mix and mix.get("render_url"):
        mix_audio = service.decode(await asyncio.to_thread(fetch_audio_bytes, mix["render_url"]))

    await _say(progress, "Comparing the parts...")
    report = await asyncio.to_thread(
        service.measure_audio, sections, bpm,
        beat=beat_audio, vocal=vocal_audio, mix=mix_audio, sr=service.LISTEN_SR, key=fp.get("key"), score=score, scope=scope, vocal_contour=contour,
    )
    report.audio_versions = versions
    await asyncio.to_thread(_cache_put, key, report)
    return report
