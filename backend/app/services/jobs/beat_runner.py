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
import logging
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

log = logging.getLogger("frank.beat")


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
        # Where bar 1 falls in the singer's recording, for music built from their singing (core-path spec 15, 8)
        "start_s": float(fp.get("music_start_s") or 0.0),
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
    project_id: str, fingerprint: dict, label: str, seed: int, lead: lead_mod.Lead | None = None,
    structure: dict | None = None, min_seconds: float = 0.0,
) -> dict:
    """
    The entire heavy job, run in ONE worker thread: render the beat, encode MP3,
    upload everything, and write the records using the sync Supabase client.

    Keeping all blocking work (CPU render + sync Supabase I/O) inside a single
    thread avoids interleaving sync HTTP calls with the event loop, which was
    causing connection races in the storage client. Returns the version dict.
    """
    log_memory("beat: start render")
    report: dict = {}
    sections, mixes, full = beat_engine.render_full_beat(fingerprint, seed, lead, structure, report=report,
                                                         min_seconds=min_seconds)
    log_memory("beat: rendered")
    fp = beat_engine.fp_utils.normalize(fingerprint)
    return _persist_sync(project_id, sections, mixes, full, fp, label, seed, lead, song_gain=report.get("song_gain"),
                         section_gains=report.get("section_gains"))


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
    report: dict = {}
    mixes, full = beat_engine.rerender_all(sections, fp, seed, lead, report=report)
    return _persist_sync(
        project_id, sections, mixes, full, fp, label, seed, lead, changes, operations, song_gain=report.get("song_gain"),
        section_gains=report.get("section_gains"),
    )


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
    song_gain: float | None = None,
    section_gains: list[float] | None = None,
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
    if song_gain is not None:
        params["song_gain"] = song_gain        # previews of later changes play at this level
    if section_gains is not None:
        params["section_gains"] = section_gains   # the parts can be rendered one at a time at the same level
    version = beat_db.create_beat_version_sync(project_id, render_url, label, params)
    _credit_beat(project_id, version["id"], sections, fp)

    for section, mix in zip(sections, section_mixes):
        section_mp3 = to_mp3_bytes(mix)
        section_url = upload_audio(
            "beats", section_mp3, extension="mp3", name_prefix=f"section-{section.name}"
        )
        beat_db.create_stem_sync(
            project_id, version["id"], "section", section.name, section_url
        )

    return version


def _credit_beat(project_id: str, version_id: str, sections: list, fp: dict) -> None:
    """Which of Frank's organs shaped this beat (frankenstein spec 14, 1.3): drummers' feel, recorded instruments."""
    from app.services import provenance
    from app.services.generation import grooves, sampled

    layers = {p for s in sections for p in s.layers}
    if "drums" in layers and not isinstance(fp.get("groove"), dict) and grooves.for_style("_default"):
        provenance.note(project_id, "beat", version_id, "groove")
    if sampled.enabled() and layers & set(sampled.INSTRUMENTS):
        provenance.note(project_id, "beat", version_id, "samples")


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
        # The person's words decide the song's shape when they have been read (song-engine task 3.1).
        try:
            structure = await song_record.active_facet(project_id, "structure")
        except Exception:  # noqa: BLE001  a missing record never stops a beat
            structure = None

        # As long as their singing, when they have recorded (core-path spec 15, requirement 3.1)
        from app.services.audio.duration import active_voice_seconds

        voice_s = await active_voice_seconds(project_id)
        # Entire heavy job (render + encode + upload + records) in one thread
        async with _one_at_a_time:
            version = await asyncio.to_thread(
                _render_and_persist_sync, project_id, fingerprint, label, seed, lead, structure, voice_s
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


async def lengthen_to_voice(project_id: str) -> str | None:
    """
    Before a mix: when the singing goes on after the music ends, the active beat is lengthened with more of its own
    verse and chorus (a NEW version; the shorter one is kept). Returns a plain line when it changed, else None.
    """
    from app.services.audio.duration import active_voice_seconds

    voice_s = await active_voice_seconds(project_id)
    if voice_s <= 0:
        return None
    try:
        sections, fp, seed, lead = await _load_active_arrangement(project_id)
    except ValueError:
        return None
    bpm = float(fp.get("tempo_bpm") or 90)
    # The music may start a moment into the recording (music built from the singing): it has to reach the end of the
    # singing from there, not from the first second.
    voice_s -= float(fp.get("music_start_s") or 0.0)
    longer, changed = beat_engine.extend_sections(sections, bpm, voice_s)
    if not changed:
        return None
    line = "Your singing went on after the music ended, so I made the music longer to carry you to the end."
    count = await beat_db.count_beat_versions(project_id)
    async with _one_at_a_time:
        version = await asyncio.to_thread(_rerender_and_persist_sync, project_id, longer, fp, f"Beat v{count + 1}",
                                          seed, lead, [line], [{"op": "lengthen_to_voice"}])
    await projects_db.update_project_active_state(project_id, {"active_beat_version_id": version["id"]})
    return line


async def _remember_speed(project_id: str, fp: dict) -> None:
    """The song's new speed is the song's speed from now on: a new beat later keeps it."""
    from app.db import feel as feel_db

    try:
        latest = await feel_db.get_latest_fingerprint(project_id)
        base = dict((latest or {}).get("fingerprint") or {})
        base["tempo_bpm"] = fp["tempo_bpm"]
        saved = await feel_db.save_fingerprint(project_id, base, (latest or {}).get("conversation_summary"))
        await projects_db.update_project_active_state(project_id, {"active_fingerprint_id": saved["id"]})
    except Exception:  # noqa: BLE001 - the beat itself is already at the new speed
        log.warning("could not save the new speed to the feeling", exc_info=True)


def _has_takes(project_id: str) -> bool:
    from app.db import voice as voice_db

    try:
        return voice_db.count_takes_sync(project_id) > 0
    except Exception:  # noqa: BLE001
        return False


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
            # Speed first (core-path spec 15, 2.2): it changes the whole song, not one part.
            fp, rest, changes = ops_mod.apply_speed(fp, operations)
            if rest:
                sections, seed, more, _ = ops_mod.apply_audible(sections, seed, rest, fp, lead)
                changes += more
        except ops_mod.OpError as exc:
            await jobs_db.mark_failed(job_id, str(exc))
            return
        if len(rest) < len(operations):
            await _remember_speed(project_id, fp)
            if await asyncio.to_thread(_has_takes, project_id):
                changes.append("Your recording was sung at the old speed, so sing it again over this one when it feels right.")
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


# ── the song's parts for mixing (finish-and-intent spec 11, requirement 1) ──

def _parts_sync(project_id: str, version: dict) -> dict:
    """
    Render and store one file per part family for this beat version, at exactly its level inside the beat.
    Older beats did not save their section levels: one silent full render learns them first (slower, once).
    Parts of this song's OTHER beat versions are removed: they are a cache and can be re-made exactly.
    """
    from app.services.storage.files import remove_objects

    params = version.get("params") or {}
    sections, fp = beat_engine.sections_from_params(params)
    seed = params.get("seed")
    seed = seed if isinstance(seed, int) else beat_engine.default_seed(fp)
    lead = beat_engine.lead_from_params(params)          # the tune THIS version was built with
    gains, song_gain = params.get("section_gains"), params.get("song_gain")
    if not gains or song_gain is None or len(gains) != len(sections):
        report: dict = {}
        beat_engine.render_song(sections, fp, seed, lead=lead, report=report)
        gains, song_gain = report["section_gains"], report["song_gain"]
    urls: dict[str, str] = {}

    def on_part(name: str, audio: np.ndarray) -> None:
        url = upload_audio("beats", to_mp3_bytes(audio), extension="mp3", name_prefix=f"part-{name}")
        beat_db.create_stem_sync(project_id, version["id"], name, beat_db.PART_SECTION, url)
        urls[name] = url

    log_memory("parts: start")
    beat_engine.render_parts(sections, fp, seed, lead, gains, song_gain, on_part)
    log_memory("parts: rendered")
    old = [s for s in beat_db.list_part_stems_sync(project_id) if s["beat_version_id"] != version["id"]]
    if old:
        remove_objects([s["audio_url"] for s in old])
        beat_db.delete_stems_sync([s["id"] for s in old])
    return {"beat_version_id": version["id"], "parts": urls}


def cached_parts(project_id: str, beat_version_id: str) -> dict[str, str]:
    """The stored part files of a beat version (name -> url), or {} when they have not been made."""
    rows = [s for s in beat_db.list_part_stems_sync(project_id) if s["beat_version_id"] == beat_version_id]
    return {s["stem_type"]: s["audio_url"] for s in rows}


async def ensure_parts(project_id: str, beat_version_id: str) -> dict[str, str]:
    """Parts for a beat version, making them first when needed (inside the heavy gate)."""
    found = await asyncio.to_thread(cached_parts, project_id, beat_version_id)
    if found:
        return found
    version = await beat_db.get_beat_version(beat_version_id)
    if not version:
        return {}
    async with _one_at_a_time:
        out = await asyncio.to_thread(_parts_sync, project_id, version)
    return out["parts"]


async def run_parts_job(job_id: str, project_id: str, beat_version_id: str) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        parts = await ensure_parts(project_id, beat_version_id)
        if not parts:
            await jobs_db.mark_failed(job_id, "I can't find that beat any more.")
            return
        await jobs_db.mark_complete(job_id, {"beat_version_id": beat_version_id, "parts": sorted(parts)})
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "Frank couldn't separate the parts just now. Want to try again?")
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ── a part written around the person's tune (frankenstein spec 14, requirement 3.4) ──────────────────────

def pick_accompaniment(parts: list[dict], max_notes: int = 400) -> dict | None:
    """The fullest non-drum part the model wrote, as (note, start, duration, velocity) inside the tune's length."""
    melodic = [p for p in parts if not p.get("drums") and p.get("notes")]
    if not melodic:
        return None
    best = max(melodic, key=lambda p: len(p["notes"]))
    notes = [(int(n["note"]), round(float(n["start"]), 4), round(float(n["duration"]), 4), max(1, min(127, int(n.get("velocity", 80)))))
             for n in best["notes"]][:max_notes]
    return {"preset": int(best["program"]) if 0 <= int(best["program"]) < 128 else 0, "notes": notes}


async def run_accompany_job(job_id: str, project_id: str) -> None:
    from app.services import provenance
    from app.services.generation import lead as lead_mod
    from app.services.remote import organs
    from app.services.remote.spaces import RemoteUnavailable

    try:
        await jobs_db.mark_processing(job_id)
        sections, fp, seed, lead = await _load_active_arrangement(project_id)
        if lead is None:
            await jobs_db.mark_failed(job_id, "I need your tune first. Hum it to me in the Feeling room, then I can write a part around it.")
            return
        notes = [{"note": p, "start": st, "duration": du, "velocity": 90} for p, st, du in lead.notes]
        try:
            parts = await asyncio.to_thread(organs.accompany, notes, float(fp["tempo_bpm"]), lead.bars * 4.0)
        except RemoteUnavailable as e:
            await jobs_db.mark_failed(job_id, e.plain)
            return
        chosen = pick_accompaniment(parts)
        if not chosen:
            await jobs_db.mark_failed(job_id, "Nothing came back that would sit well with your tune. Want to try again?")
            return
        hit = [s for s in sections if s.name in lead_mod.LEAD_SECTIONS] or sections
        for s in hit:
            s.parts["accompaniment"] = {**chosen, "bars": lead.bars}
            if "accompaniment" not in s.layers:
                s.layers.append("accompaniment")
        changes = ["I wrote a new part around your tune where it plays, so your tune has company."]
        count = await beat_db.count_beat_versions(project_id)
        label = f"Beat v{count + 1}"
        async with _one_at_a_time:
            version = await asyncio.to_thread(_rerender_and_persist_sync, project_id, sections, fp, label, seed, lead,
                                              changes, [{"op": "accompany"}])
        await projects_db.update_project_active_state(project_id, {"active_beat_version_id": version["id"]})
        await asyncio.to_thread(provenance.note, project_id, "beat", version["id"], "accompaniment")
        await jobs_db.mark_complete(job_id, {"beat_version_id": version["id"], "render_url": version["render_url"],
                                             "label": label, "changes": changes})
    except Exception as exc:  # noqa: BLE001
        await jobs_db.mark_failed(job_id, "I couldn't write that part just now. Your beat is unchanged. Want to try again?")
        raise exc


# ── Music that plays to the singer (core-path spec 15, requirement 8) ──────────────────────────────────

FOLLOW_MIN_SECONDS = 15.0       # shorter than this is a sketch, not a song to build around
FOLLOWED = ("I listened to how you sang it and built the music around you: it moves at your speed, the chords fit "
            "the notes you sing, and it changes where your verses and choruses change. The music you sang over is kept.")


def _follow_sync(project_id: str, take: dict | None, vocal_url: str, lyrics: str, structure: dict | None,
                 intent: str, fp_base: dict, sung_over: dict | None, label: str, seed: int) -> dict | None:
    from app.services.audio import pitch as pitch_svc
    from app.services.audio import vocal_notes
    from app.services.generation import accompany
    from app.services.generation import fingerprint as fp_utils
    from app.services.jobs.voice_runner import _fetch, _read_mono

    mono = _read_mono(_fetch(vocal_url))
    sung = [accompany.Note(n.start, n.end, float(n.centre)) for n in vocal_notes.sung_notes(mono, pitch_svc.SR)
            if n.length > 0.12 and n.centre == n.centre]
    del mono
    if len(sung) < accompany.MIN_NOTES or (max(n.end for n in sung) - sung[0].start) < FOLLOW_MIN_SECONDS:
        return None
    lines = ((take or {}).get("words") or {}).get("lines") or []
    params = (take or {}).get("params") or {}
    if params.get("song_time") and sung_over:
        # They sang over Frank's music: its pulse is already theirs, and the take is in its time.
        bp = sung_over.get("params") or {}
        grid = accompany.Grid(float((bp.get("fingerprint") or {}).get("tempo_bpm") or 90), float(bp.get("start_s") or 0.0))
    else:
        starts = [l["start"] for l in lines if l.get("start") is not None]
        grid = accompany.grid_from_notes(sung, f"{intent} {lyrics}", starts)
    sections = accompany.sections_from_words(lines, structure, lyrics)
    how = "words"
    if not sections:
        sections, how = accompany.sections_from_phrases(sung, grid), "phrases"
    fp = fp_utils.normalize({**fp_base, "tempo_bpm": grid.bpm})
    acc = accompany.plan(sung, grid, sections, fp, how)
    if acc is None:
        return None
    key_name, mode = acc.key.split(" ", 1)
    fp = {**fp, "key": acc.key, "mode": mode, "music_start_s": round(grid.start_s, 4), "follows_voice": True}
    fp.pop("key_from_tune", None)
    version = _rerender_and_persist_sync(project_id, acc.sections, fp, label, seed, None, [FOLLOWED],
                                         [{"op": "follow_voice", "how": how}])
    return {"version": version, "how": how, "bpm": grid.bpm, "sections": [s.name for s in acc.sections],
            "start_s": grid.start_s}


async def run_follow_voice_job(job_id: str, project_id: str) -> None:
    """Build the music around the song's current recording (a NEW beat version; the old one is kept)."""
    from app.db import feel as feel_db
    from app.db import lyrics as lyrics_db
    from app.db import voice as voice_db
    from app.services.audio.vocal_resolution import resolve_vocal_url

    try:
        await jobs_db.mark_processing(job_id)
        state = await projects_db.get_project_active_state(project_id) or {}
        take = await voice_db.get_take(state["active_vocal_id"]) if state.get("active_vocal_id") else None
        comp = await voice_db.get_comp(state["active_comp_id"]) if state.get("active_comp_id") else None
        vocal_url = resolve_vocal_url(comp, take)
        if not vocal_url:
            await jobs_db.mark_failed(job_id, "Record yourself singing first, then I'll build the music around you.")
            return
        lyrics = ((await lyrics_db.get_version(state["active_lyrics_id"])) or {}).get("content", "") if state.get("active_lyrics_id") else ""
        structure = await song_record.active_facet(project_id, "structure")
        intent = (await song_record.active_facet(project_id, "intent") or {}).get("text") or ""
        latest = await feel_db.get_latest_fingerprint(project_id)
        sung_over = None
        bvid = ((take or {}).get("params") or {}).get("beat_version_id")
        if bvid:
            sung_over = await beat_db.get_beat_version(bvid)
        base = dict((latest or {}).get("fingerprint") or ((sung_over or {}).get("params") or {}).get("fingerprint") or {})
        count = await beat_db.count_beat_versions(project_id)
        label = f"Beat v{count + 1}"
        seed = derive_seed(project_id, "follow", count)
        async with _one_at_a_time:
            out = await asyncio.to_thread(_follow_sync, project_id, take, vocal_url, lyrics, structure, intent, base,
                                          sung_over, label, seed)
        if out is None:
            await jobs_db.mark_failed(job_id, "I need a little more singing to build the music around you: a verse or "
                                              "more works best.")
            return
        version = out["version"]
        await projects_db.update_project_active_state(project_id, {"active_beat_version_id": version["id"]})
        await jobs_db.mark_complete(job_id, {"beat_version_id": version["id"], "render_url": version["render_url"],
                                             "label": label, "changes": [FOLLOWED], "message": FOLLOWED,
                                             "how": out["how"], "sections": out["sections"]})
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "I couldn't build the music around your singing just now. Want to try again?")
        except Exception:  # noqa: BLE001
            pass
        raise exc
