"""
Voice Room job runners.

CPU-bound vocal work runs in background threads: pitch analysis after upload,
pitch correction, vocal comping, and harmony generation. Each follows Frank's
pattern — do the blocking work (analysis/processing + upload + DB record) in one
worker thread, and never overwrite the original take.
"""

from __future__ import annotations
import asyncio

from app.services.storage.signing import fetch_audio_bytes
from app.db import jobs as jobs_db
from app.services.jobs.heavy import run_heavy
from app.db import voice as voice_db
from app.db import projects as projects_db
from app.services.storage.files import upload_audio
from app.services.audio import pitch as pitch_svc
from app.services.audio import comp as comp_svc
from app.services.audio import harmony as harmony_svc
from app.services.generation.renderer import to_mp3_bytes
import io
import soundfile as sf


def _fetch(url: str) -> bytes:
    """Download stored audio. Runs inside the worker thread, not the event loop."""
    return fetch_audio_bytes(url, timeout=30)


def _to_mp3(wav_bytes: bytes) -> bytes:
    """Convert WAV bytes to MP3 for compact, fast-streaming playback storage."""
    data, sr = sf.read(io.BytesIO(wav_bytes), dtype="int16")
    import numpy as np

    if data.ndim == 1:
        data = np.column_stack([data, data])  # to_mp3_bytes expects stereo
    return to_mp3_bytes(data)


# ─── Pitch analysis after upload ─────────────

def _analyze_take_sync(take_id: str, wav_bytes: bytes) -> list[dict]:
    """Detect the pitch contour and store it on the take."""
    contour = pitch_svc.detect_pitch_contour(wav_bytes)
    voice_db.update_take_sync(take_id, {"pitch_data": contour})
    return contour


async def run_pitch_analysis_job(
    job_id: str, take_id: str, wav_bytes: bytes
) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        contour = await run_heavy(_analyze_take_sync, take_id, wav_bytes)
        await jobs_db.mark_complete(
            job_id, {"take_id": take_id, "contour_points": len(contour)}
        )
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, "Couldn't analyze that take.")
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ─── Pitch correction ────────────────────────

def _correct_sync(project_id: str, take_id: str, audio_url: str, mode: str) -> dict:
    """
    Correct a take's pitch and store the result as the take's processed_url.
    The original audio_url is never touched — the user compares and chooses.
    Fetch + process + upload all run here, inside the worker thread.
    """
    wav_bytes = _fetch(audio_url)
    corrected_wav = pitch_svc.correct_pitch(wav_bytes, mode)
    # Store the playback copy as MP3 (small, streams fast); original stays WAV.
    corrected_mp3 = _to_mp3(corrected_wav)
    processed_url = upload_audio(
        "vocals", corrected_mp3, extension="mp3", name_prefix=f"tuned-{mode}"
    )
    voice_db.update_take_sync(take_id, {"processed_url": processed_url})
    return {"take_id": take_id, "processed_url": processed_url}


async def run_correction_job(
    job_id: str, project_id: str, take_id: str, audio_url: str, mode: str
) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        result = await run_heavy(
            _correct_sync, project_id, take_id, audio_url, mode
        )
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't tune that take — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ─── Vocal comp ──────────────────────────────

def _comp_sync(project_id: str, take_refs: list[tuple[str, str]]) -> dict:
    """take_refs: list of (take_id, audio_url). Fetches in-thread."""
    takes = [(tid, _fetch(url)) for tid, url in take_refs]
    comp_wav, segments = comp_svc.build_comp(takes)
    comp_mp3 = _to_mp3(comp_wav)
    comp_url = upload_audio("vocals", comp_mp3, extension="mp3", name_prefix="comp")
    record = voice_db.create_comp_sync(project_id, comp_url, segments)
    return {"comp_id": record["id"], "audio_url": comp_url, "segments": segments}


async def run_comp_job(
    job_id: str, project_id: str, take_refs: list[tuple[str, str]]
) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        result = await run_heavy(_comp_sync, project_id, take_refs)
        await projects_db.update_project_active_state(
            project_id, {"active_comp_id": result["comp_id"]}
        )
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't put that together — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ─── Harmony ─────────────────────────────────

def _harmony_sync(
    project_id: str,
    take_id: str,
    audio_url: str,
    harmony_type: str,
    mode: str | None,
) -> dict:
    """
    Generate a harmony layer from a take, using the song's mode so the interval
    fits the key. Stored as its own take record (a harmony layer). We store an
    empty pitch_data list (not null) so the UI doesn't show a perpetual
    "listening…" state for a harmony that was never a raw recording.
    """
    wav_bytes = _fetch(audio_url)
    harmony_wav = harmony_svc.generate_harmony(wav_bytes, harmony_type, mode)
    harmony_mp3 = _to_mp3(harmony_wav)
    harmony_url = upload_audio(
        "vocals", harmony_mp3, extension="mp3", name_prefix="harmony"
    )
    record = voice_db.create_take_sync(
        project_id, harmony_url, label=f"Harmony ({harmony_type})"
    )
    voice_db.update_take_sync(record["id"], {"pitch_data": []})
    return {"harmony_take_id": record["id"], "audio_url": harmony_url}


async def run_harmony_job(
    job_id: str,
    project_id: str,
    take_id: str,
    audio_url: str,
    harmony_type: str,
    mode: str | None = None,
) -> None:
    try:
        await jobs_db.mark_processing(job_id)
        result = await run_heavy(
            _harmony_sync, project_id, take_id, audio_url, harmony_type, mode
        )
        await jobs_db.mark_complete(job_id, result)
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(
                job_id, "Frank couldn't build that harmony — want to try again?"
            )
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ═══ Sing It (spec 06) ═══════════════════════════════════════════════════
# Every operation makes a NEW take row linked to the one it came from (kind: tuned, lined_up, cleaned, harmony);
# the original never changes. Each reports what it did in plain words, by section.

import numpy as np  # noqa: E402

from app.services.audio import align as align_svc  # noqa: E402
from app.services.audio import bleed as bleed_svc  # noqa: E402
from app.services.audio import engineer as engineer_svc  # noqa: E402
from app.services.audio import guide as guide_svc  # noqa: E402
from app.services.audio import song_notes  # noqa: E402
from app.services.audio import vocal_notes  # noqa: E402
from app.db import beat as beat_db  # noqa: E402

ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth"]
PLAIN_SECTION = {"intro": "intro", "verse": "verse", "pre-chorus": "build-up", "chorus": "chorus", "bridge": "bridge", "outro": "ending"}
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def _read_mono(wav_bytes: bytes) -> np.ndarray:
    data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if sr != pitch_svc.SR:
        import librosa

        mono = librosa.resample(mono, orig_sr=sr, target_sr=pitch_svc.SR)
    return mono.astype(np.float32)


def _wav(mono: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, np.clip(mono, -1.0, 1.0), pitch_svc.SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _beat_mono(render_url: str | None) -> np.ndarray | None:
    """The beat as it played, mono at the vocal's rate, in song time."""
    if not render_url:
        return None
    from app.services.audio import mixing

    stereo = mixing._load_stereo(_fetch(render_url))
    return stereo.mean(axis=0).astype(np.float32)          # _load_stereo gives (channels, samples)


def plural(word: str) -> str:
    return word + ("es" if word.endswith(("s", "sh", "ch")) else "s")


def section_phrase(song: song_notes.SongNotes, index: int | None) -> str:
    """'the second verse', or 'the chorus' when there is only one."""
    if index is None:
        return "the song"
    name = song.section_name(index) or "section"
    same = [s.value[0] for s in song.sections if s.value[1] == name]
    word = PLAIN_SECTION.get(name, name)
    if len(same) <= 1:
        return f"the {word}"
    k = same.index(index) if index in same else 0
    return f"the {ORDINALS[min(k, 5)]} {word}"


def describe_by_section(song: song_notes.SongNotes, items: list[dict], verb: str, noun: str = "note") -> str:
    """'I nudged four notes in the second verse and two in the last chorus.'"""
    if not items:
        return ""
    counts: dict = {}
    for it in items:
        counts[it.get("section")] = counts.get(it.get("section"), 0) + 1
    parts = []
    for idx, n in sorted(counts.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
        word = NUMBER_WORDS.get(n, str(n))
        parts.append(f"{word} {noun}{'s' if n != 1 else ''} in {section_phrase(song, idx)}" if not parts else
                     f"{word} in {section_phrase(song, idx)}")
    text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"I {verb} {text}."


def _derive(project_id: str, parent: dict, mono: np.ndarray, kind: str, label: str, params: dict, facts: dict,
            is_harmony: bool = False) -> dict:
    url = upload_audio("vocals", _to_mp3(_wav(mono)), extension="mp3", name_prefix=kind)
    return voice_db.create_take_sync(project_id, url, label=label, kind=kind, parent_take_id=parent["id"],
                                     params={**(parent.get("params") or {}), **params}, facts=facts, is_harmony=is_harmony)


async def _job(job_id: str, fail_message: str, fn, *args):
    """Run one heavy voice step as a job with a plain failure message."""
    try:
        await jobs_db.mark_processing(job_id)
        result = await run_heavy(fn, *args)
        if isinstance(result, dict) and result.get("failed"):
            await jobs_db.mark_failed(job_id, result["failed"])
            return None
        await jobs_db.mark_complete(job_id, result)
        return result
    except Exception as exc:  # noqa: BLE001
        try:
            await jobs_db.mark_failed(job_id, fail_message)
        except Exception:  # noqa: BLE001
            pass
        raise exc


# ── after every take: pitch line, facts, the engineer ────────────────────

def _after_take_sync(take: dict, wav_bytes: bytes, song: song_notes.SongNotes, beat_url: str | None) -> dict:
    mono = _read_mono(wav_bytes)
    contour = pitch_svc.detect_pitch_contour(wav_bytes)
    params = take.get("params") or {}
    beat = _beat_mono(beat_url) if params.get("beat_version_id") else None
    message, checks = engineer_svc.check(mono, pitch_svc.SR, beat, params.get("headphones"))
    notes = vocal_notes.sung_notes(mono, pitch_svc.SR)
    moves = pitch_svc.plan_moves(notes, song, "moderate")
    voiced = [n for n in notes if n.length > 0.12]
    covered = sorted({song.section_at((n.start + n.end) / 2) for n in voiced} - {None})
    facts = {
        "seconds": round(mono.shape[0] / pitch_svc.SR, 1),
        "sections": covered,
        "notes": len(voiced),
        "on_the_notes": round(1 - len(moves) / max(1, len(voiced)), 2) if voiced else None,
        "sits_ms": align_svc.sits_ms(mono, beat, pitch_svc.SR) if beat is not None else None,
        "bleed": checks.get("bleed"),
        "clipping": checks.get("clipping"),
        "noise_floor_db": checks.get("noise_floor_db"),
        "engineer": message,
    }
    voice_db.update_take_sync(take["id"], {"pitch_data": contour, "facts": facts})
    return {"take_id": take["id"], "contour_points": len(contour), "engineer": message, "facts": facts}


async def run_after_take_job(job_id: str, project_id: str, take: dict, wav_bytes: bytes) -> None:
    song = await song_notes.for_project(project_id)
    beat_url = None
    bvid = (take.get("params") or {}).get("beat_version_id")
    if bvid:
        bv = await beat_db.get_beat_version(bvid)
        beat_url = (bv or {}).get("render_url")
    await _job(job_id, "Couldn't listen to that take.", _after_take_sync, take, wav_bytes, song, beat_url)


# ── tuning to the song ───────────────────────────────────────────────────

MODE_WORDS = {"light": "Just the obvious mistakes", "moderate": "Tightened up", "full": "Locked in"}


def _tune_sync(project_id: str, take: dict, mode: str, song: song_notes.SongNotes) -> dict:
    mono = _read_mono(_fetch(take["audio_url"]))
    out, moves = pitch_svc.tune(mono, pitch_svc.SR, mode, song)
    if not moves:
        return {"take_id": take["id"], "moves": 0,
                "message": "Every note already sits where it belongs for this setting, so I left it exactly as you sang it."}
    derived = _derive(project_id, take, out, "tuned", f"{take.get('label') or 'Take'} · {MODE_WORDS.get(mode, mode)}",
                      {"mode": mode}, {"moves": moves[:400]})
    voice_db.update_take_sync(take["id"], {"processed_url": derived["audio_url"]})       # older screens look here
    return {"take_id": derived["id"], "parent_take_id": take["id"], "processed_url": derived["audio_url"], "moves": len(moves),
            "message": describe_by_section(song, moves, "nudged") + " Your original is kept, so you can compare."}


async def run_tune_job(job_id: str, project_id: str, take: dict, mode: str) -> None:
    song = await song_notes.for_project(project_id)
    await _job(job_id, "Frank couldn't tune that take. Want to try again?", _tune_sync, project_id, take, mode, song)


# ── timing ───────────────────────────────────────────────────────────────

def _align_sync(project_id: str, take: dict, mode: str, song: song_notes.SongNotes, beat_url: str | None) -> dict:
    mono = _read_mono(_fetch(take["audio_url"]))
    phrases = vocal_notes.phrases_from_energy(mono, pitch_svc.SR)
    out, moved = align_svc.tighten(mono, pitch_svc.SR, phrases, song.seconds_per_beat, mode)
    if not moved:
        return {"take_id": take["id"], "moved": 0,
                "message": "Your lines already start with the beat, so I didn't move anything."}
    beat = _beat_mono(beat_url)
    before, after = align_svc.sits_ms(mono, beat, pitch_svc.SR), align_svc.sits_ms(out, beat, pitch_svc.SR)
    for m in moved:
        m["section"] = song.section_at(m["start"])
    derived = _derive(project_id, take, out, "lined_up", f"{take.get('label') or 'Take'} · lined up", {"timing_mode": mode},
                      {"moved": moved, "sits_ms_before": before, "sits_ms_after": after, "sits_ms": after})
    msg = describe_by_section(song, moved, "lined up", "line")
    if before is not None and after is not None and abs(after) < abs(before) - 5:
        msg += " It sits closer to the beat now."
    return {"take_id": derived["id"], "parent_take_id": take["id"], "moved": len(moved), "message": msg + " Your original is kept."}


async def run_align_job(job_id: str, project_id: str, take: dict, mode: str) -> None:
    song = await song_notes.for_project(project_id)
    beat_url = await _beat_url(project_id, take)
    await _job(job_id, "Frank couldn't line that take up. Want to try again?", _align_sync, project_id, take, mode, song, beat_url)


async def _beat_url(project_id: str, take: dict) -> str | None:
    bvid = (take.get("params") or {}).get("beat_version_id")
    if not bvid:
        state = await projects_db.get_project_active_state(project_id) or {}
        bvid = state.get("active_beat_version_id")
    if not bvid:
        return None
    bv = await beat_db.get_beat_version(bvid)
    return (bv or {}).get("render_url")


# ── beat bleed ───────────────────────────────────────────────────────────

def _bleed_sync(project_id: str, take: dict, beat_url: str | None) -> dict:
    beat = _beat_mono(beat_url)
    if beat is None:
        return {"failed": "I need the beat that was playing to take it out, and I can't find it."}
    mono = _read_mono(_fetch(take["audio_url"]))
    out, report = bleed_svc.remove(mono, beat[: mono.shape[0]] if beat.shape[0] >= mono.shape[0]
                                   else np.pad(beat, (0, mono.shape[0] - beat.shape[0])), pitch_svc.SR)
    if not report.accepted:
        return {"take_id": take["id"], "accepted": False, "report": report.__dict__,
                "message": f"I tried taking the music out, but {report.reason}, so I kept your take as it was."}
    derived = _derive(project_id, take, out, "cleaned", f"{take.get('label') or 'Take'} · music taken out", {},
                      {"bleed_removed": report.__dict__, "bleed": 0.0})
    return {"take_id": derived["id"], "parent_take_id": take["id"], "accepted": True, "report": report.__dict__,
            "message": "I took the music out of your vocal. Have a listen with and without; your original is kept."}


async def run_bleed_job(job_id: str, project_id: str, take: dict) -> None:
    beat_url = await _beat_url(project_id, take)
    await _job(job_id, "Frank couldn't take the music out of that take. Want to try again?", _bleed_sync, project_id, take, beat_url)


# ── phrase comp and swap ─────────────────────────────────────────────────

def _phrase_comp_sync(project_id: str, take_refs: list[tuple[str, str]], song: song_notes.SongNotes,
                      labels: dict[str, str] | None = None) -> dict:
    takes = [(tid, _fetch(url)) for tid, url in take_refs]
    comp_wav, segments = comp_svc.build_phrase_comp(takes, song)
    url = upload_audio("vocals", _to_mp3(comp_wav), extension="mp3", name_prefix="comp")
    record = voice_db.create_comp_sync(project_id, url, segments)
    labels = labels or {}
    order = [tid for tid, _ in take_refs]
    used = [labels.get(t, f"take {order.index(t) + 1}") for t in order if any(s["take_id"] == t for s in segments)]
    said = used[0] if len(used) == 1 else ", ".join(used[:-1]) + " and " + used[-1]
    return {"comp_id": record["id"], "audio_url": url, "segments": segments,
            "message": (f"I put together a version from the best line of each part, using {said}. "
                        "It's a suggestion: you can swap any line for the same line from another take.")}


async def run_phrase_comp_job(job_id: str, project_id: str, take_refs: list[tuple[str, str]]) -> None:
    song = await song_notes.for_project(project_id)
    labels: dict[str, str] = {}
    for tid, _ in take_refs:
        try:
            labels[tid] = ((await voice_db.get_take(tid)) or {}).get("label") or "a take"
        except Exception:  # noqa: BLE001  a missing label only changes the wording
            pass
    result = await _job(job_id, "Frank couldn't put that together. Want to try again?", _phrase_comp_sync, project_id, take_refs, song, labels)
    if result:
        await projects_db.update_project_active_state(project_id, {"active_comp_id": result["comp_id"]})


def _swap_sync(project_id: str, comp: dict, take_refs: list[tuple[str, str]], phrase_index: int, take_id: str) -> dict:
    takes = [(tid, _fetch(url)) for tid, url in take_refs]
    try:
        comp_wav, segments = comp_svc.swap(takes, comp.get("segments") or [], phrase_index, take_id)
    except ValueError as exc:
        return {"failed": str(exc)}
    url = upload_audio("vocals", _to_mp3(comp_wav), extension="mp3", name_prefix="comp")
    record = voice_db.create_comp_sync(project_id, url, segments)
    return {"comp_id": record["id"], "audio_url": url, "segments": segments, "message": "Swapped. The earlier version is kept."}


async def run_swap_job(job_id: str, project_id: str, comp: dict, take_refs: list[tuple[str, str]], phrase_index: int, take_id: str) -> None:
    result = await _job(job_id, "Frank couldn't swap that line. Want to try again?", _swap_sync, project_id, comp, take_refs, phrase_index, take_id)
    if result:
        await projects_db.update_project_active_state(project_id, {"active_comp_id": result["comp_id"]})


# ── chord-following harmony ──────────────────────────────────────────────

def _chord_harmony_sync(project_id: str, take: dict, harmony_type: str, section_names: list[str] | None,
                        song: song_notes.SongNotes) -> dict:
    wanted = None
    if section_names:
        wanted = {s.value[0] for s in song.sections if s.value[1] in set(section_names)}
    harmony_wav, plan = harmony_svc.chord_harmony(_fetch(take["audio_url"]), song, harmony_type, wanted)
    if not plan:
        return {"failed": "I couldn't find notes to build a harmony on in that part of the take."}
    url = upload_audio("vocals", _to_mp3(harmony_wav), extension="mp3", name_prefix="harmony")
    def place(n: str) -> str:
        word = PLAIN_SECTION.get(n, n)
        return plural(word) if sum(s.value[1] == n for s in song.sections) > 1 else word

    where = " in the " + " and ".join(place(n) for n in section_names) if section_names else ""
    record = voice_db.create_take_sync(project_id, url, label=f"Harmony ({harmony_type}){where}", kind="harmony",
                                       parent_take_id=take["id"], params={"type": harmony_type, "sections": section_names or []},
                                       facts={"notes": len(plan)}, is_harmony=True)
    voice_db.update_take_sync(record["id"], {"pitch_data": []})
    return {"harmony_take_id": record["id"], "audio_url": url,
            "message": f"I made a harmony from your own voice{where}, following the chords. The Mix Room can turn it on or off."}


async def run_chord_harmony_job(job_id: str, project_id: str, take: dict, harmony_type: str, sections: list[str] | None) -> None:
    song = await song_notes.for_project(project_id)
    await _job(job_id, "Frank couldn't build that harmony. Want to try again?", _chord_harmony_sync, project_id, take,
               harmony_type, sections, song)


# ── the guide ────────────────────────────────────────────────────────────

def _guide_sync(beat_version_id: str, song: song_notes.SongNotes) -> dict:
    cached = voice_db.get_guide(beat_version_id)
    if cached:
        return {"guide_url": cached, "cached": True}
    audio = guide_svc.render_guide(song)
    if audio is None:
        return {"guide_url": None,
                "message": "There's no tune in the song yet, so just sing it your way. If you like what you sing, it can become the song's tune."}
    url = upload_audio("vocals", to_mp3_bytes(audio), extension="mp3", name_prefix="guide")
    voice_db.put_guide(beat_version_id, url)
    return {"guide_url": url, "cached": False}


async def run_guide_job(job_id: str, project_id: str, beat_version_id: str) -> None:
    song = await song_notes.for_project(project_id)
    await _job(job_id, "Frank couldn't make the sing-along guide. You can still sing with the beat.", _guide_sync, beat_version_id, song)


# ── the delay check ──────────────────────────────────────────────────────

def _delay_sync(wav_bytes: bytes, click_times: list[float]) -> dict:
    mono = _read_mono(wav_bytes)
    delay, conf = align_svc.detect_delay(mono, pitch_svc.SR, click_times)
    return {"delay_ms": None if delay is None else round(delay * 1000, 1), "confidence": round(conf, 2)}
