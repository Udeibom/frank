"""
Refine loop jobs (spec 08).

run_propose_job: listen to the song, then turn the findings into two or three directions and store the proposal.
run_preview_job: play one direction. The change is applied to a COPY of the plan or mix settings, only the
affected sections are rendered, and the file goes to a preview name. No version row and no active pointer is
ever written here (spec 08 property 1); the "before" is cut from the current song at the same place.
"""
from __future__ import annotations

from app.services import provenance

import asyncio
import logging
import os
import subprocess
import tempfile
from typing import Any, Optional

import numpy as np

from app.db import beat as beat_db
from app.db import jobs as jobs_db
from app.db import mix as mix_db
from app.db import projects as projects_db
from app.db import refine as refine_db
from app.services.generation import beat as beat_engine
from app.services.generation import ops as ops_mod
from app.services.generation.renderer import SAMPLE_RATE, to_mp3_bytes
from app.services.jobs.heavy import HEAVY, log_memory
from app.services.jobs.listen_runner import _progress
from app.services.listener import findings as findings_mod
from app.services.listener import project as listen_project
from app.services.refine import propose as propose_mod
from app.services.refine.models import Direction
from app.services.storage.files import upload_audio
from app.services.storage.signing import fetch_audio_bytes

log = logging.getLogger(__name__)


# ── what the directions are built on ─────────────────────────────────────

async def load_basis(project_id: str) -> dict[str, Any]:
    """The active beat plan and mix settings a proposal is built on (either may be missing)."""
    from app.routers.mix import DEFAULT_MIX_PARAMS
    from app.services.jobs import beat_runner

    state = await projects_db.get_project_active_state(project_id) or {}
    basis: dict[str, Any] = {"beat_id": state.get("active_beat_version_id"), "mix_id": state.get("active_mix_id"),
                             "sections": [], "seed": 0, "fp": {}, "lead": None, "mix_params": None, "beat": None}
    if basis["beat_id"]:
        try:
            sections, fp, seed, lead = await beat_runner._load_active_arrangement(project_id)
            basis.update(sections=sections, fp=fp, seed=seed, lead=lead, beat=await beat_db.get_beat_version(basis["beat_id"]))
        except Exception:  # noqa: BLE001  a beat that cannot be read leaves only mix directions
            log.warning("refine: could not read the active beat", exc_info=True)
    if basis["mix_id"]:
        mv = await mix_db.get_mix_version(basis["mix_id"])
        basis["mix_params"] = {**DEFAULT_MIX_PARAMS, **((mv or {}).get("mix_params") or {})}
        basis["mix"] = mv
    elif state.get("active_vocal_id") or state.get("active_comp_id"):
        basis["mix_params"] = dict(DEFAULT_MIX_PARAMS)
        basis["mix"] = None
    return basis


async def _prefs(project_id: str) -> dict[str, int]:
    try:
        from app.services.taste.signals import preference_map

        return await preference_map(project_id)
    except Exception:  # noqa: BLE001
        return {}


async def run_propose_job(job_id: str, project_id: str, concern: Optional[str]) -> None:
    try:
        await jobs_db.mark_processing(job_id)

        async def say(text: str) -> None:
            log_memory(f"refine: {text}")
            await _progress(job_id, text)

        await say("Waiting for my ears to be free...")
        async with HEAVY:
            report = await listen_project.measure_song(project_id, None, progress=say)
        found = findings_mod.find_issues(report, concern).model_dump()
        await say("Thinking of a few ways to go...")
        basis = await load_basis(project_id)
        message, directions, experiment = await asyncio.to_thread(
            propose_mod.propose, concern, found, basis["sections"], basis["seed"], basis["mix_params"], basis["lead"] is not None,
            True, basis["fp"] or None, basis["lead"], await _prefs(project_id),
        )
        if not directions:
            await jobs_db.mark_failed(job_id, "I couldn't find a change to try on this song yet. Build a beat or record a take first?")
            return
        # The Creative Director: an option that would take away something theirs says so, once (spec 10, req 3).
        from app.services.team import identity

        ident, _ = await identity.context(project_id)
        for d in directions:
            drift = identity.drift_notes(ident, direction=d.model_dump(), their_tune=basis["lead"] is not None)
            note = await identity.mention_once(project_id, "direction:" + drift[0], drift[0]) if drift else None
            if note:
                message = f"{message} One thing about \u201c{d.title}\u201d: {note}"
                break
        row = await asyncio.to_thread(refine_db.insert_proposal, {
            "project_id": project_id, "concern": concern, "findings": found, "experiment": experiment,
            "directions": [d.model_dump() for d in directions],
            "based_on": {"beat": basis["beat_id"], "mix": basis["mix_id"]},
        })
        await jobs_db.mark_complete(job_id, {
            "proposal_id": row["id"], "message": message, "experiment": experiment,
            "directions": [d.model_dump() for d in directions],
            "findings": found.get("findings", []), "could_not_check": found.get("could_not_check", []),
        })
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "Frank couldn't listen and think that through just now. Want to try again?")
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ── previews ─────────────────────────────────────────────────────────────

PREVIEW_GAP = beat_engine.PREVIEW_GAP_SECONDS


def _runs(indices: list[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    for i in sorted(set(indices)):
        if runs and runs[-1][-1] == i - 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    return runs


def _decode_piece(path: str, start: float, seconds: float) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{seconds:.3f}", "-i", path,
         "-f", "s16le", "-ac", "2", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True, check=True, timeout=120,
    ).stdout
    return np.frombuffer(out, dtype=np.int16).reshape(-1, 2)


def cut_before(render_url: str, sections: list[beat_engine.SectionPlan], indices: list[int], bpm: float) -> Optional[bytes]:
    """The same sections from the current song, joined the way a preview joins them. MP3 bytes."""
    if not indices:
        return None
    spans = beat_engine.section_spans(sections, bpm)
    data = fetch_audio_bytes(render_url, timeout=60)
    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        del data
        gap = np.zeros((int(PREVIEW_GAP * SAMPLE_RATE), 2), dtype=np.int16)
        pieces: list[np.ndarray] = []
        for n, run in enumerate(_runs(indices)):
            a, b = spans[run[0]][0], spans[run[-1]][1]
            if n:
                pieces.append(gap)
            pieces.append(_decode_piece(path, a / SAMPLE_RATE, (b - a) / SAMPLE_RATE))
        return to_mp3_bytes(np.concatenate(pieces)) if pieces else None
    finally:
        os.unlink(path)


def _beat_preview_sync(basis: dict, d: Direction) -> dict:
    sections, seed, lead, fp = basis["sections"], basis["seed"], basis["lead"], basis["fp"]
    new, new_seed, _ = ops_mod.apply_operations(sections, seed, d.actions)       # a copy: the saved plan is untouched
    song_gain = ((basis.get("beat") or {}).get("params") or {}).get("song_gain")
    audio = beat_engine.render_excerpt(new, d.sections, fp, new_seed, lead, song_gain=song_gain)
    preview_url = upload_audio("beats", to_mp3_bytes(audio), extension="mp3", name_prefix="preview")
    del audio
    # The same sections in the current song, matched by identity (a moved section is found where it was).
    old_at = {(s.uid if s.uid is not None else s.index): s.index for s in sections}
    before_idx = [old_at[u] for u in ((new[i].uid if new[i].uid is not None else i) for i in d.sections) if u in old_at]
    before_url = None
    render_url = (basis.get("beat") or {}).get("render_url")
    if render_url and before_idx:
        mp3 = cut_before(render_url, sections, before_idx, float(fp.get("tempo_bpm", 90)))
        if mp3:
            before_url = upload_audio("beats", mp3, extension="mp3", name_prefix="preview-before")
    return {"preview_url": preview_url, "before_url": before_url}


def made_well_words(before: float, after: float) -> str:
    """Audiobox's production-quality score (1..10) as a plain sentence. Small moves are within its noise."""
    d = after - before
    if d >= 0.3:
        return "This version sounds more polished than the one you have."
    if d <= -0.3:
        return "This version sounds a little less polished than the one you have, though you may still like it more."
    return "It's about as polished as the one you have; it's a matter of taste."


def score_change(before_url: Optional[str], after_url: Optional[str]) -> Optional[dict]:
    """Before and after, scored by Meta Audiobox Aesthetics on frank-ears (frankenstein spec 14, 2.4). None if asleep."""
    from app.services.remote import organs
    from app.services.storage.signing import fetch_audio_bytes

    if not before_url or not after_url:
        return None
    try:
        b = organs.try_(organs.aesthetics, fetch_audio_bytes(before_url), "mp3")
        a = organs.try_(organs.aesthetics, fetch_audio_bytes(after_url), "mp3")
    except Exception:  # noqa: BLE001
        return None
    if not a or not b or "made_well" not in a or "made_well" not in b:
        return None
    return {"before": b["made_well"], "after": a["made_well"], "plain": made_well_words(b["made_well"], a["made_well"])}


async def run_preview_job(job_id: str, project_id: str, proposal_id: str, n: int) -> None:
    from app.routers.mix import apply_actions
    from app.services.jobs import mix_runner

    try:
        await jobs_db.mark_processing(job_id)
        row = await asyncio.to_thread(refine_db.get_proposal, proposal_id)
        if not row or row["project_id"] != project_id or not 0 <= n < len(row.get("directions") or []):
            await jobs_db.mark_failed(job_id, "I can't find that idea any more. Ask me again?")
            return
        d = Direction(**row["directions"][n])
        if d.preview_url:                                  # already heard once: same file, no new render
            await jobs_db.mark_complete(job_id, {"n": n, "preview_url": d.preview_url, "before_url": d.before_url})
            return
        basis = await load_basis(project_id)
        stale = (d.kind == "beat" and basis["beat_id"] != (row.get("based_on") or {}).get("beat"))
        if stale:
            await jobs_db.mark_failed(job_id, "The song has changed since I suggested these. Ask me again and I'll listen fresh.")
            return
        await _progress(job_id, "Playing it the new way..." if d.kind == "beat" else "Mixing it the new way...")
        if d.kind == "beat":
            async with HEAVY:
                urls = await asyncio.to_thread(_beat_preview_sync, basis, d)
        else:
            params, _ = apply_actions(basis["mix_params"] or {}, d.actions)
            layers = await mix_runner._resolve_layers(project_id)
            async with HEAVY:
                urls = await asyncio.to_thread(mix_runner._render_preview_sync, layers, params)
            urls = {"preview_url": urls["render_url"], "before_url": (basis.get("mix") or {}).get("render_url")}
        await _progress(job_id, "Checking whether it sounds better made...")
        made_well = await asyncio.to_thread(score_change, urls.get("before_url"), urls.get("preview_url"))
        if made_well:
            urls["made_well"] = made_well
            await asyncio.to_thread(provenance.note, project_id, "refine", proposal_id, "aesthetics")
        await asyncio.to_thread(refine_db.update_direction, proposal_id, n, urls)
        await jobs_db.mark_complete(job_id, {"n": n, **urls})
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "Frank couldn't play that idea just now. Want to try again?")
        except Exception:  # noqa: BLE001
            pass
        raise exc
