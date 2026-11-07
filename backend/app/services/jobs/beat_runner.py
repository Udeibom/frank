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

import numpy as np

from app.db import jobs as jobs_db
from app.db import beat as beat_db
from app.db import projects as projects_db
from app.services.storage.files import upload_audio
from app.services.generation import beat as beat_engine
from app.services.generation import renderer
from app.services.generation.renderer import to_mp3_bytes


def _arrangement_params(sections: list[beat_engine.SectionPlan], fp: dict) -> dict:
    """Serialize the arrangement into JSON for beat_versions.params."""
    return {
        "fingerprint": fp,
        "sections": [
            {
                "index": s.index,
                "name": s.name,
                "label": s.label,
                "bars": s.bars,
                "energy": s.energy,
                "density": s.density,
                "layers": s.layers,
            }
            for s in sections
        ],
    }


def _render_and_persist_sync(
    project_id: str, fingerprint: dict, label: str
) -> dict:
    """
    The entire heavy job, run in ONE worker thread: render the beat, encode MP3,
    upload everything, and write the records using the sync Supabase client.

    Keeping all blocking work (CPU render + sync Supabase I/O) inside a single
    thread avoids interleaving sync HTTP calls with the event loop, which was
    causing connection races in the storage client. Returns the version dict.
    """
    sections, mixes, full = beat_engine.render_full_beat(fingerprint)
    fp = beat_engine.fp_utils.normalize(fingerprint)
    return _persist_sync(project_id, sections, mixes, full, fp, label)


def _rerender_and_persist_sync(
    project_id: str,
    sections: list[beat_engine.SectionPlan],
    fp: dict,
    label: str,
) -> dict:
    """Re-render an edited arrangement and persist it, all in one thread."""
    mixes, full = beat_engine.rerender_all(sections, fp)
    return _persist_sync(project_id, sections, mixes, full, fp, label)


def _persist_sync(
    project_id: str,
    sections: list[beat_engine.SectionPlan],
    section_mixes: list[np.ndarray],
    full_audio: np.ndarray,
    fp: dict,
    label: str,
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

    version = beat_db.create_beat_version_sync(
        project_id, render_url, label, _arrangement_params(sections, fp)
    )

    for section, mix in zip(sections, section_mixes):
        section_mp3 = to_mp3_bytes(mix)
        section_url = upload_audio(
            "beats", section_mp3, extension="mp3", name_prefix=f"section-{section.name}"
        )
        beat_db.create_stem_sync(
            project_id, version["id"], "section", section.name, section_url
        )

    return version


async def run_full_beat_job(
    job_id: str, project_id: str, fingerprint: dict
) -> None:
    """Generate a complete beat and make it the active beat version."""
    try:
        await jobs_db.mark_processing(job_id)

        count = await beat_db.count_beat_versions(project_id)
        label = f"Beat v{count + 1}"

        # Entire heavy job (render + encode + upload + records) in one thread
        version = await asyncio.to_thread(
            _render_and_persist_sync, project_id, fingerprint, label
        )

        await projects_db.update_project_active_state(
            project_id, {"active_beat_version_id": version["id"]}
        )

        await jobs_db.mark_complete(
            job_id,
            {"beat_version_id": version["id"], "render_url": version["render_url"], "label": label},
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't build that beat just now — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


async def _load_active_arrangement(project_id: str) -> tuple[list, dict, str]:
    """
    Load the active beat version's arrangement. Returns (sections, fp, label).
    Raises if there is no active beat to edit.
    """
    state = await projects_db.get_project_active_state(project_id)
    version_id = state.get("active_beat_version_id") if state else None
    if not version_id:
        raise ValueError("No active beat to edit")
    version = await beat_db.get_beat_version(version_id)
    sections, fp = beat_engine.sections_from_params(version["params"])
    return sections, fp, version.get("label", "Beat")


async def run_edit_section_job(
    job_id: str,
    project_id: str,
    section_index: int,
    instruction: str | None,
) -> None:
    """
    Apply a plain-language edit to one section and re-render the beat as a NEW
    version (the previous version is preserved, per the versioning principle).
    """
    try:
        await jobs_db.mark_processing(job_id)
        sections, fp, _ = await _load_active_arrangement(project_id)

        for s in sections:
            if s.index == section_index:
                beat_engine.apply_section_instruction(s, instruction, fp)
                break

        count = await beat_db.count_beat_versions(project_id)
        label = f"Beat v{count + 1}"
        version = await asyncio.to_thread(
            _rerender_and_persist_sync, project_id, sections, fp, label
        )
        await projects_db.update_project_active_state(
            project_id, {"active_beat_version_id": version["id"]}
        )
        await jobs_db.mark_complete(
            job_id,
            {"beat_version_id": version["id"], "render_url": version["render_url"], "label": label},
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't make that change — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


async def run_mute_stem_job(
    job_id: str,
    project_id: str,
    stem_type: str,
    section_index: int | None,
) -> None:
    """
    Remove a layer (stem_type) from one section (or all sections if
    section_index is None) and re-render as a new version. Used by
    "remove the keys from the bridge".
    """
    try:
        await jobs_db.mark_processing(job_id)
        sections, fp, _ = await _load_active_arrangement(project_id)

        for s in sections:
            if section_index is None or s.index == section_index:
                if stem_type in s.layers:
                    s.layers.remove(stem_type)

        count = await beat_db.count_beat_versions(project_id)
        label = f"Beat v{count + 1}"
        version = await asyncio.to_thread(
            _rerender_and_persist_sync, project_id, sections, fp, label
        )
        await projects_db.update_project_active_state(
            project_id, {"active_beat_version_id": version["id"]}
        )
        await jobs_db.mark_complete(
            job_id,
            {"beat_version_id": version["id"], "render_url": version["render_url"], "label": label},
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't take that out — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


async def run_add_stem_job(
    job_id: str,
    project_id: str,
    stem_type: str,
    section_index: int | None,
) -> None:
    """
    Add a layer (stem_type) to one section (or all sections if section_index is
    None) and re-render as a new version. Used by "add a bassline", etc.
    """
    try:
        await jobs_db.mark_processing(job_id)
        sections, fp, _ = await _load_active_arrangement(project_id)

        for s in sections:
            if section_index is None or s.index == section_index:
                if stem_type not in s.layers:
                    s.layers.append(stem_type)

        count = await beat_db.count_beat_versions(project_id)
        label = f"Beat v{count + 1}"
        version = await asyncio.to_thread(
            _rerender_and_persist_sync, project_id, sections, fp, label
        )
        await projects_db.update_project_active_state(
            project_id, {"active_beat_version_id": version["id"]}
        )
        await jobs_db.mark_complete(
            job_id,
            {"beat_version_id": version["id"], "render_url": version["render_url"], "label": label},
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't add that in — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc
