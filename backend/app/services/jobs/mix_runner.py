"""
Mix rendering job runner.

Loads the active vocal (take or comp), the active beat, and the harmony (if any),
renders them into one mix with the given params, uploads an MP3, and records a
mix version. Preview renders are lighter (lower bitrate); full renders are 320k.

All fetch + render + upload + record runs in one worker thread, matching the
pattern established for beats, to keep sync Supabase I/O off the event loop.
"""

from __future__ import annotations
import asyncio
import httpx

from app.db import jobs as jobs_db
from app.db import mix as mix_db
from app.db import voice as voice_db
from app.db import beat as beat_db
from app.db import projects as projects_db
from app.services.storage.files import upload_audio
from app.services.audio import mixing
from app.services.audio.vocal_resolution import resolve_vocal_url


def _fetch(url: str | None) -> bytes | None:
    if not url:
        return None
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def _summarize_params(mix_params: dict) -> str:
    """A plain-language label summarizing what this mix emphasizes."""
    bits: list[str] = []
    v = mix_params.get("vocal_gain_db", 0.0)
    b = mix_params.get("beat_gain_db", -6.0)
    if v - b > 7:
        bits.append("vocals forward")
    elif b - v > -3:
        bits.append("beat forward")
    for e in mix_params.get("vocal_effects", []):
        bits.append({"warm": "warmer", "space": "more space", "smooth": "smoother"}.get(e, e))
    for e in mix_params.get("beat_effects", []):
        bits.append({"clean_low": "cleaner low end"}.get(e, e))
    return ", ".join(bits) if bits else "balanced"


def _render_sync(
    layers: dict,
    mix_params: dict,
    quality: str,
) -> bytes:
    """Fetch layers, render, encode. Returns MP3 bytes. No DB writes."""
    vocal = _fetch(layers["vocal_url"])
    beat = _fetch(layers["beat_url"])
    harmony = _fetch(layers["harmony_url"])

    mix = mixing.render_mix(
        vocal,
        beat,
        harmony,
        mix_params,
        beat_sections=layers.get("beat_sections"),
        beat_bpm=layers.get("beat_bpm", 90),
    )
    # Preview is light (spec R4: 64kbps); full export quality is 320kbps.
    bitrate = "320k" if quality == "full" else "64k"
    return mixing.to_mp3_bytes(mix, bitrate=bitrate)


def _render_and_persist_sync(
    project_id: str,
    layers: dict,
    mix_params: dict,
    quality: str,
) -> dict:
    """Render + upload + create a mix version. One worker thread."""
    mp3 = _render_sync(layers, mix_params, quality)
    render_url = upload_audio("mixes", mp3, extension="mp3", name_prefix=f"mix-{quality}")

    # Label carries a plain-language summary of what this mix emphasizes (R3)
    count = mix_db.count_mix_versions_sync(project_id)
    summary = _summarize_params(mix_params)
    label = f"Mix v{count + 1} — {summary}"

    version = mix_db.create_mix_version_sync(
        project_id, render_url, label, mix_params
    )
    return {"mix_version_id": version["id"], "render_url": render_url, "label": label}


def _render_preview_sync(layers: dict, mix_params: dict) -> dict:
    """
    Render a throwaway preview (e.g. 'hear it with my vocal') WITHOUT creating a
    mix version or touching active_mix_id. Returns just the audio URL.
    """
    mp3 = _render_sync(layers, mix_params, "preview")
    render_url = upload_audio("mixes", mp3, extension="mp3", name_prefix="preview")
    return {"render_url": render_url}


async def _resolve_layers(project_id: str) -> dict:
    """
    Find the active vocal, beat, and harmony audio URLs plus the beat's section
    timing (so per-section gain can be applied at render time).
    Returns a dict: { vocal_url, beat_url, harmony_url, beat_sections, beat_bpm }.
    """
    state = await projects_db.get_project_active_state(project_id)
    vocal_url = beat_url = harmony_url = None
    beat_sections: list[dict] = []
    beat_bpm = 90

    if state:
        # Active vocal: the pointers decide (see vocal_resolution.py), and the
        # comp is fetched by its own id, not "newest comp".
        comp_id = state.get("active_comp_id")
        vocal_id = state.get("active_vocal_id")
        active_comp = await voice_db.get_comp(comp_id) if comp_id else None
        active_take = await voice_db.get_take(vocal_id) if vocal_id else None
        vocal_url = resolve_vocal_url(active_comp, active_take)

        beat_vid = state.get("active_beat_version_id")
        if beat_vid:
            bv = await beat_db.get_beat_version(beat_vid)
            if bv:
                beat_url = bv.get("render_url")
                params = bv.get("params") or {}
                beat_sections = params.get("sections", [])
                fp = params.get("fingerprint") or {}
                beat_bpm = int(fp.get("tempo_bpm", 90) or 90)

    # Harmony: the most recent take labeled as a harmony, if any
    takes = await voice_db.list_takes(project_id)
    for t in takes:
        if (t.get("label") or "").lower().startswith("harmony"):
            harmony_url = t["audio_url"]
            break

    return {
        "vocal_url": vocal_url,
        "beat_url": beat_url,
        "harmony_url": harmony_url,
        "beat_sections": beat_sections,
        "beat_bpm": beat_bpm,
    }


async def run_mix_job(
    job_id: str, project_id: str, mix_params: dict, quality: str
) -> None:
    try:
        await jobs_db.mark_processing(job_id)

        layers = await _resolve_layers(project_id)
        if not layers["vocal_url"] and not layers["beat_url"]:
            await jobs_db.mark_failed(
                job_id, "There's nothing to mix yet — record a vocal or build a beat first."
            )
            return

        result = await asyncio.to_thread(
            _render_and_persist_sync, project_id, layers, mix_params, quality
        )

        await projects_db.update_project_active_state(
            project_id, {"active_mix_id": result["mix_version_id"]}
        )
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't put the mix together — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


async def run_vocal_preview_job(
    job_id: str, project_id: str, mix_params: dict
) -> None:
    """
    "Hear it with my vocal" (Beat Room) — a throwaway preview mix of the active
    beat + vocal. Does NOT create a mix version or change active_mix_id; the job
    result just carries the audio URL to play. Keeps the real mix list clean.
    """
    try:
        await jobs_db.mark_processing(job_id)
        layers = await _resolve_layers(project_id)
        if not layers["vocal_url"] or not layers["beat_url"]:
            await jobs_db.mark_failed(
                job_id, "Need both a beat and a vocal to hear them together."
            )
            return
        result = await asyncio.to_thread(_render_preview_sync, layers, mix_params)
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't play that back — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc
