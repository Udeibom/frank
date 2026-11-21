"""
Frank listens with more than numbers (frankenstein spec 14, requirement 2.3).

After the Listener has measured the song, a 30-second bounce of the part in question goes to Gemini with the
measurements and what the person said. Gemini's notes come back tagged; a note is "confirmed" only when the
Listener found the same kind of thing. Confirmed notes may steer the refine loop; unconfirmed ones are said as
"I think" and never acted on. Nothing here can fail the listen job.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Optional

from app.db import beat as beat_db
from app.db import mix as mix_db
from app.db import projects as projects_db
from app.services.generation import beat as beat_engine
from app.services.listener.models import FindingsReport, MeasurementReport
from app.services.llm import gemini_media
from app.services.storage.signing import fetch_audio_bytes

log = logging.getLogger("frank.ears")

CLIP_SECONDS = 30.0


def clip_window(sections: list, bpm: float, scope: Optional[list[str]], concern: Optional[str]) -> tuple[float, float]:
    """Where to listen: the first section named in scope (or the concern), else the first chorus, else 20 s in."""
    if not sections or bpm <= 0:
        return 20.0, CLIP_SECONDS
    bar = 4 * 60.0 / bpm
    wanted = [s.lower() for s in (scope or [])]
    if concern:
        wanted += [n for n in ("chorus", "verse", "bridge", "intro", "outro") if n in concern.lower()]
    wanted.append("chorus")
    t = 0.0
    starts = []
    for s in sorted(sections, key=lambda x: x.index):
        starts.append((s.name.lower(), t, s.bars * bar))
        t += s.bars * bar
    for w in wanted:
        for name, at, length in starts:
            if name == w:
                return max(0.0, at - 2.0), min(CLIP_SECONDS, length + 4.0)
    return min(20.0, max(0.0, t - CLIP_SECONDS)), CLIP_SECONDS


def _clip_mp3(audio: bytes, start: float, length: float) -> bytes:
    r = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", "pipe:0",
         "-ac", "1", "-b:a", "96k", "-f", "mp3", "pipe:1"],
        input=audio, capture_output=True, timeout=60, check=True,
    )
    return r.stdout


def summary_numbers(report: MeasurementReport) -> dict:
    """A compact view of the measurements for the prompt (the full report is too long and too technical)."""
    names = {s.index: s.name for s in report.sections}
    out: dict = {}
    for k, v in report.values.items():
        parts = k.split(".")
        if parts[0] == "section" and len(parts) == 3 and parts[1].isdigit():
            k = f"{names.get(int(parts[1]), 'section')} {int(parts[1]) + 1} {parts[2]}"
        out[k] = round(v, 2)
        if len(out) >= 60:
            break
    return out


async def hear(project_id: str, report: MeasurementReport, found: FindingsReport,
               scope: Optional[list[str]] = None, concern: Optional[str] = None) -> Optional[dict]:
    try:
        state = await projects_db.get_project_active_state(project_id) or {}
        mix = await mix_db.get_mix_version(state["active_mix_id"]) if state.get("active_mix_id") else None
        beat = await beat_db.get_beat_version(state["active_beat_version_id"]) if state.get("active_beat_version_id") else None
        url = (mix or {}).get("render_url") or (beat or {}).get("render_url")
        if not url:
            return None
        sections, fp = beat_engine.sections_from_params(beat["params"]) if beat else ([], {})
        start, length = clip_window(sections, float(fp.get("tempo_bpm") or 0), scope, concern)
        audio = await asyncio.to_thread(fetch_audio_bytes, url)
        clip = await asyncio.to_thread(_clip_mp3, audio, start, length)
        del audio
        numbers = summary_numbers(report)
        numbers["what_frank_found"] = [f.plain for f in found.findings]
        heard = await asyncio.to_thread(gemini_media.listen, clip, "audio/mp3", numbers, concern or "")
        if heard is None:
            return None
        notes = gemini_media.confirm(heard, {f.id for f in found.findings})
        return {"heard": heard.heard, "notes": notes, "from_seconds": round(start, 1), "seconds": round(length, 1)}
    except Exception:  # noqa: BLE001
        log.warning("listening with Gemini failed", exc_info=True)
        return None


async def style_check(project_id: str) -> Optional[dict]:
    """Styles and moods the render sounds like (frank-ears), and a finding when they drift from the brief."""
    from app.db import feel as feel_db
    from app.services.listener import style
    from app.services.remote import organs

    try:
        state = await projects_db.get_project_active_state(project_id) or {}
        mix = await mix_db.get_mix_version(state["active_mix_id"]) if state.get("active_mix_id") else None
        beat = await beat_db.get_beat_version(state["active_beat_version_id"]) if state.get("active_beat_version_id") else None
        url = (mix or {}).get("render_url") or (beat or {}).get("render_url")
        if not url:
            return None
        audio = await asyncio.to_thread(fetch_audio_bytes, url)
        clip = await asyncio.to_thread(_clip_mp3, audio, 10.0, 60.0)
        del audio
        got = await asyncio.to_thread(organs.try_, organs.labels, clip, "mp3")
        if not got:
            return None
        fp = ((await feel_db.get_latest_fingerprint(project_id)) or {}).get("fingerprint") or {}
        f = style.finding(list(fp.get("genre_proximity") or []), got.get("styles", []), got.get("moods", []))
        return {"styles": got.get("styles", []), "moods": got.get("moods", []), "finding": f.model_dump() if f else None}
    except Exception:  # noqa: BLE001
        log.warning("style check failed", exc_info=True)
        return None
