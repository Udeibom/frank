"""
Beat generation job runners.

Three kinds of background work, all CPU-bound (run via asyncio.to_thread):
  - full beat generation from a fingerprint
  - regenerating a single section (keeps the rest of the beat)
  - adding one stem/layer to the beat

Each produces audio, uploads stems + an assembled render to storage, and writes
the version/stem records. The arrangement (section labels, order, bars, layers)
is stored in beat_versions.params so the frontend can draw the timeline and so
sections can be addressed individually later.
"""

from __future__ import annotations
import asyncio
import json
from dataclasses import replace

import numpy as np

from app.db import jobs as jobs_db
from app.services.jobs.heavy import HEAVY, log_memory
from app.db import beat as beat_db
from app.db import projects as projects_db
from app.services.storage.files import upload_audio
from app.services.generation import beat as beat_engine
from app.services.generation import renderer
from app.services.generation.renderer import to_mp3_bytes
from app.services.generation import lead as lead_mod
from app.services.generation.rng import derive_seed
from app.services.intake.melody import CONFIDENT
from app.services.song import record as song_record
from app.services.generation.styles import pick_style


# One beat is built at a time. A render holds a large SoundFont and several minutes of audio in memory,
# so several at once could use more than a small server has. Others simply wait their turn.
_one_at_a_time = HEAVY          # shared with every heavy job (heavy.py)


def _lead_used(version: dict) -> bool:
    """Whether the beat that was just made plays the person's own tune."""
    return bool(((version.get("params") or {}).get("lead_info") or {}).get("used"))


def _arrangement_params(
    sections: list[beat_engine.SectionPlan], fp: dict, seed: int, lead: lead_mod.Lead | None = None
) -> dict:
    """Serialize the arrangement into JSON for beat_versions.params."""
    style = pick_style(fp)
    return {
        "fingerprint": fp,
        "engine": beat_engine.ENGINE_VERSION,
        "mix_chain": True,
        "seed": seed,
        "lead": lead.to_dict() if lead else None,
        "lead_info": beat_engine.lead_info(sections, lead),
        "style": style.name,
        "unsupported_hints": style.unsupported,
        "sections": [
            {
                "index": s.index,
                "name": s.name,
                "label": s.label,
                "bars": s.bars,
                "energy": s.energy,
                "density": s.density,
                "layers": s.layers,
                "uid": s.uid if s.uid is not None else s.index,
                "parts": s.parts,
            }
            for s in sections
        ],
    }


def _render_and_persist_sync(
    project_id: str, fingerprint: dict, label: str, seed: int, lead: lead_mod.Lead | None = None
) -> dict:
    """
    The entire heavy job, run in ONE worker thread: render the beat, encode MP3,
    upload everything, and write the records using the sync Supabase client.

    Keeping all blocking work (CPU render + sync Supabase I/O) inside a single
    thread avoids interleaving sync HTTP calls with the event loop, which was
    causing connection races in the storage client. Returns the version dict.
    """
    log_memory("beat: start render")
    sections, mixes, full = beat_engine.render_full_beat(fingerprint, seed, lead)
    log_memory("beat: rendered")
    fp = beat_engine.fp_utils.normalize(fingerprint)
    return _persist_sync(project_id, sections, mixes, full, fp, label, seed, lead)


def _rerender_and_persist_sync(
    project_id: str,
    sections: list[beat_engine.SectionPlan],
    fp: dict,
    label: str,
    seed: int,
    lead: lead_mod.Lead | None = None,
    changes: list[str] | None = None,
    operations: list[dict] | None = None,
) -> dict:
    """Re-render an edited arrangement and persist it, all in one thread."""
    mixes, full = beat_engine.rerender_all(sections, fp, seed, lead)
    return _persist_sync(project_id, sections, mixes, full, fp, label, seed, lead, changes, operations)


def _persist_sync(
    project_id: str,
    sections: list[beat_engine.SectionPlan],
    section_mixes: list[np.ndarray],
    full_audio: np.ndarray,
    fp: dict,
    label: str,
    seed: int,
    lead: lead_mod.Lead | None = None,
    changes: list[str] | None = None,
    operations: list[dict] | None = None,
) -> dict:
    """
    Upload the assembled render + one mixed file per section, and write records.
    Fully synchronous — runs inside a worker thread via asyncio.to_thread.

    We store a mixed file PER SECTION (not per-stem-per-section). The section's
    layer list lives in params, so layer toggles re-render just that section.
    This keeps uploads and memory bounded (≈8 section files, not ~30 stems).
    """
    full_mp3 = to_mp3_bytes(full_audio)
    render_url = upload_audio("beats", full_mp3, extension="mp3", name_prefix="beat")

    params = _arrangement_params(sections, fp, seed, lead)
    if changes:
        params["changes"] = changes            # what this version changed, in plain words
        params["operations"] = operations or []
    version = beat_db.create_beat_version_sync(project_id, render_url, label, params)

    for section, mix in zip(sections, section_mixes):
        section_mp3 = to_mp3_bytes(mix)
        section_url = upload_audio(
            "beats", section_mp3, extension="mp3", name_prefix=f"section-{section.name}"
        )
        beat_db.create_stem_sync(
            project_id, version["id"], "section", section.name, section_url
        )

    return version


async def _fingerprint_and_lead(project_id: str, fingerprint: dict) -> tuple[dict, lead_mod.Lead | None]:
    """
    If the person has confirmed a hummed tune, the beat is built around it. The speed only comes from
    the hum when nothing else has settled it (a value that is already in the fingerprint is never
    replaced); the key always comes from the tune, because the tune is what has to fit.
    A problem reading the tune never stops a beat from being built.
    """
    try:
        found = await song_record.active_melody(project_id)
    except Exception:  # noqa: BLE001
        return fingerprint, None
    if not found:
        return fingerprint, None
    version_id, content = found
    lead = lead_mod.from_sketch(content, source=version_id)
    if lead is None:
        return fingerprint, None
    fp = dict(fingerprint or {})
    key, changed = lead_mod.choose_key(lead, fp.get("key") or None)
    if key:
        lead = replace(lead, key=key)
        fp["key"] = key                   # the beat's real key, so everything downstream agrees with it
    if changed:
        fp["key_from_tune"] = True
    try:
        if "tempo_bpm" not in fp and float(content.get("tempo_confidence", 0)) >= CONFIDENT:
            fp["tempo_bpm"] = int(round(float(content["tempo_bpm"])))
    except (KeyError, TypeError, ValueError, OverflowError):
        fp.pop("tempo_bpm", None)           # a missing or impossible speed is simply not used
    return fp, lead


async def run_full_beat_job(
    job_id: str, project_id: str, fingerprint: dict
) -> None:
    """Generate a complete beat and make it the active beat version."""
    try:
        await jobs_db.mark_processing(job_id)

        count = await beat_db.count_beat_versions(project_id)
        label = f"Beat v{count + 1}"
        fingerprint, lead = await _fingerprint_and_lead(project_id, fingerprint)
        # A new version gets a new seed, so asking for another one gives a different song, while
        # the same fingerprint and the same count always give the same song (repeatable).
        seed = derive_seed(json.dumps(fingerprint, sort_keys=True, default=str), count)

        # Entire heavy job (render + encode + upload + records) in one thread
        async with _one_at_a_time:
            version = await asyncio.to_thread(
                _render_and_persist_sync, project_id, fingerprint, label, seed, lead
            )

        await projects_db.update_project_active_state(
            project_id, {"active_beat_version_id": version["id"]}
        )

        await jobs_db.mark_complete(
            job_id,
            {"beat_version_id": version["id"], "render_url": version["render_url"], "label": label, "lead_used": _lead_used(version)},
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't build that beat just now — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


async def _load_active_arrangement(project_id: str) -> tuple[list, dict, int, lead_mod.Lead | None]:
    """
    Load the active beat version's arrangement. Returns (sections, fp, seed, lead).
    Raises if there is no active beat to edit.
    """
    state = await projects_db.get_project_active_state(project_id)
    version_id = state.get("active_beat_version_id") if state else None
    if not version_id:
        raise ValueError("No active beat to edit")
    version = await beat_db.get_beat_version(version_id)
    sections, fp = beat_engine.sections_from_params(version["params"])
    seed = version["params"].get("seed")
    if not isinstance(seed, int):
        seed = beat_engine.default_seed(fp)   # beats saved before seeds existed
    stored = beat_engine.lead_from_params(version["params"])
    fp, lead = await _follow_newest_tune(project_id, fp, stored)
    return sections, fp, seed, lead


async def _follow_newest_tune(
    project_id: str, fp: dict, stored: lead_mod.Lead | None
) -> tuple[dict, lead_mod.Lead | None]:
    """
    An edit re-renders the saved arrangement. If the person has confirmed a DIFFERENT tune since that beat
    was made, the edit follows the newer tune (the last thing they confirmed is what they want to hear),
    instead of quietly keeping the old one. If nothing newer exists, or it cannot be read, the saved tune stays.
    """
    new_fp, newest = await _fingerprint_and_lead(project_id, fp)
    if newest is None:
        return fp, stored
    if stored is not None and stored.source == newest.source:
        return fp, stored
    return new_fp, newest


async def run_operations_job(job_id: str, project_id: str, operations: list[dict]) -> None:
    """
    Apply typed edit operations (generation/ops.py) to the active beat and render the result as a NEW version.
    The previous version is kept. The job result says, in plain words, exactly what changed. An operation that
    cannot be applied fails the job with its plain reason and creates nothing.
    """
    from app.services.generation import ops as ops_mod

    try:
        await jobs_db.mark_processing(job_id)
        sections, fp, seed, lead = await _load_active_arrangement(project_id)
        try:
            sections, seed, changes = ops_mod.apply_operations(sections, seed, operations)
        except ops_mod.OpError as exc:
            await jobs_db.mark_failed(job_id, str(exc))
            return
        count = await beat_db.count_beat_versions(project_id)
        label = f"Beat v{count + 1}"
        async with _one_at_a_time:
            version = await asyncio.to_thread(
                _rerender_and_persist_sync, project_id, sections, fp, label, seed, lead, changes, operations
            )
        await projects_db.update_project_active_state(project_id, {"active_beat_version_id": version["id"]})
        await jobs_db.mark_complete(
            job_id,
            {"beat_version_id": version["id"], "render_url": version["render_url"], "label": label,
             "lead_used": _lead_used(version), "changes": changes},
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "Frank couldn't make that change — want to try again?")
        except Exception:  # noqa: BLE001
            pass
        raise exc
